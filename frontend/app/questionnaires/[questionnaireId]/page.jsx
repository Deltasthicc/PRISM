'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { questionnairesApi } from '@/lib/api/questionnaires';
import { countdownText, formatDeadline } from '@/lib/questionnaireForm';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';

// Trainee attempt page. The questions arrive WITHOUT the answer key; the key
// and per-question correctness come back only after the (single) submission,
// all computed server-side. The visible countdown is a convenience -- the
// server's clock decides whether a submission is accepted.
// English only for now, like the other new PS75 pages.

function ResultView({ attempt }) {
  return (
    <Panel variant="accent">
      <h2 className="font-sans text-sm font-bold text-[#131b2e]" tabIndex={-1} id="questionnaire-result">
        Your result: {attempt.score} out of {attempt.max_score}
      </h2>
      <p className="font-sans text-xs text-[#757682] mt-1">Submitted {formatDeadline(attempt.submitted_at)}.</p>
      <ol className="flex flex-col gap-3 mt-3 list-decimal pl-5">
        {attempt.questions.map((question) => (
          <li key={question.question_id} className="font-sans text-sm text-[#131b2e]">
            <p className="font-semibold">{question.prompt}</p>
            <p className="mt-0.5">
              <Badge tone={question.is_correct ? 'success' : 'danger'}>
                {question.is_correct ? 'Correct' : 'Incorrect'}
              </Badge>
            </p>
            <ul className="mt-1 flex flex-col gap-0.5">
              {question.options.map((option, optionIndex) => {
                const chosen = question.selected_index === optionIndex;
                const correct = question.correct_index === optionIndex;
                return (
                  <li key={optionIndex} className="text-xs text-[#444651]">
                    {option}
                    {chosen && <strong> (your answer)</strong>}
                    {correct && <strong> (correct answer)</strong>}
                  </li>
                );
              })}
            </ul>
          </li>
        ))}
      </ol>
    </Panel>
  );
}

export default function QuestionnaireAttemptPage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);
  const playerId = player?.player_id;
  const params = useParams();
  const questionnaireId = params?.questionnaireId;

  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [answers, setAnswers] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [result, setResult] = useState(null);
  const [nowMs, setNowMs] = useState(() => Date.now());

  const load = useCallback(async () => {
    if (!playerId || !questionnaireId) return;
    setLoading(true);
    setLoadError('');
    try {
      setDetail(await questionnairesApi.get(questionnaireId, playerId));
    } catch (cause) {
      setLoadError(cause.message || 'Could not load this questionnaire.');
    } finally {
      setLoading(false);
    }
  }, [playerId, questionnaireId]);

  useEffect(() => {
    if (!ready) return;
    load();
  }, [ready, load]);

  useEffect(() => {
    const timer = setInterval(() => setNowMs(Date.now()), 15000);
    return () => clearInterval(timer);
  }, []);

  async function handleSubmit(event) {
    event.preventDefault();
    if (!detail) return;
    const unanswered = detail.questions.filter((q) => answers[q.question_id] === undefined);
    if (unanswered.length) {
      setSubmitError(
        `Answer every question before submitting. Missing: ${unanswered.map((q) => q.position + 1).join(', ')}.`
      );
      return;
    }
    setSubmitting(true);
    setSubmitError('');
    try {
      const attempt = await questionnairesApi.submit(questionnaireId, playerId, answers);
      setResult(attempt);
    } catch (cause) {
      setSubmitError(cause.message || 'Could not submit your answers.');
      // A rejected late submission changes what the page should show.
      load();
    } finally {
      setSubmitting(false);
    }
  }

  if (!ready || !player) return null;

  const backLink = (
    <Link
      href="/questionnaires"
      className="font-sans text-sm text-[#00236f] underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#00236f]"
    >
      Back to all questionnaires
    </Link>
  );

  if (loading && !detail) {
    return (
      <div className="max-w-2xl mx-auto">
        <p className="font-sans text-sm text-[#757682]" role="status">
          Loading questionnaire…
        </p>
      </div>
    );
  }

  if (loadError && !detail) {
    return (
      <div className="max-w-2xl mx-auto flex flex-col gap-3 items-start">
        <p role="alert" className="font-sans text-sm text-[#b3261e]">
          {loadError}
        </p>
        <Button variant="ghost" onClick={load}>
          Retry
        </Button>
        {backLink}
      </div>
    );
  }

  if (!detail) return null;

  const attempt = result || detail.attempt;
  const closedMissed = !attempt && detail.status === 'closed_missed';

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-4">
      <div>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">{detail.title}</h1>
        {detail.description && <p className="font-sans text-sm text-[#757682] mt-1">{detail.description}</p>}
        <p className="font-sans text-sm text-[#131b2e] mt-2">
          Deadline: <strong>{formatDeadline(detail.due_at)}</strong>
          {!attempt && !closedMissed && <span> ({countdownText(detail.due_at, nowMs)})</span>}
        </p>
      </div>

      {attempt && <ResultView attempt={attempt} />}

      {closedMissed && (
        <div role="alert" className="font-sans text-sm text-[#b3261e] border border-[#f5c6c2] bg-[#fce8e6] rounded-lg p-3">
          This questionnaire closed on {formatDeadline(detail.due_at)} and you did not submit it, so it can no longer be
          taken. Please contact your trainer if you think this is a mistake.
        </div>
      )}

      {!attempt && !closedMissed && (
        <form onSubmit={handleSubmit} className="flex flex-col gap-4" noValidate>
          {detail.questions.map((question) => (
            <fieldset key={question.question_id} className="border border-[#c5c5d3]/60 rounded-lg p-3 bg-white">
              <legend className="font-sans text-sm font-semibold text-[#131b2e] px-1">
                Question {question.position + 1}: {question.prompt}
              </legend>
              <div className="flex flex-col gap-2 mt-2">
                {question.options.map((option, optionIndex) => {
                  const inputId = `q-${question.question_id}-${optionIndex}`;
                  return (
                    <label key={optionIndex} htmlFor={inputId} className="flex items-center gap-2 font-sans text-sm text-[#131b2e]">
                      <input
                        id={inputId}
                        type="radio"
                        name={`question-${question.question_id}`}
                        checked={answers[question.question_id] === optionIndex}
                        onChange={() => setAnswers((current) => ({ ...current, [question.question_id]: optionIndex }))}
                      />
                      {option}
                    </label>
                  );
                })}
              </div>
            </fieldset>
          ))}
          {submitError && (
            <p role="alert" className="font-sans text-sm text-[#b3261e]">
              {submitError}
            </p>
          )}
          <p className="font-sans text-xs text-[#757682]">
            You can submit only once. A submission is accepted until the deadline above, by the server&apos;s clock.
          </p>
          <Button type="submit" disabled={submitting} className="self-start">
            {submitting ? 'Submitting…' : 'Submit answers'}
          </Button>
        </form>
      )}

      {backLink}
    </div>
  );
}
