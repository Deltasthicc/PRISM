import { beforeEach, describe, expect, it, vi } from 'vitest';

const request = vi.fn(async () => ({}));
vi.mock('@/lib/api/client', () => ({ request: (...args) => request(...args) }));

const { competencyOptions, trainerExpertiseApi, EVIDENCE_LEVEL_LABELS } = await import('@/lib/api/trainerExpertise');

describe('competencyOptions', () => {
  it('flattens curricula, de-duplicates by id and sorts by label', () => {
    const options = competencyOptions([
      { name: 'B', competencies: [{ id: 'z', label: 'Zeta' }, { id: 'a', label: 'Alpha' }] },
      { name: 'C', competencies: [{ id: 'a', label: 'Alpha' }, { id: 'm', label: 'Mu' }] },
    ]);
    expect(options.map((o) => o.id)).toEqual(['a', 'm', 'z']);
    expect(options[0].curriculum).toBe('B');
  });

  it('tolerates missing data', () => {
    expect(competencyOptions(undefined)).toEqual([]);
    expect(competencyOptions([{ name: 'x' }])).toEqual([]);
  });
});

describe('trainerExpertiseApi', () => {
  beforeEach(() => request.mockClear());

  it('encodes ids and maps the upsert body to snake_case', async () => {
    await trainerExpertiseApi.upsert('t 1', 'arrays', {
      declaredLevel: 4,
      basis: 'degree',
      basisDetail: 'MSc',
      yearsTeaching: 6,
    });
    expect(request).toHaveBeenCalledWith('/learning/trainers/t%201/expertise/arrays', {
      method: 'PUT',
      body: { declared_level: 4, basis: 'degree', basis_detail: 'MSc', years_teaching: 6 },
    });
  });

  it('calls the match endpoint with the competency in the query string', async () => {
    await trainerExpertiseApi.match('linked_lists');
    expect(request).toHaveBeenCalledWith('/learning/trainers/match?competency_id=linked_lists');
  });
});

describe('evidence level labels', () => {
  it('spells out NO EVIDENCE as text', () => {
    expect(EVIDENCE_LEVEL_LABELS.NO_EVIDENCE).toBe('NO EVIDENCE');
    expect(Object.keys(EVIDENCE_LEVEL_LABELS).sort()).toEqual(
      ['ACTIVITY_ONLY', 'DECLARED_AND_ACTIVITY', 'DECLARED_ONLY', 'NO_EVIDENCE']
    );
  });
});
