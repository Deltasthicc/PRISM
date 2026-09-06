'use client';

import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { DEFAULT_LANGUAGE, TRANSLATIONS } from './translations';

const STORAGE_KEY = 'prism-language';

const LanguageContext = createContext({
  language: DEFAULT_LANGUAGE,
  setLanguage: () => {},
  t: (key) => key,
});

function lookup(language, key) {
  const path = key.split('.');
  let node = TRANSLATIONS[language];
  for (const segment of path) {
    node = node?.[segment];
    if (node === undefined) break;
  }
  if (typeof node === 'string') return node;
  // Fall back to English rather than showing a raw dot-path key to the user.
  let fallback = TRANSLATIONS[DEFAULT_LANGUAGE];
  for (const segment of path) {
    fallback = fallback?.[segment];
    if (fallback === undefined) break;
  }
  return typeof fallback === 'string' ? fallback : key;
}

export function LanguageProvider({ children }) {
  const [language, setLanguageState] = useState(DEFAULT_LANGUAGE);

  useEffect(() => {
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored && TRANSLATIONS[stored]) setLanguageState(stored);
    } catch {
      // localStorage unavailable (private browsing, etc.) -- stay on default.
    }
  }, []);

  function setLanguage(next) {
    if (!TRANSLATIONS[next]) return;
    setLanguageState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Best-effort only; the language still applies for this session.
    }
  }

  const value = useMemo(
    () => ({
      language,
      setLanguage,
      t: (key) => lookup(language, key),
    }),
    [language]
  );

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

export function useLanguage() {
  return useContext(LanguageContext);
}
