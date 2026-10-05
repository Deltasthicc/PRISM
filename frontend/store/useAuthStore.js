'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { auth } from '@/lib/api/client';

export const useAuthStore = create(
  persist(
    (set, get) => ({
      player: null,
      isAuthenticated: false,
      loading: true, // true until the initial player-session check resolves
      error: null,
      // HTTP status of the last login()/register() failure, if any -- lets a
      // caller distinguish "this username doesn't exist yet" (404 from
      // login's by-username lookup) from a generic backend/network failure,
      // which `error` alone (a plain message string) can't do.
      errorCode: null,
      // Roles asserted by the verified OIDC token (display/navigation only --
      // the backend re-checks every permission). Empty in demo mode.
      roles: [],

      // Asks the backend who the signed-in OIDC identity is and, only when it
      // is an approved account that actually holds a role, binds the browser
      // to that player. Returns the raw /auth/me payload so callers can route
      // on status ('not_registered' | 'pending_approval' | 'rejected' |
      // 'approved'); an approved account with no role claim yet is returned
      // un-hydrated, since it has no usable permissions to act with.
      async resolveOidcSession() {
        const status = await auth.oidcStatus();
        if (status.status === 'approved' && status.player_id && status.roles.length > 0) {
          const { player } = await auth.adoptOidcPlayer(status.player_id);
          set({ player, isAuthenticated: true, loading: false, roles: status.roles, error: null });
        }
        return status;
      },

      async fetchMe() {
        const isInitialLoad = !get().player;
        if (isInitialLoad) set({ loading: true });
        try {
          const { player } = await auth.me();
          set({ player, isAuthenticated: true, loading: false, error: null });
        } catch (e) {
          // Demo mode has no real auth (backend/routes/authorization.py's
          // DISABLE_AUTH), so a 401/403 here can't mean "wrong identity" --
          // only a genuinely missing player (404) means this player no
          // longer exists. A dropped request or backend hiccup (error.code
          // === 0, or any 5xx) is refetched from fetchMe()'s next call
          // either way, not a reason to log out.
          const playerGenuinelyMissing = e.code === 404;
          if (playerGenuinelyMissing) {
            set({ player: null, isAuthenticated: false, loading: false });
          } else if (isInitialLoad) {
            // No prior local identity to fall back on (fresh tab, nothing in
            // localStorage) -- there's genuinely nothing to show, so this
            // does need to land on /login.
            set({ player: null, isAuthenticated: false, loading: false });
          } else {
            // Keep whatever identity we already had locally; just couldn't
            // refresh it this time.
            set({ loading: false });
          }
        }
      },

      async login(username) {
        set({ error: null, errorCode: null });
        try {
          const { player } = await auth.login(username);
          set({ player, isAuthenticated: true });
          return true;
        } catch (e) {
          set({ error: e.message, errorCode: e.code ?? null });
          return false;
        }
      },

      async register(username) {
        set({ error: null, errorCode: null });
        try {
          const { player } = await auth.register(username);
          set({ player, isAuthenticated: true });
          return true;
        } catch (e) {
          set({ error: e.message, errorCode: e.code ?? null });
          return false;
        }
      },

      async logout() {
        await auth.logout().catch(() => {});
        set({ player: null, isAuthenticated: false, roles: [] });
      },

      clearError() {
        set({ error: null });
      },

      // Client-side optimistic decrement, so the UI updates instantly instead
      // of waiting on POST /game/hint/use's response. useGameStore.revealHint
      // is what actually calls that server-authoritative endpoint; this just
      // mirrors its effect on the locally-held player object.
      spendHintToken() {
        const p = get().player;
        if (!p || p.hint_tokens <= 0) return;
        set({ player: { ...p, hint_tokens: p.hint_tokens - 1 } });
      },

      async selectHero(heroId) {
        const p = get().player;
        if (!p) return false;
        try {
          await auth.setHero(p.player_id, heroId);
          set({ player: { ...p, hero_id: heroId } });
          return true;
        } catch (e) {
          set({ error: e.message });
          return false;
        }
      },

      // Presentation-surface switch only (models/enums.py's LearningMode on
      // the backend) -- 'professional' (default) or the opt-in 'quest'
      // dungeon/combat layer. Never an authorization decision.
      async setPreferredMode(mode) {
        const p = get().player;
        if (!p) return false;
        try {
          await auth.setPreferredMode(p.player_id, mode);
          set({ player: { ...p, preferred_mode: mode } });
          return true;
        } catch (e) {
          set({ error: e.message });
          return false;
        }
      },
    }),
    {
      name: 'prism-auth',
      // Persist display data only; the API adapter revalidates the player on load.
      partialize: (s) => ({ player: s.player, isAuthenticated: s.isAuthenticated, roles: s.roles }),
    }
  )
);
