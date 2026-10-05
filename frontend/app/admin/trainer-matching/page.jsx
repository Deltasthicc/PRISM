'use client';

import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { UserSearch } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { learning } from '@/lib/api/client';
import {
  EVIDENCE_LEVEL_LABELS,
  EVIDENCE_LEVEL_TONES,
  competencyOptions,
  trainerExpertiseApi,
} from '@/lib/api/trainerExpertise';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';

const SELECT_CLASS =
  'bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 ' +
  'outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]';

function formatRaw(value) {
  if (value === null || value === undefined) return 'n/a';
  return String(value);
}

function ScoreBreakdown({ components }) {
  if (!components?.length) return null;
  return (
    <div className="overflow-x-auto mt-3">
      <table className="w-full text-left font-sans text-xs">
        <caption className="sr-only">Score breakdown by component</caption>
        <thead>
          <tr className="text-[#757682]">
            <th scope="col" className="py-1 pr-3 font-semibold">Component</th>
            <th scope="col" className="py-1 pr-3 font-semibold">Value</th>
            <th scope="col" className="py-1 pr-3 font-semibold">Weight</th>
            <th scope="col" className="py-1 font-semibold">Points</th>
          </tr>
        </thead>
        <tbody>
          {components.map((component) => (
            <tr key={component.key} className="border-t border-[#c5c5d3]/30 align-top">
              <td className="py-1 pr-3 text-[#131b2e]">
                {component.label}
                <span className="block text-[10px] text-[#8a8f9d]">{component.note}</span>
              </td>
              <td className="py-1 pr-3 text-[#444651]">{formatRaw(component.raw_value)}</td>
              <td className="py-1 pr-3 text-[#444651]">{component.weight}</td>
              <td className="py-1 text-[#131b2e]">
                {component.available ? component.points : '0 (not available)'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function TrainerRow({ trainer }) {
  const noEvidence = trainer.evidence_level === 'NO_EVIDENCE';
  const name = trainer.full_name || trainer.username || trainer.trainer_id;
  return (
    <Panel>
      <div className="flex items-start justify-between gap-3 flex-wrap">
        <div>
          <h3 className="font-sans text-sm font-bold text-[#131b2e]">
            {trainer.rank ? `#${trainer.rank} · ` : ''}
            {name}
          </h3>
          <p className="font-mono text-[10px] text-[#8a8f9d]">
            {trainer.username} · {trainer.trainer_id}
          </p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <Badge tone={EVIDENCE_LEVEL_TONES[trainer.evidence_level] || 'default'}>
            {EVIDENCE_LEVEL_LABELS[trainer.evidence_level] || trainer.evidence_level}
          </Badge>
          <span className="font-sans text-sm font-bold text-[#00236f]">
            {noEvidence ? 'Score: none (no evidence)' : `Score: ${trainer.score} / 100`}
          </span>
        </div>
      </div>

      <ScoreBreakdown components={trainer.components} />

      <ul className="list-disc pl-5 mt-3 flex flex-col gap-1">
        {trainer.rationale.map((line, index) => (
          <li key={index} className="font-sans text-xs text-[#444651]">
            {line}
          </li>
        ))}
      </ul>
    </Panel>
  );
}

// Admin trainer-to-subject matching (backend/routes/trainer_expertise.py,
// GET /learning/trainers/match). Not role-gated in the UI yet --
// TRAINER_MATCH_READ is enforced server-side (403 for anyone without
// organization_admin), the same known gap as the other admin pages.
export default function AdminTrainerMatchingPage() {
  const { ready } = useRequireAuth();
  const [competencyId, setCompetencyId] = useState('');

  const curriculaQuery = useQuery({
    queryKey: ['curricula', 'en'],
    queryFn: () => learning.getCurricula('en'),
    staleTime: 10 * 60 * 1000,
    enabled: ready,
  });
  const options = useMemo(() => competencyOptions(curriculaQuery.data?.curricula), [curriculaQuery.data]);

  const matchQuery = useQuery({
    queryKey: ['trainer-match', competencyId],
    queryFn: () => trainerExpertiseApi.match(competencyId),
    enabled: ready && !!competencyId,
  });
  const result = matchQuery.data;

  if (!ready) return null;

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1 flex items-center gap-1.5">
          <UserSearch size={12} aria-hidden="true" />
          Admin
        </p>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">Trainer matching</h1>
        <p className="font-sans text-sm text-[#757682] mt-1">
          Find which trainers are suitable to teach a subject, ranked from stored facts only. No AI is
          involved and every score is broken down below.
        </p>
      </div>

      <Panel variant="accent" role="note">
        <p className="font-sans text-xs text-[#444651]">
          <strong>Declared levels are self-declared and unverified.</strong>{' '}
          {result?.notice ||
            'They are combined with real teaching activity: published courses, learners who completed them, and ratings.'}{' '}
          A trainer with no declared expertise and no published course for the subject is shown as
          NO EVIDENCE, which is not the same as a low score.
        </p>
      </Panel>

      <Panel>
        {curriculaQuery.isLoading && <p className="font-sans text-sm text-[#757682]">Loading competencies…</p>}
        {curriculaQuery.isError && (
          <div role="alert" className="flex items-center gap-3">
            <p className="font-sans text-sm text-[#b3261e]">Could not load the competency list.</p>
            <Button variant="ghost" onClick={() => curriculaQuery.refetch()}>
              Retry
            </Button>
          </div>
        )}
        {curriculaQuery.isSuccess && (
          <div className="flex flex-col gap-1.5">
            <label htmlFor="match-competency" className="font-sans text-xs font-semibold text-[#444651]">
              Subject (competency)
            </label>
            <select
              id="match-competency"
              className={SELECT_CLASS}
              value={competencyId}
              onChange={(e) => setCompetencyId(e.target.value)}
            >
              <option value="">Select a competency…</option>
              {options.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label} ({option.curriculum})
                </option>
              ))}
            </select>
          </div>
        )}
      </Panel>

      {!competencyId && curriculaQuery.isSuccess && (
        <p className="font-sans text-sm text-[#757682] text-center">Choose a subject to see ranked trainers.</p>
      )}
      {competencyId && matchQuery.isLoading && (
        <p className="font-sans text-sm text-[#757682] text-center">Ranking trainers…</p>
      )}
      {competencyId && matchQuery.isError && (
        <div role="alert" className="flex items-center gap-3">
          <p className="font-sans text-sm text-[#b3261e]">
            {matchQuery.error?.message || 'Could not rank trainers.'}
          </p>
          <Button variant="ghost" onClick={() => matchQuery.refetch()}>
            Retry
          </Button>
        </div>
      )}

      {result && (
        <section aria-labelledby="match-results-heading" className="flex flex-col gap-3">
          <div>
            <h2 id="match-results-heading" className="font-sans text-sm font-bold text-[#131b2e]">
              {result.competency_label}
            </h2>
            <p className="font-mono text-[10px] text-[#8a8f9d]">
              policy {result.policy_version} · max {result.max_points} points · declared claims alone cap at{' '}
              {result.declared_max_points} · mean rating shown only with {result.min_ratings_for_mean}+ ratings
            </p>
          </div>
          {result.trainers.length === 0 && (
            <p className="font-sans text-sm text-[#757682]">
              No trainers on record yet. A trainer appears once they declare expertise or author a course.
            </p>
          )}
          {result.trainers.map((trainer) => (
            <TrainerRow key={trainer.trainer_id} trainer={trainer} />
          ))}
        </section>
      )}
    </div>
  );
}
