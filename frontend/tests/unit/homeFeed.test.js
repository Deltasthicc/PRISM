import { describe, expect, it } from 'vitest';
import { formatFeedDate, isFeedEmpty, localInputToIso, STATUS_LABELS } from '@/lib/homeFeed';

describe('isFeedEmpty', () => {
  it('is empty for a missing feed and for three empty sections', () => {
    expect(isFeedEmpty(null)).toBe(true);
    expect(isFeedEmpty({ announcements: [], new_courses: [], my_achievements: [] })).toBe(true);
  });

  it('is not empty when any section has an item', () => {
    expect(isFeedEmpty({ announcements: [], new_courses: [{ course_id: 'c' }], my_achievements: [] })).toBe(false);
    expect(isFeedEmpty({ announcements: [], new_courses: [], my_achievements: [{ certificate_id: 'x' }] })).toBe(false);
  });
});

describe('formatFeedDate', () => {
  it('returns an empty string for missing or invalid input', () => {
    expect(formatFeedDate(null)).toBe('');
    expect(formatFeedDate('not-a-date')).toBe('');
  });

  it('formats a valid ISO date', () => {
    expect(formatFeedDate('2026-10-05T12:00:00+00:00')).toMatch(/2026/);
  });
});

describe('localInputToIso', () => {
  it('returns null for empty or invalid values and ISO otherwise', () => {
    expect(localInputToIso('')).toBeNull();
    expect(localInputToIso('garbage')).toBeNull();
    expect(localInputToIso('2026-10-05T12:00')).toMatch(/^\d{4}-\d{2}-\d{2}T/);
  });
});

describe('STATUS_LABELS', () => {
  it('states visibility in words for every status', () => {
    for (const status of ['draft', 'published', 'unpublished', 'expired']) {
      expect(STATUS_LABELS[status]).toMatch(/visible|hidden/);
    }
  });
});
