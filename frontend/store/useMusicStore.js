'use client';

import { create } from 'zustand';

const STORAGE_KEY = 'codecrypt_music_enabled';

function loadInitial() {
  if (typeof window === 'undefined') return false;
  return window.localStorage.getItem(STORAGE_KEY) === 'true';
}

// Browsers block audio-with-sound until a real user gesture, so music starts
// off by default -- MusicPlayer only ever calls .play() from inside this
// store's toggle(), which is itself only ever invoked from a click handler.
export const useMusicStore = create((set, get) => ({
  enabled: false,
  hydrated: false,
  hydrate() {
    if (get().hydrated) return;
    set({ enabled: loadInitial(), hydrated: true });
  },
  toggle() {
    const next = !get().enabled;
    set({ enabled: next });
    if (typeof window !== 'undefined') window.localStorage.setItem(STORAGE_KEY, String(next));
  },
}));
