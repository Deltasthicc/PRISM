'use client';

import { createContext, useContext, useEffect, useMemo, useState } from 'react';

// Mirrors lib/i18n/LanguageContext.jsx's exact shape (context + provider +
// useX() hook + namespaced localStorage key) -- a sibling to the language
// system, not a rewrite of it.
const STORAGE_KEY = 'prism-a11y-prefs';

const AccessibilityContext = createContext({
  highContrast: false,
  setHighContrast: () => {},
  largeText: false,
  setLargeText: () => {},
  reducedMotion: false,
  setReducedMotion: () => {},
});

function readStoredPrefs() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    // localStorage unavailable (private browsing, etc.) or corrupt JSON --
    // stay on defaults.
    return null;
  }
}

function writeStoredPrefs(next) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    // Best-effort only; the preference still applies for this session.
  }
}

function osPrefersReducedMotion() {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch {
    return false;
  }
}

export function AccessibilityProvider({ children }) {
  const [highContrast, setHighContrastState] = useState(false);
  const [largeText, setLargeTextState] = useState(false);
  const [reducedMotion, setReducedMotionState] = useState(false);

  // Hydrate from localStorage once we're in the browser. `reducedMotion`
  // is special: if the learner has never made an explicit choice (nothing
  // stored yet for that key), initialize it from the real OS-level
  // `prefers-reduced-motion` signal instead of hardcoding false. Once they
  // do choose explicitly (see the wrapped setters below), that choice is
  // persisted and wins over the OS setting on every future visit.
  useEffect(() => {
    const stored = readStoredPrefs();
    if (stored && typeof stored.highContrast === 'boolean') {
      setHighContrastState(stored.highContrast);
    }
    if (stored && typeof stored.largeText === 'boolean') {
      setLargeTextState(stored.largeText);
    }
    if (stored && typeof stored.reducedMotion === 'boolean') {
      setReducedMotionState(stored.reducedMotion);
    } else {
      setReducedMotionState(osPrefersReducedMotion());
    }
  }, []);

  // Real, working behavior: these attributes are exactly what a11y.css
  // keys off of for high-contrast/large-text/reduced-motion rules -- not
  // decorative markers with no CSS behind them.
  useEffect(() => {
    document.documentElement.setAttribute('data-high-contrast', String(highContrast));
  }, [highContrast]);

  useEffect(() => {
    document.documentElement.setAttribute('data-large-text', String(largeText));
  }, [largeText]);

  useEffect(() => {
    document.documentElement.setAttribute('data-reduced-motion', String(reducedMotion));
  }, [reducedMotion]);

  // Every explicit setter call both updates state and persists immediately
  // -- merging into whatever is already stored so toggling one preference
  // never clobbers the other two.
  function setHighContrast(next) {
    setHighContrastState(next);
    writeStoredPrefs({ ...readStoredPrefs(), highContrast: next });
  }

  function setLargeText(next) {
    setLargeTextState(next);
    writeStoredPrefs({ ...readStoredPrefs(), largeText: next });
  }

  function setReducedMotion(next) {
    setReducedMotionState(next);
    writeStoredPrefs({ ...readStoredPrefs(), reducedMotion: next });
  }

  const value = useMemo(
    () => ({
      highContrast,
      setHighContrast,
      largeText,
      setLargeText,
      reducedMotion,
      setReducedMotion,
    }),
    [highContrast, largeText, reducedMotion]
  );

  return <AccessibilityContext.Provider value={value}>{children}</AccessibilityContext.Provider>;
}

export function useAccessibility() {
  return useContext(AccessibilityContext);
}
