'use client';

import { create } from 'zustand';

const SEEN_KEY = 'codecrypt_onboarding_seen';

export const useOnboardingStore = create((set) => ({
  open: false,
  openModal: () => set({ open: true }),
  closeModal: () => {
    if (typeof window !== 'undefined') window.localStorage.setItem(SEEN_KEY, '1');
    set({ open: false });
  },
  // Called once auth resolves -- opens automatically only the first time.
  openIfUnseen: () => {
    const seen = typeof window !== 'undefined' && window.localStorage.getItem(SEEN_KEY);
    if (!seen) set({ open: true });
  },
}));
