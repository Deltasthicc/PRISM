'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { ClipboardCheck } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { questionnairesApi } from '@/lib/api/questionnaires';
import { countdownText, formatDeadline } from '@/lib/questionnaireForm';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';

// Trainee list of questionnaires aimed at them (backend/routes/questionnaires.py).
// The status label always carries text; colour on the badge is only a hint.
// English only for now, like the other new PS75 pages.

const STATUS = {
  not_started: { label: 'Not started', tone: 'accent' },
  submitted: { label: 'Submitted', tone: 'success' },
  closed_missed: { label: 'Closed, not submitted', tone: 'danger' },
};

export default function QuestionnairesPage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);
  const playerId = player?.player_id;

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [nowMs, setNowMs] = useState(() => Date.now());

  const load = useCallback(async () => {
    if (!playerId) return;
    setLoading(true);
    setError('');
    try {
      setItems((await questionnairesApi.available(playerId)) || []);
    } catch (cause) {
      setError(cause.message || 'Could not load your questionnaires.');
    } finally {
      setLoading(false);
    }
  }, [playerId]);

  useEffect(() => {
    if (!ready) return;
    load();
  }, [ready, load]);

  // Keeps the countdown text fresh; the server alone decides what is open.
  useEffect(() => {
    const timer = setInterval(() => setNowMs(Date.now()), 30000);
    return () => clearInterval(timer);
  }, []);

  if (!ready || !player) return null;

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1 flex items-center gap-1.5">
          <ClipboardCheck size={12} aria-hidden="true" />
          Trainee
        </p>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">Questionnaires</h1>
        <p className="font-sans text-sm text-[#757682] mt-1">
          Questionnaires set by your trainers. Each one can be submitted once, before its deadline.
        </p>
      </div>

      {loading && (
        <p className="font-sans text-sm text-[#757682]" role="status">
          Loading your questionnaires…
        </p>
      )}
      {!loading && error && (
        <div className="flex flex-col gap-2 items-start">
          <p role="alert" className="font-sans text-sm text-[#b3261e]">
            {error}
          </p>
          <Button variant="ghost" onClick={load}>
            Retry
          </Button>
        </div>
      )}
      {!loading && !error && items.length === 0 && (
        <p className="font-sans text-sm text-[#757682]">
          Nothing to do right now. Questionnaires appear here when a trainer publishes one for your cohort or course.
        </p>
      )}

      {!loading && !error && (
        <ul className="flex flex-col gap-3">
          {items.map((item) => {
            const status = STATUS[item.status] || STATUS.not_started;
            const notYetOpen = item.status === 'not_started' && !item.is_open;
            return (
              <li key={item.questionnaire_id}>
                <Panel>
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div>
                      <h2 className="font-sans text-sm font-bold text-[#131b2e]">{item.title}</h2>
                      {item.description && (
                        <p className="font-sans text-xs text-[#757682] mt-0.5">{item.description}</p>
                      )}
                      <p className="font-sans text-xs text-[#444651] mt-1">
                        {item.question_count} question{item.question_count === 1 ? '' : 's'}. Due{' '}
                        {formatDeadline(item.due_at)}
                      </p>
                      <p className="font-sans text-xs font-semibold text-[#00236f]">
                        {item.status === 'submitted'
                          ? `Your score: ${item.score} out of ${item.max_score}`
                          : notYetOpen
                            ? `Opens ${formatDeadline(item.opens_at)}`
                            : countdownText(item.due_at, nowMs)}
                      </p>
                    </div>
                    <Badge tone={status.tone}>{status.label}</Badge>
                  </div>
                  <div className="mt-3">
                    <Link
                      href={`/questionnaires/${encodeURIComponent(item.questionnaire_id)}`}
                      className="font-sans text-sm text-[#00236f] underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#00236f]"
                    >
                      {item.status === 'not_started' && item.is_open
                        ? 'Start questionnaire'
                        : item.status === 'submitted'
                          ? 'View your result'
                          : 'View details'}
                      <span className="sr-only"> for {item.title}</span>
                    </Link>
                  </div>
                </Panel>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
