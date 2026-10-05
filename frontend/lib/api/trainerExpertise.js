import { request } from './client';

// Trainer declared expertise and trainer-to-subject matching
// (backend/routes/trainer_expertise.py). Declared levels are self-declared
// and unverified; `match` returns a transparent, versioned ranking built from
// stored facts, with NO_EVIDENCE trainers listed last and never scored.
const base = (trainerId) => `/learning/trainers/${encodeURIComponent(trainerId)}`;

export const trainerExpertiseApi = {
  list: (trainerId) => request(`${base(trainerId)}/expertise`),
  profile: (trainerId) => request(`${base(trainerId)}/profile`),
  upsert: (trainerId, competencyId, { declaredLevel, basis, basisDetail, yearsTeaching }) =>
    request(`${base(trainerId)}/expertise/${encodeURIComponent(competencyId)}`, {
      method: 'PUT',
      body: {
        declared_level: declaredLevel,
        basis,
        basis_detail: basisDetail,
        years_teaching: yearsTeaching,
      },
    }),
  remove: (trainerId, competencyId) =>
    request(`${base(trainerId)}/expertise/${encodeURIComponent(competencyId)}`, { method: 'DELETE' }),
  match: (competencyId) =>
    request(`/learning/trainers/match?competency_id=${encodeURIComponent(competencyId)}`),
};

export const EXPERTISE_BASES = [
  { value: 'degree', label: 'Degree' },
  { value: 'certification', label: 'Certification' },
  { value: 'experience', label: 'Experience' },
  { value: 'other', label: 'Other' },
];

export const EVIDENCE_LEVEL_LABELS = {
  DECLARED_ONLY: 'Declared only (unverified)',
  DECLARED_AND_ACTIVITY: 'Declared + teaching activity',
  ACTIVITY_ONLY: 'Teaching activity only',
  NO_EVIDENCE: 'NO EVIDENCE',
};

export const EVIDENCE_LEVEL_TONES = {
  DECLARED_ONLY: 'warning',
  DECLARED_AND_ACTIVITY: 'success',
  ACTIVITY_ONLY: 'accent',
  NO_EVIDENCE: 'default',
};

// Flattens a getCurricula() response into a sorted, de-duplicated
// [{ id, label, curriculum }] picker list.
export function competencyOptions(curricula) {
  const seen = new Set();
  const options = [];
  for (const curriculum of curricula || []) {
    for (const competency of curriculum.competencies || []) {
      if (seen.has(competency.id)) continue;
      seen.add(competency.id);
      options.push({ id: competency.id, label: competency.label, curriculum: curriculum.name });
    }
  }
  return options.sort((a, b) => a.label.localeCompare(b.label) || a.id.localeCompare(b.id));
}
