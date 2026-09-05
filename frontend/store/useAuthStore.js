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

      async fetchMe() {
        const isInitialLoad = !get().player;
        if (isInitialLoad) set({ loading: true });
        try {
          const { player } = await auth.me();
          set({ player, isAuthenticated: true, loading: false, error: null });
        } catch (e) {
          // Only treat an actual 401/403 as "not logged in" -- and only when
          // a real bearer token was sent and rejected (e.hadToken). A 401
          // with NO token attached means dev-login itself never completed
          // (Keycloak unreachable/misconfigured -- see client.js's
          // tryDevLogin), which is an infra availability problem, not proof
          // this player isn't who they say they are. Treating that as a hard
          // logout would bounce an already-registered demo player back to
          // /login on every single page load for as long as the identity
          // service stays down. A dropped request or backend hiccup
          // (error.code === 0, or any 5xx) is refetched from fetchMe()'s next
          // call either way.
          const isRealAuthRejection = (e.code === 401 || e.code === 403) && e.hadToken;
          if (isRealAuthRejection) {
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
        set({ error: null });
        try {
          const { player } = await auth.login(username);
          set({ player, isAuthenticated: true });
          return true;
        } catch (e) {
          set({ error: e.message });
          return false;
        }
      },

      async register(username) {
        set({ error: null });
        try {
          const { player } = await auth.register(username);
          set({ player, isAuthenticated: true });
          return true;
        } catch (e) {
          set({ error: e.message });
          return false;
        }
      },

      async logout() {
        await auth.logout().catch(() => {});
        set({ player: null, isAuthenticated: false });
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
    }),
    {
      name: 'prism-auth',
      // Persist display data only; the API adapter revalidates the player on load.
      partialize: (s) => ({ player: s.player, isAuthenticated: s.isAuthenticated }),
    }
  )
);
