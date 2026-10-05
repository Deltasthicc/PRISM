import { describe, expect, it, vi } from 'vitest';
import { invalidateLearnerData } from '@/lib/invalidateLearnerData';

describe('invalidateLearnerData', () => {
  it('invalidates every profile-derived cache for that learner', async () => {
    const invalidateQueries = vi.fn(async () => {});
    await invalidateLearnerData({ invalidateQueries }, 'p-1');

    const keys = invalidateQueries.mock.calls.map(([options]) => options.queryKey);
    expect(keys).toEqual([
      ['learning-profile', 'p-1'],
      ['academy', 'p-1'],
      ['pathway', 'p-1'],
      ['dashboard', 'p-1'],
    ]);
  });

  it('does nothing without a player id', async () => {
    const invalidateQueries = vi.fn();
    await invalidateLearnerData({ invalidateQueries }, undefined);
    expect(invalidateQueries).not.toHaveBeenCalled();
  });
});
