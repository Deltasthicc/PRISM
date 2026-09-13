'use client';

// Real participant flow for the "QR-code live quiz session" feature
// (backend/routes/live_sessions.py) -- reached either by scanning the QR
// code app/host-session/page.jsx renders (which encodes a deep link
// straight into this route) or by typing the join code in by hand. Resolves
// the code, joins automatically, then polls the shared session state to
// stay in lockstep with whatever question the host is currently showing --
// answering locks that question until the host advances, matching a real
// live-quiz feel (no self-pacing here, unlike the ordinary quiz flow).
//
// Not yet translated into the other 10 UI languages -- plain English, same
// honesty convention as this project's other documented pending items (see
// app/sampling-lab/page.jsx).

import { Suspense, useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Radio, CheckCircle2, Clock, Trophy } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { liveSessions } from '@/lib/api/client';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';

function JoinSession() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);
  const params = useParams();
  const joinCode = (params.joinCode || '').toString();

  const [sessionId, setSessionId] = useState(null);
  const [error, setError] = useState('');
  const [joined, setJoined] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(null);
  const [results, setResults] = useState(null);

  // Step 1: resolve the code to a session, then join it -- both are
  // idempotent/safe to run once per mount.
  useEffect(() => {
    if (!ready || !player || !joinCode) return;
    let cancelled = false;
    (async () => {
      try {
        const resolved = await liveSessions.resolveJoinCode(joinCode);
        if (cancelled) return;
        setSessionId(resolved.session_id);
        await liveSessions.join(resolved.session_id, player.player_id);
        if (!cancelled) setJoined(true);
      } catch (cause) {
        if (!cancelled) setError(cause.message);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [ready, player, joinCode]);

  // Step 2: poll the shared session state -- this is how the room stays in
  // lockstep with the host without a websocket.
  const { data: state } = useQuery({
    queryKey: ['live-session-state', sessionId],
    queryFn: () => liveSessions.getState(sessionId, player.player_id),
    enabled: ready && !!player && !!sessionId && joined,
    refetchInterval: 3000,
  });

  // A new question means any locally-selected (but not yet submitted)
  // choice from the previous question is stale.
  useEffect(() => {
    setSelectedIndex(null);
  }, [state?.current_question_index]);

  useEffect(() => {
    if (state?.status === 'ended' && !results) {
      liveSessions.getResults(sessionId, player.player_id).then(setResults).catch(() => {});
    }
  }, [state?.status, results, sessionId, player]);

  const submitAnswer = useMutation({
    mutationFn: (choiceIndex) =>
      liveSessions.answer(sessionId, player.player_id, state.current_question_index, choiceIndex),
    onError: (e) => setError(e.message),
  });

  if (!ready) return null;

  return (
    <div className="max-w-xl mx-auto flex flex-col gap-5">
      <div className="flex items-center gap-2">
        <Radio className="text-[#00236f]" size={20} aria-hidden="true" />
        <h1 className="font-sans text-lg font-bold text-[#00236f]">Live Session</h1>
        <Badge tone="accent">{joinCode.toUpperCase()}</Badge>
      </div>

      {error && (
        <p className="font-sans text-sm text-[#b3261e] bg-[#fce8e6] border border-[#f5c6c2] rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {!joined && !error && (
        <Panel>
          <p className="font-sans text-sm text-[#757682]">Joining session {joinCode.toUpperCase()}...</p>
        </Panel>
      )}

      {joined && !state && (
        <Panel>
          <p className="font-sans text-sm text-[#757682]">Loading...</p>
        </Panel>
      )}

      {joined && state && state.status === 'waiting' && (
        <Panel variant="accent">
          <div className="flex flex-col items-center gap-2 py-6">
            <Clock className="text-[#757682]" size={24} aria-hidden="true" />
            <p className="font-sans text-sm text-[#757682]">
              You&apos;re in! Waiting for the host to start the session...
            </p>
          </div>
        </Panel>
      )}

      {joined && state && state.status === 'active' && state.current_question && (
        <Panel variant="accent">
          <Badge tone="default">
            Question {state.current_question_index + 1} of {state.question_count}
          </Badge>
          <p className="font-sans text-base font-semibold text-[#131b2e] mt-3 mb-4">
            {state.current_question.question}
          </p>
          {state.has_answered_current_question ? (
            <div className="flex flex-col gap-2">
              {(state.current_question.options || []).map((option, index) => (
                <div
                  key={option}
                  className={`flex items-center gap-2 border rounded-lg px-3 py-2 font-sans text-sm ${
                    index === state.current_question.answer_index
                      ? 'border-[#1a7f4b] bg-[#e6f4ea] text-[#1a7f4b] font-medium'
                      : 'border-[#c5c5d3]/30 text-[#444651]'
                  }`}
                >
                  {String.fromCharCode(65 + index)}. {option}
                  {index === state.current_question.answer_index && (
                    <CheckCircle2 size={14} className="ml-auto" aria-hidden="true" />
                  )}
                </div>
              ))}
              <p className="font-mono text-[10px] uppercase tracking-wide text-[#757682] mt-2 flex items-center gap-1.5">
                <Clock size={12} aria-hidden="true" /> Waiting for the host to move to the next question...
              </p>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {(state.current_question.options || []).map((option, index) => (
                <button
                  key={option}
                  type="button"
                  disabled={submitAnswer.isPending}
                  onClick={() => {
                    setSelectedIndex(index);
                    submitAnswer.mutate(index);
                  }}
                  className={`text-left border rounded-lg px-3 py-2 font-sans text-sm transition-colors disabled:opacity-60 ${
                    selectedIndex === index
                      ? 'border-[#00236f] bg-[#f2f3ff] text-[#00236f] font-medium'
                      : 'border-[#c5c5d3]/40 text-[#131b2e] hover:border-[#00236f]/30'
                  }`}
                >
                  {String.fromCharCode(65 + index)}. {option}
                </button>
              ))}
            </div>
          )}
        </Panel>
      )}

      {joined && state && state.status === 'ended' && (
        <Panel>
          <div className="flex items-center gap-2 mb-3">
            <Trophy className="text-[#fe932c]" size={18} aria-hidden="true" />
            <h2 className="font-sans text-base font-bold text-[#131b2e]">Session ended</h2>
          </div>
          {state.score != null && (
            <p className="font-sans text-sm text-[#131b2e] mb-3">
              Your score: <span className="font-bold">{state.score}%</span>
            </p>
          )}
          {!results ? (
            <p className="font-sans text-sm text-[#757682]">Loading final results...</p>
          ) : (
            <ol className="flex flex-col gap-2">
              {results.leaderboard.map((row, index) => (
                <li
                  key={row.player_id}
                  className={`flex items-center justify-between gap-2 border rounded-lg px-3 py-2 ${
                    row.player_id === player.player_id ? 'border-[#00236f]' : 'border-[#c5c5d3]/30'
                  }`}
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

export default function JoinSessionPage() {
  return (
    <Suspense fallback={null}>
      <JoinSession />
    </Suspense>
  );
}
