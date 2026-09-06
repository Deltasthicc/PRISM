'use client';

import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { DEFAULT_LANGUAGE, TRANSLATIONS } from './translations';

const STORAGE_KEY = 'prism-language';

const LanguageContext = createContext({
  language: DEFAULT_LANGUAGE,
  setLanguage: () => {},
  t: (key) => key,
});

// `key` is always a hardcoded string literal at every call site (e.g.
// t('nav.signOut')), never user input -- but walking a dict by a
// caller-supplied path one segment at a time, with no own-property check,
// is exactly the shape a prototype-pollution scanner flags on sight (a
// segment of "__proto__" would otherwise walk into Object.prototype
// instead of failing the lookup). Guarding each segment with a real
// hasOwnProperty check closes that off for good, regardless of where a
// future caller's key string comes from.
function getOwn(node, segment) {
  if (node === null || typeof node !== 'object') return undefined;
  if (!Object.prototype.hasOwnProperty.call(node, segment)) return undefined;
  return node[segment];
}

function resolve(dict, path) {
  let node = dict;
  for (const segment of path) {
    node = getOwn(node, segment);
    if (node === undefined) return undefined;
  }
  return typeof node === 'string' ? node : undefined;
}

function lookup(language, key) {
  const path = key.split('.');
  const value = resolve(TRANSLATIONS[language], path);
  if (value !== undefined) return value;
  // Fall back to English rather than showing a raw dot-path key to the user.
  const fallback = resolve(TRANSLATIONS[DEFAULT_LANGUAGE], path);
  return fallback !== undefined ? fallback : key;
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
