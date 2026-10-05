import { describe, expect, it } from 'vitest';
import { formatDeadline } from '@/lib/questionnaireForm';

describe('formatDeadline', () => {
  it('formats an ISO instant without throwing and names the zone', () => {
    const text = formatDeadline('2026-10-07T09:30:00Z');
    expect(text).toMatch(/2026/);
    expect(text).toMatch(/[A-Za-z]{2,}|GMT|UTC|[+-]\d/); // a zone label is present
  });

  it('returns an empty string for missing or invalid input', () => {
    expect(formatDeadline('')).toBe('');
    expect(formatDeadline(null)).toBe('');
    expect(formatDeadline('not a date')).toBe('');
  });
});
