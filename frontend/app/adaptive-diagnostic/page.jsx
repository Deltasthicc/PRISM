'use client';

// A real two-stage adaptive diagnostic: a broad stage-1 quiz across a whole
// curriculum, then -- only when stage 1's wrong answers point at a real,
// tagged misconception (see backend/data/misconception_tags.json) -- a
// small stage-2 quiz built entirely from other real items tagged with that
// exact misconception. If no real signal exists, or no further real item
// carries that tag, this page says so plainly instead of faking a
// follow-up round.
//
// Not yet translated into the other 10 UI languages -- plain English, same
// honesty convention as this project's other documented pending items (see
// app/sampling-lab/page.jsx).

import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Brain, ArrowRight, CheckCircle2, XCircle, Target } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import { learning, adaptiveDiagnostic } from '@/lib/api/client';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';

function QuizRunner({ items, onSubmit, submitting, title }) {
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState({});

  const current = items[index];
  const selected = answers[current.item_id];

  function selectOption(optionIndex) {
    setAnswers((prev) => ({ ...prev, [current.item_id]: optionIndex }));
  }

  function next() {
    if (index < items.length - 1) {
      setIndex(index + 1);
    } else {
      onSubmit(
        items.map((item) => ({ item_id: item.item_id, selected_index: answers[item.item_id] }))
      );
    }
  }

  const allAnswered = Object.keys(answers).length === items.length;

  return (
    <Panel>
      <div className="flex items-center justify-between gap-2 mb-3">
        <h2 className="font-sans text-base font-bold text-[#00236f]">{title}</h2>
        <Badge tone="default">
          {index + 1} / {items.length}
        </Badge>
      </div>
      <p className="font-mono text-[10px] uppercase tracking-wide text-[#757682] mb-2">
        {current.competency_label}
      </p>
      <p className="font-sans text-sm text-[#131b2e] mb-4">{current.question}</p>
      <div className="flex flex-col gap-2">
        {current.options.map((option, optionIndex) => (
          <button
            key={option}
            type="button"
            onClick={() => selectOption(optionIndex)}
            className={`text-left font-sans text-sm px-4 py-3 rounded-lg border transition-colors ${
              selected === optionIndex
                ? 'border-[#00236f] bg-[#f2f3ff] text-[#00236f] font-medium'
                : 'border-[#c5c5d3]/60 text-[#131b2e] hover:border-[#00236f]/40'
            }`}
          >
            {String.fromCharCode(65 + optionIndex)}. {option}
          </button>
        ))}
      </div>
      <div className="flex justify-between items-center mt-4">
        <Button variant="ghost" disabled={index === 0} onClick={() => setIndex((i) => Math.max(0, i - 1))}>
          Back
        </Button>
        <Button
          onClick={next}
          disabled={selected == null || submitting || (index === items.length - 1 && !allAnswered)}
          className="flex items-center gap-1.5"
        >
          {index < items.length - 1 ? (
            <>
              Next <ArrowRight size={14} />
            </>
          ) : submitting ? (
            'Grading…'
          ) : (
            'Submit'
          )}
        </Button>
      </div>
    </Panel>
  );
}

function GradedList({ graded }) {
  return (
    <ol className="flex flex-col gap-3 mt-4">
      {graded.map((g, i) => (
        <li
          key={g.item_id}
          className={`rounded-lg border p-3 ${g.correct ? 'border-[#1a7f4b]/40 bg-[#e6f4ea]/40' : 'border-[#b3261e]/40 bg-[#fce8e6]/40'}`}
        >
          <div className="flex items-center gap-2 mb-1">
            {g.correct ? (
              <CheckCircle2 size={14} className="text-[#1a7f4b] shrink-0" />
            ) : (
              <XCircle size={14} className="text-[#b3261e] shrink-0" />
            )}
            <span className="font-mono text-[10px] uppercase text-[#757682]">Q{i + 1}</span>
            {g.misconception_label && (
              <Badge tone="warning">
                <Target size={10} className="inline mr-1 -mt-0.5" />
                {g.misconception_label}
              </Badge>
            )}
          </div>
          <p className="font-sans text-sm text-[#131b2e]">{g.explanation}</p>
        </li>
      ))}
    </ol>
  );
}

export default function AdaptiveDiagnosticPage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);
  const { language } = useLanguage();

  const [curriculumSlug, setCurriculumSlug] = useState('');
  const [session, setSession] = useState(null); // {session_id, items}
  const [stage1Result, setStage1Result] = useState(null);
  const [stage2Items, setStage2Items] = useState(null);
  const [stage2Result, setStage2Result] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const { data: curriculaData } = useQuery({
    queryKey: ['diagnostic-curricula', language],
    queryFn: () => learning.getCurricula(language),
    enabled: ready,
  });
  const curricula = curriculaData?.curricula || [];

  async function begin() {
    setError('');
    try {
      const result = await adaptiveDiagnostic.startStage1(player.player_id, curriculumSlug);
      setSession(result);
      setStage1Result(null);
      setStage2Items(null);
      setStage2Result(null);
    } catch (cause) {
      setError(cause.message || 'Could not start the diagnostic.');
    }
  }

  async function submitStage1(answers) {
    setSubmitting(true);
    setError('');
    try {
      const result = await adaptiveDiagnostic.submitStage1(session.session_id, player.player_id, answers);
      setStage1Result(result);
    } catch (cause) {
      setError(cause.message || 'Could not grade stage 1.');
    } finally {
      setSubmitting(false);
    }
  }

  async function beginStage2() {
    setError('');
    try {
      const result = await adaptiveDiagnostic.startStage2(session.session_id, player.player_id);
      setStage2Items(result.items);
    } catch (cause) {
      setError(cause.message || 'Could not start stage 2.');
    }
  }

  async function submitStage2(answers) {
    setSubmitting(true);
    setError('');
    try {
      const result = await adaptiveDiagnostic.submitStage2(session.session_id, player.player_id, answers);
      setStage2Result(result);
    } catch (cause) {
      setError(cause.message || 'Could not grade stage 2.');
    } finally {
      setSubmitting(false);
    }
  }

  if (!ready) return null;

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-4">
      <div>
        <div className="flex items-center gap-2">
          <Brain className="text-[#00236f]" size={20} aria-hidden="true" />
          <h1 className="font-sans text-lg font-bold text-[#00236f]">Adaptive Diagnostic</h1>
        </div>
        <p className="font-sans text-sm text-[#757682] mt-2 max-w-xl">
          A broad first round across a whole curriculum, then -- only when your wrong answers point
          at a real, specific misconception -- a short second round targeted exactly there. If
          there&apos;s no real pattern to target, this says so instead of guessing.
        </p>
      </div>

      {error && <p className="font-sans text-xs text-[#b3261e]">{error}</p>}

      {!session ? (
        <Panel>
          <label className="flex flex-col gap-1.5">
            <span className="font-sans text-xs font-semibold text-[#444651]">Curriculum</span>
            <select
              value={curriculumSlug}
              onChange={(e) => setCurriculumSlug(e.target.value)}
              className="bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 outline-none focus:border-[#00236f]"
            >
              <option value="">Choose a curriculum…</option>
              {curricula.map((c) => (
                <option key={c.slug} value={c.slug}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <Button className="mt-4" disabled={!curriculumSlug} onClick={begin}>
            Start stage 1
          </Button>
        </Panel>
      ) : stage2Result ? (
        <Panel>
          <h2 className="font-sans text-base font-bold text-[#131b2e] mb-2">Diagnostic complete</h2>
          <p className="font-sans text-sm text-[#757682] mb-1">
            Stage 1: {stage2Result.combined_summary.stage1_correct} / {stage2Result.combined_summary.stage1_total}{' '}
            correct
          </p>
          <p className="font-sans text-sm text-[#757682] mb-3">
            Stage 2 ({stage2Result.target_misconception}): {stage2Result.combined_summary.stage2_correct} /{' '}
            {stage2Result.combined_summary.stage2_total} correct
          </p>
          <GradedList graded={stage2Result.graded} />
        </Panel>
      ) : stage2Items ? (
        <QuizRunner items={stage2Items} onSubmit={submitStage2} submitting={submitting} title="Stage 2: targeted follow-up" />
      ) : stage1Result ? (
        <Panel>
          <h2 className="font-sans text-base font-bold text-[#131b2e] mb-2">Stage 1 results</h2>
          <p className="font-sans text-sm text-[#757682] mb-3">
            {stage1Result.correct} / {stage1Result.total} correct
          </p>
          <GradedList graded={stage1Result.graded} />

          <div className="mt-4 pt-4 border-t border-[#c5c5d3]/30">
            {stage1Result.misconception_signal ? (
              stage1Result.misconception_signal.stage2_available ? (
                <>
                  <p className="font-sans text-sm text-[#131b2e] mb-2">
                    Your wrong answers point at a real pattern:{' '}
                    <strong>{stage1Result.misconception_signal.label}</strong> (
                    {stage1Result.misconception_signal.wrong_answer_count} answer
                    {stage1Result.misconception_signal.wrong_answer_count === 1 ? '' : 's'}).
                  </p>
                  <Button onClick={beginStage2}>Start targeted stage 2</Button>
                </>
              ) : (
                <p className="font-sans text-sm text-[#757682]">
                  Your wrong answers point at <strong>{stage1Result.misconception_signal.label}</strong>, but
                  there&apos;s no further real item tagged with it yet -- honestly, not enough content exists yet
                  for a stage 2 here.
                </p>
              )
            ) : (
              <p className="font-sans text-sm text-[#757682]">
                No clear misconception pattern was found in your wrong answers (or you got everything
                right) -- there&apos;s nothing honest to target for a stage 2.
              </p>
            )}
          </div>
        </Panel>
      ) : (
        <QuizRunner items={session.items} onSubmit={submitStage1} submitting={submitting} title="Stage 1: broad diagnostic" />
      )}
    </div>
  );
}
