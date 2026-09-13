'use client';

// Real trainer flow for the "QR-code live quiz session" feature (backend/
// routes/live_sessions.py) -- a trainer picks one of their own quizzes
// (private or published, same visibility rule the backend enforces),
// creates a live session, shows the join_code big and a scannable QR code
// (client-side, via the `qrcode` package -- no server-side image generation
// needed), then runs the room: Start, Next question, End session, with a
// live participant list polled every ~3s. After ending, shows the real
// results leaderboard.
//
// Not yet translated into the other 10 UI languages -- plain English, same
// honesty convention as this project's other documented pending items (see
// app/sampling-lab/page.jsx).

import { Suspense, useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { useQuery, useMutation } from '@tanstack/react-query';
import QRCode from 'qrcode';
import { Radio, Play, ArrowRight, Square, Users, Trophy } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { learning, liveSessions } from '@/lib/api/client';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';

function ParticipantList({ participants }) {
  if (!participants) return null;
  return (
    <div className="mt-4 pt-4 border-t border-[#c5c5d3]/30">
      <p className="font-mono text-[10px] uppercase tracking-wide text-[#757682] mb-2 flex items-center gap-1.5">
        <Users size={12} aria-hidden="true" /> {participants.length} joined
      </p>
      {participants.length === 0 ? (
        <p className="font-sans text-sm text-[#757682]">
          Nobody has joined yet -- share the code or QR code above.
        </p>
      ) : (
        <ul className="flex flex-col gap-1">
          {participants.map((participant) => (
            <li
              key={participant.player_id}
              className="flex items-center justify-between gap-2 text-sm font-sans border border-[#c5c5d3]/20 rounded-md px-2 py-1"
            >
              <span className="text-[#131b2e]">{participant.username}</span>
              <span className="text-[#757682] font-mono text-xs">
                {participant.score != null ? `${participant.score}%` : `${participant.answered_count} answered`}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function HostSession() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);
  const searchParams = useSearchParams();
  const preselectedQuizId = searchParams.get('quizId') || '';

  const [selectedQuizId, setSelectedQuizId] = useState(preselectedQuizId);
  const [session, setSession] = useState(null);
  const [error, setError] = useState('');
  const [results, setResults] = useState(null);
  const qrCanvasRef = useRef(null);

  const { data: historyData } = useQuery({
    queryKey: ['quiz-history', player?.player_id],
    queryFn: () => learning.listQuizzes(player.player_id),
    enabled: ready && !!player,
  });

  // A live session can only be hosted from a quiz that already exists in a
  // stable, takeable state -- not one still awaiting or rejected by review.
  const hostableQuizzes = (historyData?.quizzes || []).filter(
    (quiz) => quiz.review_status === 'private' || quiz.review_status === 'published'
  );

  const createSession = useMutation({
    mutationFn: () => liveSessions.create(player.player_id, selectedQuizId),
    onSuccess: (data) => {
      setError('');
      setSession(data);
    },
    onError: (e) => setError(e.message),
  });

  const startSession = useMutation({
    mutationFn: () => liveSessions.start(session.session_id),
    onError: (e) => setError(e.message),
  });

  const advanceSession = useMutation({
    mutationFn: () => liveSessions.advance(session.session_id),
    onError: (e) => setError(e.message),
  });

  const endSession = useMutation({
    mutationFn: async () => {
      await liveSessions.end(session.session_id);
      return liveSessions.getResults(session.session_id, player.player_id);
    },
    onSuccess: (data) => setResults(data),
    onError: (e) => setError(e.message),
  });

  // Polling, not a websocket -- this is how the host sees the room actually
  // engage in real time. Cheap: a handful of indexed row lookups server-side.
  const { data: liveState } = useQuery({
    queryKey: ['live-session-state', session?.session_id],
    queryFn: () => liveSessions.getState(session.session_id, player.player_id),
    enabled: ready && !!session && session.status !== 'ended',
    refetchInterval: 3000,
  });

  useEffect(() => {
    if (liveState) setSession((prev) => (prev ? { ...prev, ...liveState } : prev));
  }, [liveState]);

  useEffect(() => {
    if (session?.join_code && qrCanvasRef.current) {
      const joinUrl = `${window.location.origin}/join/${session.join_code}`;
      QRCode.toCanvas(qrCanvasRef.current, joinUrl, { width: 200, margin: 1 }, (err) => {
        if (err) console.error('QR render failed', err);
      });
    }
  }, [session?.join_code]);

  if (!ready) return null;

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-5">
      <div>
        <div className="flex items-center gap-2">
          <Radio className="text-[#00236f]" size={20} aria-hidden="true" />
          <h1 className="font-sans text-lg font-bold text-[#00236f]">Host a Live Session</h1>
        </div>
        <p className="font-sans text-sm text-[#757682] mt-2 max-w-2xl">
          Run one of your quizzes live for a room of learners -- everyone joins on their own phone
          or laptop with a code or QR scan, sees the same question at the same time, and you
          control the pace.
        </p>
      </div>

      {error && (
        <p className="font-sans text-sm text-[#b3261e] bg-[#fce8e6] border border-[#f5c6c2] rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {!session && (
        <Panel>
          <h2 className="font-sans text-base font-bold text-[#131b2e] mb-3">Choose a quiz to host</h2>
          {hostableQuizzes.length === 0 ? (
            <p className="font-sans text-sm text-[#757682]">
              You don&apos;t have a quiz to host yet -- generate one from the Source Quiz Generator
              first.
            </p>
          ) : (
            <div className="flex flex-col gap-2">
              {hostableQuizzes.map((quiz) => (
                <label
                  key={quiz.quiz_id}
                  className={`flex items-center justify-between gap-2 border rounded-lg px-3 py-2 cursor-pointer ${
                    selectedQuizId === quiz.quiz_id ? 'border-[#00236f]' : 'border-[#c5c5d3]/40'
                  }`}
                >
                  <span className="flex items-center gap-2">
                    <input
                      type="radio"
                      name="quiz"
                      checked={selectedQuizId === quiz.quiz_id}
                      onChange={() => setSelectedQuizId(quiz.quiz_id)}
                    />
                    <span className="font-sans text-sm font-semibold text-[#131b2e]">{quiz.title}</span>
                  </span>
                  <span className="flex items-center gap-2">
                    <Badge tone="default">{quiz.question_count} questions</Badge>
                    <Badge tone={quiz.review_status === 'published' ? 'success' : 'default'}>
                      {quiz.review_status}
                    </Badge>
                  </span>
                </label>
              ))}
            </div>
          )}
          <div className="mt-4">
            <Button
              disabled={!selectedQuizId || createSession.isPending}
              onClick={() => createSession.mutate()}
            >
              Create session
            </Button>
          </div>
        </Panel>
      )}

      {session && session.status === 'waiting' && (
        <Panel variant="accent">
          <div className="flex flex-col items-center gap-3 py-4">
            <p className="font-mono text-xs uppercase tracking-wide text-[#757682]">Join code</p>
            <p className="font-mono text-5xl font-bold text-[#00236f] tracking-[0.3em]">{session.join_code}</p>
            <canvas ref={qrCanvasRef} className="rounded-lg" />
            <p className="font-sans text-sm text-[#757682] text-center">
              Scan the code, or go to <span className="font-mono">/join/{session.join_code}</span> on
              any device.
            </p>
            <Button onClick={() => startSession.mutate()} disabled={startSession.isPending}>
              <span className="flex items-center gap-1.5">
                <Play size={14} aria-hidden="true" /> Start session
              </span>
            </Button>
          </div>
          <ParticipantList participants={session.participants} />
        </Panel>
      )}

      {session && session.status === 'active' && (
        <Panel variant="accent">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Badge tone="accent">
              Question {session.current_question_index + 1} of {session.question_count}
            </Badge>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                onClick={() => advanceSession.mutate()}
                disabled={advanceSession.isPending || session.current_question_index >= session.question_count - 1}
              >
                <span className="flex items-center gap-1.5">
                  <ArrowRight size={14} aria-hidden="true" /> Next question
                </span>
              </Button>
              <Button variant="danger" onClick={() => endSession.mutate()} disabled={endSession.isPending}>
                <span className="flex items-center gap-1.5">
                  <Square size={14} aria-hidden="true" /> End session
                </span>
              </Button>
            </div>
          </div>
          {session.current_question && (
            <p className="font-sans text-sm font-semibold text-[#131b2e] mt-4">
              {session.current_question.question}
            </p>
          )}
          <ParticipantList participants={session.participants} />
        </Panel>
      )}

      {session && session.status === 'ended' && (
        <Panel>
          <div className="flex items-center gap-2 mb-3">
            <Trophy className="text-[#fe932c]" size={18} aria-hidden="true" />
            <h2 className="font-sans text-base font-bold text-[#131b2e]">Final results</h2>
          </div>
          {!results ? (
            <p className="font-sans text-sm text-[#757682]">Loading results...</p>
          ) : results.leaderboard.length === 0 ? (
            <p className="font-sans text-sm text-[#757682]">Nobody joined this session.</p>
          ) : (
            <ol className="flex flex-col gap-2">
              {results.leaderboard.map((row, index) => (
                <li
                  key={row.player_id}
                  className="flex items-center justify-between gap-2 border border-[#c5c5d3]/30 rounded-lg px-3 py-2"
                >
                  <span className="font-sans text-sm font-semibold text-[#131b2e]">
                    #{index + 1} {row.username}
                  </span>
                  <Badge tone={index === 0 ? 'success' : 'default'}>{row.score}%</Badge>
                </li>
              ))}
            </ol>
          )}
        </Panel>
      )}
    </div>
  );
}

export default function HostSessionPage() {
  return (
    <Suspense fallback={null}>
      <HostSession />
    </Suspense>
  );
}
