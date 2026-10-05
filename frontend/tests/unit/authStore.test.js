import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/lib/api/client', () => ({
  auth: {
    oidcStatus: vi.fn(),
    adoptOidcPlayer: vi.fn(),
    logout: vi.fn(async () => ({ ok: true })),
  },
}));

import { auth } from '@/lib/api/client';
import { useAuthStore } from '@/store/useAuthStore';

const PLAYER = { player_id: 'p-1', username: 'approved_user' };

beforeEach(() => {
  vi.clearAllMocks();
  useAuthStore.setState({ player: null, isAuthenticated: false, roles: [], error: null });
});

describe('resolveOidcSession', () => {
  it('binds the browser to the player for an approved account that holds a role', async () => {
    auth.oidcStatus.mockResolvedValue({ status: 'approved', player_id: 'p-1', roles: ['trainer'] });
    auth.adoptOidcPlayer.mockResolvedValue({ player: PLAYER });

    const status = await useAuthStore.getState().resolveOidcSession();

    expect(status.status).toBe('approved');
    expect(auth.adoptOidcPlayer).toHaveBeenCalledWith('p-1');
    const state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.player).toEqual(PLAYER);
    expect(state.roles).toEqual(['trainer']);
  });

  it('does not authenticate an approved account whose token carries no role', async () => {
    auth.oidcStatus.mockResolvedValue({ status: 'approved', player_id: 'p-1', roles: [] });

    await useAuthStore.getState().resolveOidcSession();

    expect(auth.adoptOidcPlayer).not.toHaveBeenCalled();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it.each(['not_registered', 'pending_approval', 'rejected'])('does not authenticate a %s account', async (status) => {
    auth.oidcStatus.mockResolvedValue({ status, player_id: null, roles: [] });

    const result = await useAuthStore.getState().resolveOidcSession();

    expect(result.status).toBe(status);
    expect(auth.adoptOidcPlayer).not.toHaveBeenCalled();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });

  it('propagates a failed status request so the caller can route on it', async () => {
    const failure = Object.assign(new Error('Authentication required'), { code: 401 });
    auth.oidcStatus.mockRejectedValue(failure);
    await expect(useAuthStore.getState().resolveOidcSession()).rejects.toBe(failure);
  });
});

describe('logout', () => {
  it('clears the player and roles', async () => {
    useAuthStore.setState({ player: PLAYER, isAuthenticated: true, roles: ['learner'] });
    await useAuthStore.getState().logout();
    const state = useAuthStore.getState();
    expect(state.player).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.roles).toEqual([]);
    expect(auth.logout).toHaveBeenCalledTimes(1);
  });
});
