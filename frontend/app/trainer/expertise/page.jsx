'use client';

import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BadgeCheck } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { learning } from '@/lib/api/client';
import { EXPERTISE_BASES, competencyOptions, trainerExpertiseApi } from '@/lib/api/trainerExpertise';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';

const SELECT_CLASS =
  'bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 ' +
  'outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]';

const LEVELS = [
  { value: 1, label: '1 - Introductory' },
  { value: 2, label: '2 - Developing' },
  { value: 3, label: '3 - Proficient' },
  { value: 4, label: '4 - Advanced' },
  { value: 5, label: '5 - Expert' },
];

const EMPTY_FORM = { competencyId: '', declaredLevel: '3', basis: 'experience', basisDetail: '', yearsTeaching: '0' };

// Trainer's own declared-expertise editor (backend/routes/trainer_expertise.py).
// Everything entered here is a self-declaration: the server stores it as
// unverified and the admin matching view labels it that way. Not role-gated
// in the UI -- TRAINER_EXPERTISE_MANAGE is enforced server-side (403 for a
// learner-only account), the same known gap as the other trainer pages.
export default function TrainerExpertisePage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);
  const playerId = player?.player_id;
  const queryClient = useQueryClient();

  const [form, setForm] = useState(EMPTY_FORM);
  const [formError, setFormError] = useState('');
  const [rowError, setRowError] = useState('');

  const curriculaQuery = useQuery({
    queryKey: ['curricula', 'en'],
    queryFn: () => learning.getCurricula('en'),
    staleTime: 10 * 60 * 1000,
    enabled: ready,
  });
  const options = useMemo(() => competencyOptions(curriculaQuery.data?.curricula), [curriculaQuery.data]);

  const expertiseQuery = useQuery({
    queryKey: ['trainer-expertise', playerId],
    queryFn: () => trainerExpertiseApi.list(playerId),
    enabled: ready && !!playerId,
  });
  const rows = expertiseQuery.data?.expertise || [];

  const saveMutation = useMutation({
    mutationFn: (values) =>
      trainerExpertiseApi.upsert(playerId, values.competencyId, {
        declaredLevel: Number(values.declaredLevel),
        basis: values.basis,
        basisDetail: values.basisDetail.trim(),
        yearsTeaching: Number(values.yearsTeaching),
      }),
    onSuccess: () => {
      setFormError('');
      setForm(EMPTY_FORM);
      queryClient.invalidateQueries({ queryKey: ['trainer-expertise', playerId] });
    },
    onError: (cause) => setFormError(cause.message || 'Could not save your expertise.'),
  });

  const removeMutation = useMutation({
    mutationFn: (competencyId) => trainerExpertiseApi.remove(playerId, competencyId),
    onSuccess: () => {
      setRowError('');
      queryClient.invalidateQueries({ queryKey: ['trainer-expertise', playerId] });
    },
    onError: (cause) => setRowError(cause.message || 'Could not remove that entry.'),
  });

  function handleSubmit(event) {
    event.preventDefault();
    if (!form.competencyId) {
      setFormError('Choose a competency.');
      return;
    }
    const years = Number(form.yearsTeaching);
    if (!Number.isInteger(years) || years < 0 || years > 80) {
      setFormError('Years teaching must be a whole number between 0 and 80.');
      return;
    }
    setFormError('');
    saveMutation.mutate(form);
  }

  function editRow(row) {
    setFormError('');
    setForm({
      competencyId: row.competency_id,
      declaredLevel: String(row.declared_level),
      basis: row.basis,
      basisDetail: row.basis_detail || '',
      yearsTeaching: String(row.years_teaching),
    });
  }

  if (!ready) return null;

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1 flex items-center gap-1.5">
          <BadgeCheck size={12} aria-hidden="true" />
          Trainer
        </p>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">My teaching expertise</h1>
        <p className="font-sans text-sm text-[#757682] mt-1">
          Declare the competencies you can teach. Administrators use this, together with your real
          teaching activity, to find suitable trainers for a subject.
        </p>
      </div>

      <Panel variant="accent" role="note">
        <p className="font-sans text-xs text-[#444651]">
          <strong>Self-declared and unverified.</strong> Nothing you enter here is checked against a
          credential. It is shown to administrators labelled as self-declared, and it can only
          contribute part of a matching score on its own.
        </p>
      </Panel>

      <Panel>
        <h2 className="font-sans text-sm font-bold text-[#131b2e] mb-3">Add or update an entry</h2>
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
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <div className="flex flex-col gap-1.5">
              <label htmlFor="expertise-competency" className="font-sans text-xs font-semibold text-[#444651]">
                Competency
              </label>
              <select
                id="expertise-competency"
                className={SELECT_CLASS}
                value={form.competencyId}
                onChange={(e) => setForm({ ...form, competencyId: e.target.value })}
                required
              >
                <option value="">Select a competency…</option>
                {options.map((option) => (
                  <option key={option.id} value={option.id}>
                    {option.label} ({option.curriculum})
                  </option>
                ))}
              </select>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="flex flex-col gap-1.5">
                <label htmlFor="expertise-level" className="font-sans text-xs font-semibold text-[#444651]">
                  Teaching level (self-declared)
                </label>
                <select
                  id="expertise-level"
                  className={SELECT_CLASS}
                  value={form.declaredLevel}
                  onChange={(e) => setForm({ ...form, declaredLevel: e.target.value })}
                >
                  {LEVELS.map((level) => (
                    <option key={level.value} value={level.value}>
                      {level.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex flex-col gap-1.5">
                <label htmlFor="expertise-basis" className="font-sans text-xs font-semibold text-[#444651]">
                  Basis of this claim
                </label>
                <select
                  id="expertise-basis"
                  className={SELECT_CLASS}
                  value={form.basis}
                  onChange={(e) => setForm({ ...form, basis: e.target.value })}
                >
                  {EXPERTISE_BASES.map((basis) => (
                    <option key={basis.value} value={basis.value}>
                      {basis.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <Input
              id="expertise-detail"
              label="Basis detail (e.g. qualification name, max 500 characters)"
              value={form.basisDetail}
              maxLength={500}
              onChange={(e) => setForm({ ...form, basisDetail: e.target.value })}
            />
            <Input
              id="expertise-years"
              label="Years teaching this subject"
              type="number"
              min={0}
              max={80}
              step={1}
              value={form.yearsTeaching}
              onChange={(e) => setForm({ ...form, yearsTeaching: e.target.value })}
              required
            />

            {formError && (
              <p role="alert" className="font-sans text-xs text-[#b3261e]">
                {formError}
              </p>
            )}
            <Button type="submit" disabled={saveMutation.isPending} className="self-start">
              {saveMutation.isPending ? 'Saving…' : 'Save expertise'}
            </Button>
          </form>
        )}
      </Panel>

      <section aria-labelledby="declared-heading" className="flex flex-col gap-3">
        <h2 id="declared-heading" className="font-sans text-sm font-bold text-[#131b2e]">
          Your declared expertise
        </h2>
        {expertiseQuery.isLoading && <p className="font-sans text-sm text-[#757682]">Loading your entries…</p>}
        {expertiseQuery.isError && (
          <div role="alert" className="flex items-center gap-3">
            <p className="font-sans text-sm text-[#b3261e]">
              {expertiseQuery.error?.message || 'Could not load your entries.'}
            </p>
            <Button variant="ghost" onClick={() => expertiseQuery.refetch()}>
              Retry
            </Button>
          </div>
        )}
        {rowError && (
          <p role="alert" className="font-sans text-xs text-[#b3261e]">
            {rowError}
          </p>
        )}
        {expertiseQuery.isSuccess && rows.length === 0 && (
          <p className="font-sans text-sm text-[#757682]">
            You have not declared any expertise yet. Until you do (or publish a course), you will show
            as having no evidence for every subject.
          </p>
        )}
        {rows.map((row) => (
          <Panel key={row.expertise_id}>
            <div className="flex items-start justify-between gap-3 flex-wrap">
              <div>
                <h3 className="font-sans text-sm font-bold text-[#131b2e]">{row.competency_label}</h3>
                <p className="font-mono text-[10px] text-[#8a8f9d]">{row.competency_id}</p>
              </div>
              <Badge tone="warning">Self-declared · unverified</Badge>
            </div>
            <p className="font-sans text-xs text-[#444651] mt-2">
              Level {row.declared_level} of 5 · basis: {row.basis}
              {row.basis_detail ? ` (${row.basis_detail})` : ''} · {row.years_teaching} year
              {row.years_teaching === 1 ? '' : 's'} teaching
            </p>
            <div className="flex gap-3 mt-2">
              <button
                type="button"
                onClick={() => editRow(row)}
                className="font-sans text-xs text-[#00236f] underline"
              >
                Edit
              </button>
              <button
                type="button"
                disabled={removeMutation.isPending}
                onClick={() => removeMutation.mutate(row.competency_id)}
                className="font-sans text-xs text-[#b3261e] underline disabled:opacity-50"
              >
                Remove
              </button>
            </div>
          </Panel>
        ))}
      </section>
    </div>
  );
}
