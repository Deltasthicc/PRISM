'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { Mic, MicOff, BookOpen, ShieldAlert, Volume2, VolumeX } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import { API_BASE_URL } from '@/lib/config';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';

// A real, full-duplex voice interface to the Learner Assistant --
// backend/routes/ai_voice.py's WebSocket protocol: mic PCM16 @ 16kHz streamed
// up, real faster-whisper transcription, the same access-filtered RAG
// assistant /assistant already uses, and Piper TTS streamed back as PCM16
// chunks. All audio processing (downsampling, PCM16 encoding, playback
// queueing) happens client-side with the Web Audio API -- no audio file, no
// upload, nothing written to disk on either side.
//
// TTS requires a local Piper voice model (PIPER_MODEL_PATH) that this repo
// deliberately does not commit (see README's Voice AI pipeline section) --
// without one, the server honestly reports a TTS_FAILURE per turn rather
// than pretending to speak. This page still shows the real transcript and
// the real grounded answer either way; a "voice reply unavailable" note
// takes the place of playback when that happens, rather than failing silently.

const STATE = {
  IDLE: 'idle',
  CONNECTING: 'connecting',
  LISTENING: 'listening',
  PROCESSING: 'processing',
  SPEAKING: 'speaking',
  ERROR: 'error',
};

function wsUrlFor(path) {
  const httpUrl = new URL(path, API_BASE_URL);
  httpUrl.protocol = httpUrl.protocol === 'https:' ? 'wss:' : 'ws:';
  return httpUrl.toString();
}

// Linear-interpolation resample from the AudioContext's native rate (48kHz
// or 44.1kHz on most browsers, never guaranteed to be 16kHz) down to the
// 16kHz mono PCM16 the backend requires, then encodes to signed 16-bit
// little-endian bytes.
function floatTo16kPCM16(float32, sourceSampleRate) {
  const ratio = sourceSampleRate / 16000;
  const outLength = Math.floor(float32.length / ratio);
  const out = new Int16Array(outLength);
  for (let i = 0; i < outLength; i++) {
    const srcIndex = i * ratio;
    const i0 = Math.floor(srcIndex);
    const i1 = Math.min(i0 + 1, float32.length - 1);
    const frac = srcIndex - i0;
    const sample = float32[i0] * (1 - frac) + float32[i1] * frac;
    const clamped = Math.max(-1, Math.min(1, sample));
    out[i] = clamped < 0 ? clamped * 32768 : clamped * 32767;
  }
  return out.buffer;
}

export default function VoiceAssistantPage() {
  const { ready } = useRequireAuth();
  const { t } = useLanguage();

  const [state, setState] = useState(STATE.IDLE);
  const [errorMessage, setErrorMessage] = useState('');
  const [transcript, setTranscript] = useState('');
  const [answer, setAnswer] = useState(null);
  const [ttsUnavailable, setTtsUnavailable] = useState(false);

  const wsRef = useRef(null);
  const audioContextRef = useRef(null);
  const micStreamRef = useRef(null);
  const processorRef = useRef(null);
  const playbackQueueTimeRef = useRef(0);
  const playbackNodesRef = useRef([]);

  const stopMic = useCallback(() => {
    processorRef.current?.disconnect();
    processorRef.current = null;
    micStreamRef.current?.getTracks().forEach((track) => track.stop());
    micStreamRef.current = null;
  }, []);

  const stopPlayback = useCallback(() => {
    playbackNodesRef.current.forEach((node) => {
      try {
        node.stop();
      } catch {
        // Already stopped -- fine to ignore.
      }
    });
    playbackNodesRef.current = [];
    if (audioContextRef.current) {
      playbackQueueTimeRef.current = audioContextRef.current.currentTime;
    }
  }, []);

  const disconnect = useCallback(() => {
    stopMic();
    stopPlayback();
    wsRef.current?.close();
    wsRef.current = null;
    setState(STATE.IDLE);
  }, [stopMic, stopPlayback]);

  useEffect(() => () => disconnect(), [disconnect]);

  function playPCM16Chunk(bytes, sampleRate, channels) {
    if (!audioContextRef.current) return;
    const ctx = audioContextRef.current;
    const int16 = new Int16Array(bytes);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) float32[i] = int16[i] / 32768;

    const buffer = ctx.createBuffer(channels || 1, float32.length, sampleRate || 22050);
    buffer.getChannelData(0).set(float32);

    const source = ctx.createBufferSource();
    source.buffer = buffer;
    source.connect(ctx.destination);

    const startAt = Math.max(ctx.currentTime, playbackQueueTimeRef.current);
    source.start(startAt);
    playbackQueueTimeRef.current = startAt + buffer.duration;
    playbackNodesRef.current.push(source);
    source.onended = () => {
      playbackNodesRef.current = playbackNodesRef.current.filter((n) => n !== source);
    };
  }

  async function startConversation() {
    setErrorMessage('');
    setTranscript('');
    setAnswer(null);
    setTtsUnavailable(false);
    setState(STATE.CONNECTING);

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (cause) {
      setState(STATE.ERROR);
      setErrorMessage(t('voicePage.micDenied'));
      return;
    }
    micStreamRef.current = stream;

    const AudioContextCtor = window.AudioContext || window.webkitAudioContext;
    const audioContext = new AudioContextCtor();
    audioContextRef.current = audioContext;
    playbackQueueTimeRef.current = audioContext.currentTime;

    const ws = new WebSocket(wsUrlFor('/ai/voice/stream'));
    wsRef.current = ws;
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      ws.send(JSON.stringify({ type: 'start', sample_rate: 16000, channels: 1, format: 'pcm_s16le' }));
    };

    ws.onerror = () => {
      setState(STATE.ERROR);
      setErrorMessage(t('voicePage.connectionError'));
    };

    ws.onclose = () => {
      stopMic();
    };

    ws.onmessage = (event) => {
      if (typeof event.data !== 'string') {
        // Binary audio frame -- always immediately preceded by its own
        // "audio_chunk" JSON metadata message, handled in the branch below.
        return;
      }
      const msg = JSON.parse(event.data);
      switch (msg.type) {
        case 'ready': {
          const source = audioContext.createMediaStreamSource(stream);
          const processor = audioContext.createScriptProcessor(4096, 1, 1);
          processorRef.current = processor;
          processor.onaudioprocess = (audioEvent) => {
            const input = audioEvent.inputBuffer.getChannelData(0);
            const pcm16Buffer = floatTo16kPCM16(input, audioContext.sampleRate);
            if (ws.readyState === WebSocket.OPEN) ws.send(pcm16Buffer);
          };
          source.connect(processor);
          processor.connect(audioContext.destination);
          setState(STATE.LISTENING);
          break;
        }
        case 'speech_start':
          setState(STATE.LISTENING);
          break;
        case 'speech_end':
          setState(STATE.PROCESSING);
          break;
        case 'transcript':
          setTranscript(msg.text);
          break;
        case 'assistant':
          setAnswer(msg);
          break;
        case 'audio_chunk':
          ws._pendingChunkMeta = msg;
          setState(STATE.SPEAKING);
          ws.addEventListener(
            'message',
            function onBinary(binEvent) {
              if (typeof binEvent.data !== 'string') {
                playPCM16Chunk(binEvent.data, msg.sample_rate, msg.channels);
                ws.removeEventListener('message', onBinary);
              }
            },
            { once: false }
          );
          break;
        case 'interrupt':
          stopPlayback();
          setState(STATE.LISTENING);
          break;
        case 'turn_complete':
          setState(STATE.LISTENING);
          break;
        case 'error':
          if (msg.code === 'TTS_FAILURE') {
            setTtsUnavailable(true);
            setState(STATE.LISTENING);
          } else {
            setState(STATE.ERROR);
            setErrorMessage(msg.message || t('voicePage.connectionError'));
          }
          break;
        default:
          break;
      }
    };
  }

  const isActive = state !== STATE.IDLE && state !== STATE.ERROR;

  const statusLabel = {
    [STATE.IDLE]: t('voicePage.statusIdle'),
    [STATE.CONNECTING]: t('voicePage.statusConnecting'),
    [STATE.LISTENING]: t('voicePage.statusListening'),
    [STATE.PROCESSING]: t('voicePage.statusProcessing'),
    [STATE.SPEAKING]: t('voicePage.statusSpeaking'),
    [STATE.ERROR]: t('voicePage.statusError'),
  }[state];

  const statusTone = {
    [STATE.IDLE]: 'default',
    [STATE.CONNECTING]: 'warning',
    [STATE.LISTENING]: 'accent',
    [STATE.PROCESSING]: 'warning',
    [STATE.SPEAKING]: 'success',
    [STATE.ERROR]: 'danger',
  }[state];

  if (!ready) {
    return <p className="font-sans text-sm text-[#757682] text-center mt-10">{t('assistantPage.loadingShell')}</p>;
  }

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1">
          {t('voicePage.eyebrow')}
        </p>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">{t('voicePage.title')}</h1>
        <p className="font-sans text-sm text-[#757682] mt-1 max-w-xl">{t('voicePage.subtitle')}</p>
      </div>

      <Panel>
        <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
          <Badge tone={statusTone}>{statusLabel}</Badge>
          {ttsUnavailable && (
            <span className="flex items-center gap-1.5 font-mono text-[10px] text-[#904d00]">
              <VolumeX size={12} />
              {t('voicePage.ttsUnavailable')}
            </span>
          )}
        </div>

        <div className="flex justify-center">
          <button
            type="button"
            onClick={isActive ? disconnect : startConversation}
            className={
              'w-20 h-20 rounded-full flex items-center justify-center shadow-md transition-colors ' +
              (isActive ? 'bg-[#b3261e] hover:bg-[#8f1e18]' : 'bg-[#00236f] hover:bg-[#001a54]')
            }
            aria-label={isActive ? t('voicePage.stopButton') : t('voicePage.startButton')}
          >
            {isActive ? <MicOff size={28} className="text-white" /> : <Mic size={28} className="text-white" />}
          </button>
        </div>
        <p className="text-center font-sans text-xs text-[#757682] mt-3">
          {isActive ? t('voicePage.stopButton') : t('voicePage.startButton')}
        </p>

        {errorMessage && (
          <p className="mt-3 flex items-center gap-1.5 justify-center font-sans text-xs text-[#b3261e]">
            <ShieldAlert size={14} />
            {errorMessage}
          </p>
        )}
      </Panel>

      {transcript && (
        <Panel>
          <p className="font-mono text-[10px] font-bold uppercase text-[#757682] mb-1.5">
            {t('voicePage.youSaid')}
          </p>
          <p className="font-sans text-sm text-[#131b2e]">{transcript}</p>
        </Panel>
      )}

      {answer && (
        <Panel>
          <div className="flex items-center justify-between gap-3 flex-wrap mb-2">
            <span className="font-sans text-xs font-semibold text-[#757682]">{t('voicePage.answerHeading')}</span>
            {answer.status === 'supported' ? (
              <Badge tone="success">{t('assistantPage.statusSupported')}</Badge>
            ) : (
              <Badge tone="warning">{t('assistantPage.statusInsufficientEvidence')}</Badge>
            )}
          </div>
          <p className="font-sans text-sm text-[#131b2e] leading-6">{answer.answer}</p>
          {answer.citations?.length > 0 && (
            <div className="mt-4 pt-3 border-t border-[#c5c5d3]/30">
              <p className="font-mono text-[10px] font-bold uppercase text-[#757682] mb-2 flex items-center gap-1.5">
                <BookOpen size={12} />
                {t('assistantPage.citationsHeading')}
              </p>
              <div className="flex flex-col gap-2">
                {answer.citations.map((c) => (
                  <div key={c.citation_id} className="p-3 rounded-lg bg-[#f7f7fb] border border-[#c5c5d3]/40">
                    <p className="font-mono text-[10px] text-[#8a8f9d] mb-1">
                      {c.filename} — {c.locator_label}
                    </p>
                    <p className="font-sans text-xs text-[#333a49] italic">&ldquo;{c.quote}&rdquo;</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Panel>
      )}

      <Panel className="bg-[#f7f7fb]">
        <p className="flex items-center gap-1.5 font-mono text-[10px] text-[#8a8f9d]">
          <Volume2 size={12} />
          {t('voicePage.footerNote')}
        </p>
      </Panel>
    </div>
  );
}
