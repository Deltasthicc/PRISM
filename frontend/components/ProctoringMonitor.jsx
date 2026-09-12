'use client';

// Real, client-side webcam exam-integrity monitor. Detection runs entirely
// in the browser via real ML models (blazeface for face count, coco-ssd for
// object/phone detection) -- no video frame or image is ever sent anywhere.
// Only the resulting violation *events* are reported through
// lib/api/client.js's `proctoring` export, which hits
// backend/routes/proctoring.py -- see that route's docstring for the full
// privacy + anti-fabrication rationale (this is an audit signal, never a
// pass/fail gate, and must never block or auto-fail the exam).
//
// Not yet translated into the other 10 UI languages -- English only for now,
// same honesty convention as this project's other documented pending items
// (see app/sampling-lab/page.jsx).

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Camera, Loader2, ShieldCheck, VideoOff } from 'lucide-react';
import { proctoring } from '@/lib/api/client';

const POLL_INTERVAL_MS = 2500;
// A continuously-true condition (e.g. the camera stays blocked by a hand for
// the whole exam) re-pings the reviewer at most this often -- frequent
// enough that a long-running violation isn't silently lost, but nowhere near
// once-per-poll, which would make the counter noise rather than signal.
const RECHECK_COOLDOWN_MS = 20000;
// Discrete browser events (tab switch / fullscreen exit) get a short
// debounce window so one real switch can't double-log from a jittery
// visibilitychange/fullscreenchange firing twice for the same action.
const EVENT_COOLDOWN_MS = 4000;
const PHONE_CONFIDENCE_THRESHOLD = 0.6;

export const VIOLATION_LABELS = {
  no_face_detected: 'No face detected',
  multiple_faces_detected: 'Multiple faces detected',
  phone_detected: 'Phone detected in frame',
  tab_switch: 'Switched away from the exam tab',
  fullscreen_exit: 'Exited fullscreen',
};

/**
 * Props:
 *  - playerId, attemptId: identify the quiz attempt this session's
 *    violations are logged against (see backend/routes/proctoring.py).
 *  - enabled: the learner's explicit opt-in. While false, no camera is
 *    requested and no listeners are attached -- consent must be an
 *    affirmative action, never a silent default.
 *  - onViolation(violationType, detail): fired whenever a new violation is
 *    detected (after this component's own debounce/cooldown), so the parent
 *    can keep a running count for its own summary UI.
 */
export default function ProctoringMonitor({ playerId, attemptId, enabled, onViolation }) {
  const videoRef = useRef(null);
  const streamRef = useRef(null);
  const pollRef = useRef(null);
  const modelsRef = useRef({ face: null, phone: null });
  // Per-violation-type debounce state: { active, lastFiredAt }.
  const violationStateRef = useRef({});

  const [permission, setPermission] = useState('idle'); // idle | requesting | granted | denied | error
  const [modelsStatus, setModelsStatus] = useState('idle'); // idle | loading | ready | error
  const [modelsError, setModelsError] = useState('');
  const [log, setLog] = useState([]); // [{type, detail, at}]

  const reportViolation = useCallback(
    (type, detail) => {
      setLog((prev) => [...prev, { type, detail: detail ?? null, at: Date.now() }]);
      onViolation?.(type, detail ?? null);
      if (playerId && attemptId) {
        proctoring
          .reportViolation(playerId, attemptId, type, detail != null ? String(detail) : undefined)
          .catch(() => {
            // Best-effort logging only -- a failed report must never
            // interrupt or gate the live exam.
          });
      }
    },
    [playerId, attemptId, onViolation]
  );

  // Debounced reporter for a continuous, poll-sampled condition (face
  // count, phone presence): fires the moment the condition first becomes
  // true, stays quiet while it remains true, and only re-fires after
  // RECHECK_COOLDOWN_MS if it never cleared.
  const signalCondition = useCallback(
    (type, isActiveNow, detail) => {
      const state = violationStateRef.current[type] || { active: false, lastFiredAt: 0 };
      if (isActiveNow) {
        const now = Date.now();
        if (!state.active || now - state.lastFiredAt > RECHECK_COOLDOWN_MS) {
          reportViolation(type, detail);
          state.lastFiredAt = now;
        }
        state.active = true;
      } else {
        state.active = false;
      }
      violationStateRef.current[type] = state;
    },
    [reportViolation]
  );

  // Debounced reporter for a one-off browser event.
  const signalEvent = useCallback(
    (type, detail) => {
      const state = violationStateRef.current[type] || { active: false, lastFiredAt: 0 };
      const now = Date.now();
      if (now - state.lastFiredAt > EVENT_COOLDOWN_MS) {
        reportViolation(type, detail);
        state.lastFiredAt = now;
      }
      violationStateRef.current[type] = state;
    },
    [reportViolation]
  );

  // Camera + model lifecycle, tied to `enabled`. Never starts the camera
  // silently -- only ever runs while the caller has already recorded an
  // explicit opt-in.
  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;

    async function start() {
      setPermission('requesting');
      let stream;
      try {
        stream = await navigator.mediaDevices.getUserMedia({ video: true });
      } catch {
        if (!cancelled) setPermission('denied');
        return;
      }
      if (cancelled) {
        stream.getTracks().forEach((track) => track.stop());
        return;
      }
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setPermission('granted');

      setModelsStatus('loading');
      try {
        const [tf, blazeface, cocoSsd] = await Promise.all([
          import('@tensorflow/tfjs'),
          import('@tensorflow-models/blazeface'),
          import('@tensorflow-models/coco-ssd'),
        ]);
        await tf.ready();
        const [faceModel, phoneModel] = await Promise.all([blazeface.load(), cocoSsd.load()]);
        if (cancelled) return;
        modelsRef.current = { face: faceModel, phone: phoneModel };
        setModelsStatus('ready');
      } catch (cause) {
        if (!cancelled) {
          setModelsStatus('error');
          setModelsError(cause?.message || 'Could not load the on-device detection models.');
        }
      }
    }

    start();

    return () => {
      cancelled = true;
      // Stop every track explicitly -- a leaked open camera stream is both
      // a real privacy issue and an easy thing to miss.
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
        streamRef.current = null;
      }
      modelsRef.current = { face: null, phone: null };
      setPermission('idle');
      setModelsStatus('idle');
    };
  }, [enabled]);

  // Polling loop: real inference against the live video frame.
  useEffect(() => {
    if (!enabled || permission !== 'granted' || modelsStatus !== 'ready') return undefined;

    async function tick() {
      const video = videoRef.current;
      const { face, phone } = modelsRef.current;
      if (!video || !face || !phone || video.readyState < 2) return;

      try {
        const faces = await face.estimateFaces(video, false);
        signalCondition('no_face_detected', faces.length === 0);
        signalCondition('multiple_faces_detected', faces.length > 1);
      } catch {
        // Transient WebGL/frame-read failure -- skip this tick rather than
        // tearing down the whole monitor.
      }

      try {
        const predictions = await phone.detect(video);
        const bestPhone = predictions
          .filter((p) => p.class === 'cell phone' && p.score >= PHONE_CONFIDENCE_THRESHOLD)
          .sort((a, b) => b.score - a.score)[0];
        signalCondition(
          'phone_detected',
          Boolean(bestPhone),
          bestPhone ? bestPhone.score.toFixed(2) : undefined
        );
      } catch {
        // Same as above.
      }
    }

    pollRef.current = setInterval(tick, POLL_INTERVAL_MS);
    tick();

    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [enabled, permission, modelsStatus, signalCondition]);

  // Non-camera signals: tab switch + fullscreen exit. Active for the whole
  // time `enabled` is true, independent of camera permission/model state --
  // these don't need the camera at all.
  useEffect(() => {
    if (!enabled) return undefined;

    function handleVisibility() {
      if (document.hidden) signalEvent('tab_switch');
    }
    function handleFullscreenChange() {
      if (!document.fullscreenElement) signalEvent('fullscreen_exit');
    }

    document.addEventListener('visibilitychange', handleVisibility);
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => {
      document.removeEventListener('visibilitychange', handleVisibility);
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, [enabled, signalEvent]);

  if (!enabled) return null;

  const isActive = permission === 'granted' && modelsStatus === 'ready';

  return (
    <div className="bg-white border border-[#dfe2eb] rounded-2xl shadow-[0_5px_20px_rgba(0,35,111,0.04)] p-5">
      <div className="flex items-center justify-between mb-3">
        <div>
          <p className="text-[10px] uppercase tracking-[0.12em] font-bold font-mono text-[#00236f]">
            Integrity Monitor
          </p>
          <p className="text-[10px] text-[#8a8f9d] font-mono mt-1">On-device webcam check</p>
        </div>
        <span
          className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg font-mono text-[10px] font-bold ${
            isActive ? 'bg-[#d7f4ee] text-[#005147]' : 'bg-[#eef1ff] text-[#757682]'
          }`}
        >
          {isActive ? (
            <>
              <ShieldCheck size={12} /> Active
            </>
          ) : (
            <>
              <Loader2 size={12} className="animate-spin" /> Starting
            </>
          )}
        </span>
      </div>

      <div className="relative w-full aspect-video rounded-xl overflow-hidden bg-[#10182b] border border-[#c5c5d3]/40">
        {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
        <video ref={videoRef} muted autoPlay playsInline className="w-full h-full object-cover" />

        {permission !== 'granted' && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#10182b]/95 px-4 text-center">
            {permission === 'denied' ? (
              <p className="text-[11px] font-mono text-white/80 flex flex-col items-center gap-2">
                <VideoOff size={18} />
                Camera access was denied. Integrity monitoring is off -- your exam continues normally.
              </p>
            ) : permission === 'error' ? (
              <p className="text-[11px] font-mono text-white/80">Could not start the camera.</p>
            ) : (
              <p className="text-[11px] font-mono text-white/70 flex flex-col items-center gap-2">
                <Camera size={18} className="animate-pulse" />
                Requesting camera access…
              </p>
            )}
          </div>
        )}

        {permission === 'granted' && modelsStatus !== 'ready' && (
          <div className="absolute inset-0 flex items-center justify-center bg-[#10182b]/70 px-4 text-center">
            <p className="text-[11px] font-mono text-white/80 flex flex-col items-center gap-2">
              <Loader2 size={18} className="animate-spin" />
              {modelsStatus === 'error'
                ? modelsError || 'Could not load detection models.'
                : 'Loading proctoring models…'}
            </p>
          </div>
        )}
      </div>

      <div className="mt-3 flex items-center justify-between text-[10px] font-mono">
        <span className="text-[#757682]">
          {permission === 'granted' ? 'Proctoring active' : 'Proctoring unavailable'}
        </span>
        <span className={`font-bold ${log.length > 0 ? 'text-[#904d00]' : 'text-[#005147]'}`}>
          {log.length} integrity signal{log.length === 1 ? '' : 's'} this session
        </span>
      </div>

      <p className="mt-2 text-[9px] text-[#8a8f9d] font-mono leading-relaxed">
        Detection runs entirely in your browser. No video or image ever leaves your device -- only
        the resulting signal (e.g. &quot;phone detected&quot;) is recorded for a human reviewer.
      </p>
    </div>
  );
}
