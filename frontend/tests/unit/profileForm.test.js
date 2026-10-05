import { describe, expect, it } from 'vitest';
import { cleanStructured, parseTags, structuredProblem, tagsToText } from '@/lib/profileForm';

describe('parseTags', () => {
  it('trims, drops blanks and collapses case-insensitive duplicates', () => {
    expect(parseTags(' Python, python ,, GIS ')).toEqual(['Python', 'GIS']);
  });
  it('round-trips through tagsToText', () => {
    expect(parseTags(tagsToText(['A', 'B']))).toEqual(['A', 'B']);
  });
  it('handles empty input', () => {
    expect(parseTags('')).toEqual([]);
    expect(parseTags(undefined)).toEqual([]);
  });
});

describe('cleanStructured', () => {
  it('drops rows without their required field and converts years', () => {
    const cleaned = cleanStructured({
      qualifications: [{ degree: ' B.Sc ', institution: '', year: '2012' }, { degree: '  ', institution: 'x', year: '' }],
      work_experience: [{ title: 'Analyst', organization: 'IMD', start_year: '2015', end_year: '', description: '' }, { title: '' }],
      external_certificates: [{ name: 'GIS', issuer: '', year: '', credential_id: ' 1 ' }, { name: '' }],
      interests: ['a'],
      skills: ['b'],
    });
    expect(cleaned.qualifications).toEqual([{ degree: 'B.Sc', institution: '', year: 2012 }]);
    expect(cleaned.work_experience).toEqual([
      { title: 'Analyst', organization: 'IMD', start_year: 2015, end_year: null, description: '' },
    ]);
    expect(cleaned.external_certificates).toEqual([{ name: 'GIS', issuer: '', year: null, credential_id: '1' }]);
    expect(cleaned.interests).toEqual(['a']);
  });

  it('treats a non-numeric year as absent rather than sending NaN', () => {
    expect(cleanStructured({ qualifications: [{ degree: 'x', year: 'abc' }] }).qualifications[0].year).toBeNull();
  });
});

describe('structuredProblem', () => {
  it('flags an end year before the start year', () => {
    expect(structuredProblem({ work_experience: [{ title: 'T', start_year: '2020', end_year: '2010' }] })).toMatch(/end year/);
  });
  it('flags out-of-range years', () => {
    expect(structuredProblem({ qualifications: [{ degree: 'x', year: '1800' }] })).toMatch(/1950/);
  });
  it('accepts a valid profile', () => {
    expect(structuredProblem({ qualifications: [{ degree: 'x', year: '2010' }], work_experience: [] })).toBe('');
  });
});
