'use client';

import { Suspense, useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { ArrowLeft, ArrowRight, BadgeCheck, BookOpen, CheckCircle2, XCircle } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { learning } from '@/lib/api/client';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';

const QUESTION_COUNT = 5;

// A plain, professional-shell practice quiz for exactly one competency --
// reached from a Prerequisite Pathways room (/dungeon's "Practice this
// competency" button). Deliberately not routed through /combat: this page
// has no enemies, health bars, damage, or dungeon framing, matching every
// other page on the always-visible professional path (/dungeon, /stats,
// /academy). Game-skinned practice can be layered back on top of this same
// backend endpoint later as a separate, opt-in Quest Mode experience --
// this route is the plain pipeline underneath it.
function PracticeCompetency() {
  const { ready } = useRequireAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const player = useAuthStore((s) => s.player);

  const competencyId = searchParams.get('competency_id');
  const label = searchParams.get('label') || competencyId;

  const [attempt, setAttempt] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [result, setResult] = useState(null);
  const [reviewIndex, setReviewIndex] = useState(null);

  // Per-question elapsed time, keyed by item_id -- sent as time_taken_ms so
  // the backend's scoring can use it as a secondary, accuracy-never-
  // overriding confidence signal (services/quiz_scoring.py).
  const timeSpentRef = useRef({});
  const questionStartRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    if (!ready || !competencyId) {
      setLoading(false);
      return undefined;
    }
    async function load() {
      setLoading(true);
      setLoadError('');
      try {
        const data = await learning.getPracticeQuestions(competencyId, QUESTION_COUNT);
        if (!cancelled) setAttempt(data);
      } catch (cause) {
        if (!cancelled) setLoadError(cause.message || 'Could not load practice questions.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [ready, competencyId]);

  const questions = attempt?.questions || [];
  const current = questions[index];

  useEffect(() => {
    if (result || !questions.length) return;
    questionStartRef.current = Date.now();
    // Only the active question index should reset the per-question timer.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index, questions.length, result]);

  function recordElapsed() {
    if (!current || questionStartRef.current == null) return;
    const delta = Date.now() - questionStartRef.current;
    timeSpentRef.current[current.item_id] = (timeSpentRef.current[current.item_id] || 0) + delta;
    questionStartRef.current = Date.now();
  }

  const answeredCount = Object.keys(answers).length;

  function selectOption(optionIndex) {
    if (result || !current) return;
    setAnswers((prev) => ({ ...prev, [current.item_id]: optionIndex }));
  }

  function setTextAnswer(text) {
    if (result || !current) return;
    setAnswers((prev) => {
      const next = { ...prev };
      if (text.trim()) next[current.item_id] = text;
      else delete next[current.item_id];
      return next;
    });
  }

  function goNext() {
    recordElapsed();
    setIndex((i) => Math.min(i + 1, questions.length - 1));
  }

  function goPrev() {
    recordElapsed();
    setIndex((i) => Math.max(i - 1, 0));
  }

  async function handleSubmit() {
    if (answeredCount !== questions.length) {
      setSubmitError('Answer every question before submitting.');
      return;
    }
    recordElapsed();
    setSubmitting(true);
    setSubmitError('');
    try {
      const payloadAnswers = questions.map((q) => {
        const timeTakenMs = timeSpentRef.current[q.item_id] || null;
        return q.question_type === 'fill_in_blank'
          ? { item_id: q.item_id, answer_text: answers[q.item_id], time_taken_ms: timeTakenMs }
          : { item_id: q.item_id, selected_index: answers[q.item_id], time_taken_ms: timeTakenMs };
      });
      const response = await learning.submitCompetencyQuiz(
        attempt.attempt_id,
        attempt.topic_id,
        payloadAnswers,
        player?.player_id
      );
      setResult(response);
    } catch (cause) {
      setSubmitError(cause.message || 'This attempt could not be graded. Please retry.');
    } finally {
      setSubmitting(false);
    }
  }

  function handlePracticeAgain() {
    setAttempt(null);
    setAnswers({});
    setResult(null);
    setReviewIndex(null);
    setIndex(0);
    timeSpentRef.current = {};
    setLoading(true);
    learning
      .getPracticeQuestions(competencyId, QUESTION_COUNT)
      .then(setAttempt)
      .catch((cause) => setLoadError(cause.message || 'Could not load practice questions.'))
      .finally(() => setLoading(false));
  }

  if (!competencyId) {
    return (
      <div className="max-w-2xl mx-auto mt-10 flex flex-col items-center gap-3">
        <p className="font-sans text-sm text-[#b3261e] text-center">
          No competency was specified to practice.
        </p>
        <Button variant="ghost" onClick={() => router.push('/dungeon')}>
          Back to Prerequisite Pathways
        </Button>
      </div>
    );
  }

  if (!ready || loading) {
    return <p className="font-sans text-sm text-[#757682] text-center mt-10">Loading practice questions…</p>;
  }

  if (loadError || questions.length === 0) {
    return (
      <div className="max-w-2xl mx-auto mt-10 flex flex-col items-center gap-3">
        <p className="font-sans text-sm text-[#b3261e] text-center">
          {loadError || 'No questions are available yet for this competency.'}
        </p>
        <Button variant="ghost" onClick={() => router.push('/dungeon')}>
          Back to Prerequisite Pathways
        </Button>
      </div>
    );
  }

  // ============================================================
  // RESULTS
  // ============================================================
  if (result) {
    if (reviewIndex !== null) {
      const q = questions[reviewIndex];
      const graded = result.graded_answers.find((g) => g.item_id === q.item_id);
      const isCorrect = Boolean(graded?.correct);
      const isFillInBlank = q.question_type === 'fill_in_blank';
      const submittedValue = isFillInBlank ? graded?.submitted_text : graded?.selected_index;

      return (
        <div className="max-w-3xl mx-auto flex flex-col gap-4">
          <Panel>
            <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
              <span className="font-sans text-xs font-semibold text-[#757682]">
                Question {reviewIndex + 1} of {questions.length}
              </span>
              <Badge tone={isCorrect ? 'success' : 'danger'}>
                {isCorrect ? 'Correct' : 'Incorrect'}
              </Badge>
            </div>
            <h2 className="font-sans text-sm font-semibold text-[#131b2e] mb-4">{q.question}</h2>

            {isFillInBlank ? (
              <div className="flex flex-col gap-2">
                <div className="p-3 rounded-lg border border-[#c5c5d3]/40 bg-[#f7f7fb]">
                  <span className="font-mono text-[10px] text-[#757682] block mb-1">Your answer</span>
                  <span className="font-sans text-sm text-[#131b2e]">{submittedValue || '(skipped)'}</span>
                </div>
                {!isCorrect && (
                  <div className="p-3 rounded-lg border border-[#b7e1c4]/60 bg-[#e6f4ea]">
                    <span className="font-mono text-[10px] text-[#757682] block mb-1">Accepted answer</span>
                    <span className="font-sans text-sm font-semibold text-[#1a7f4b]">
                      {graded?.correct_answer_display}
                    </span>
                  </div>
                )}
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {q.options.map((optionText, optionIndex) => {
                  const wasSelected = submittedValue === optionIndex;
                  const isCorrectOption = graded?.correct_index === optionIndex;
                  return (
                    <div
                      key={optionIndex}
                      className={
                        'flex items-center gap-3 p-3 rounded-lg border font-sans text-sm ' +
                        (isCorrectOption
                          ? 'bg-[#e6f4ea] border-[#b7e1c4]/60 text-[#1a7f4b]'
                          : wasSelected
                            ? 'bg-[#fce8e6] border-[#f5c6c2]/60 text-[#b3261e]'
                            : 'bg-white border-[#c5c5d3]/40 text-[#131b2e]')
                      }
                    >
                      <span className="font-mono text-xs font-bold shrink-0">
                        {String.fromCharCode(65 + optionIndex)}
                      </span>
                      <span className="flex-1">{optionText}</span>
                      {isCorrectOption && <CheckCircle2 size={16} className="shrink-0" />}
                      {wasSelected && !isCorrectOption && <XCircle size={16} className="shrink-0" />}
                    </div>
                  );
                })}
              </div>
            )}

            <div className="mt-4 p-3 rounded-lg bg-[#f7f7fb] border border-[#c5c5d3]/40">
              <p className="font-mono text-[10px] font-bold uppercase text-[#757682] mb-1">Explanation</p>
              <p className="font-sans text-sm text-[#333a49]">{graded?.explanation}</p>
              <p className="font-mono text-[10px] text-[#8a8f9d] mt-2">
                Source: {graded?.doc_id}
                {graded?.locator ? ` — ${graded.locator}` : ''}
              </p>
            </div>

            <div className="flex items-center justify-between gap-3 mt-4 pt-3 border-t border-[#c5c5d3]/30">
              <Button
                variant="ghost"
                disabled={reviewIndex === 0}
                onClick={() => setReviewIndex(Math.max(0, reviewIndex - 1))}
              >
                <ArrowLeft size={14} className="inline mr-1" />
                Previous
              </Button>
              <Button variant="ghost" onClick={() => setReviewIndex(null)}>
                Back to results
              </Button>
              {reviewIndex < questions.length - 1 ? (
                <Button onClick={() => setReviewIndex(reviewIndex + 1)}>
                  Next
                  <ArrowRight size={14} className="inline ml-1" />
                </Button>
              ) : (
                <span className="w-[88px]" />
              )}
            </div>
          </Panel>
        </div>
      );
    }

    return (
      <div className="max-w-3xl mx-auto flex flex-col gap-4">
        <Panel>
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div>
              <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1">
                Practice complete
              </p>
              <h1 className="font-sans text-lg font-bold text-[#00236f]">{label}</h1>
            </div>
            <div className="flex items-center gap-2 bg-[#f7f7fb] px-4 py-2.5 rounded-lg border border-[#c5c5d3]/40">
              <div className="text-right font-mono">
                <div className="text-[9px] uppercase text-[#8a8f9d] font-bold">Score</div>
                <div className="text-base font-bold text-[#00236f]">
                  {result.correct} / {result.total}
                </div>
              </div>
              <div className="w-12 h-12 rounded-lg bg-[#00236f] text-white font-mono font-bold text-sm flex items-center justify-center">
                {result.score_percentage}%
              </div>
            </div>
          </div>
        </Panel>

        <Panel>
          <h2 className="font-sans text-sm font-bold text-[#131b2e] mb-3">Question review</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            {questions.map((q, i) => {
              const graded = result.graded_answers.find((g) => g.item_id === q.item_id);
              const isCorrect = Boolean(graded?.correct);
              return (
                <button
                  key={q.item_id}
                  onClick={() => setReviewIndex(i)}
                  className={
                    'text-left p-3 rounded-lg border font-sans text-xs flex items-center justify-between gap-2 ' +
                    (isCorrect
                      ? 'bg-[#e6f4ea] border-[#b7e1c4]/60 hover:bg-[#dcf0e2]'
                      : 'bg-[#fce8e6] border-[#f5c6c2]/60 hover:bg-[#f9dcda]')
                  }
                >
                  <span className="font-semibold text-[#131b2e]">Q{i + 1}</span>
                  <Badge tone={isCorrect ? 'success' : 'danger'}>{isCorrect ? 'Correct' : 'Review'}</Badge>
                </button>
              );
            })}
          </div>
        </Panel>

        {result.competency_scores?.length > 0 && (
          <Panel>
            <h2 className="font-sans text-sm font-bold text-[#131b2e] mb-2">Updated evidence</h2>
            {result.competency_scores.map((score) => (
              <p key={score.competency_id} className="font-sans text-sm text-[#757682]">
                Provisional level: <strong className="text-[#131b2e]">{score.provisional_level} / 5</strong>{' '}
                ({score.confidence} confidence, {score.correct}/{score.total} correct this attempt)
              </p>
            ))}
          </Panel>
        )}

        <div className="flex flex-wrap gap-3">
          <Button variant="ghost" onClick={handlePracticeAgain}>
            Practice again
          </Button>
          <Button onClick={() => router.push('/dungeon')}>
            <BadgeCheck size={16} className="inline mr-1.5" />
            Back to Prerequisite Pathways
          </Button>
        </div>
      </div>
    );
  }

  // ============================================================
  // LIVE QUIZ
  // ============================================================
  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1">
            Practice
          </p>
          <h1 className="font-sans text-lg font-bold text-[#00236f]">{label}</h1>
        </div>
        <Badge tone="accent">
          {answeredCount}/{questions.length} answered
        </Badge>
      </div>

      <Panel>
        <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
          <span className="font-sans text-xs font-semibold text-[#757682]">
            Question {index + 1} of {questions.length}
          </span>
          <Badge tone="default">{current.difficulty}</Badge>
        </div>

        <h2 className="font-sans text-sm font-semibold text-[#131b2e] mb-2">{current.question}</h2>
        <p className="flex items-center gap-1.5 font-mono text-[10px] text-[#8a8f9d] mb-4">
          <BookOpen size={12} />
          Source: {current.doc_id}
          {current.locator ? ` — ${current.locator}` : ''}
        </p>

        {current.question_type === 'fill_in_blank' ? (
          <input
            type="text"
            autoComplete="off"
            value={answers[current.item_id] || ''}
            onChange={(e) => setTextAnswer(e.target.value)}
            placeholder="Type the missing word or phrase…"
            className="w-full px-3.5 py-2.5 rounded-lg border border-[#c5c5d3]/60 font-sans text-sm outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]"
          />
        ) : (
          <div className="flex flex-col gap-2" role="radiogroup" aria-label={`Question ${index + 1} answer options`}>
            {current.options.map((optionText, optionIndex) => {
              const isSelected = answers[current.item_id] === optionIndex;
              return (
                <button
                  key={optionIndex}
                  type="button"
                  role="radio"
                  aria-checked={isSelected}
                  onClick={() => selectOption(optionIndex)}
                  className={
                    'text-left flex items-center gap-3 p-3 rounded-lg border font-sans text-sm transition-colors ' +
                    (isSelected
                      ? 'bg-[#f2f3ff] border-[#00236f]/60 text-[#00236f] font-semibold'
                      : 'bg-white border-[#c5c5d3]/40 text-[#131b2e] hover:border-[#00236f]/30')
                  }
                >
                  <span
                    className={
                      'w-6 h-6 rounded-md flex items-center justify-center shrink-0 font-mono text-[11px] font-bold ' +
                      (isSelected ? 'bg-[#00236f] text-white' : 'bg-[#f7f7fb] text-[#757682] border border-[#c5c5d3]/50')
                    }
                  >
                    {String.fromCharCode(65 + optionIndex)}
                  </span>
                  <span>{optionText}</span>
                </button>
              );
            })}
          </div>
        )}

        <div className="flex items-center justify-between gap-3 mt-5 pt-4 border-t border-[#c5c5d3]/30">
          <Button variant="ghost" disabled={index === 0} onClick={goPrev}>
            <ArrowLeft size={14} className="inline mr-1" />
            Previous
          </Button>
          {index < questions.length - 1 ? (
            <Button onClick={goNext}>
              Next
              <ArrowRight size={14} className="inline ml-1" />
            </Button>
          ) : (
            <Button onClick={handleSubmit} disabled={submitting || answeredCount !== questions.length}>
              {submitting ? 'Grading…' : 'Submit'}
            </Button>
          )}
        </div>
        {submitError && <p className="mt-3 font-sans text-xs text-[#b3261e]">{submitError}</p>}
      </Panel>
    </div>
  );
}

export default function PracticeCompetencyPage() {
  return (
    <Suspense fallback={null}>
      <PracticeCompetency />
    </Suspense>
  );
}
