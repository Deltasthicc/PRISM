import { describe, expect, it } from 'vitest';
import { DEFAULT_LANGUAGE, LANGUAGES, TRANSLATIONS } from '@/lib/i18n/translations';

function leafPaths(node, prefix = '') {
  return Object.entries(node).flatMap(([key, value]) =>
    value !== null && typeof value === 'object' ? leafPaths(value, `${prefix}${key}.`) : [`${prefix}${key}`]
  );
}

const english = new Set(leafPaths(TRANSLATIONS[DEFAULT_LANGUAGE]));

describe('translations', () => {
  it('defines a dictionary for every advertised language', () => {
    for (const { code } of LANGUAGES) {
      expect(TRANSLATIONS[code], `missing dictionary for ${code}`).toBeTruthy();
    }
  });

  it('has no key in any language that English lacks (English is the fallback)', () => {
    for (const [code, dictionary] of Object.entries(TRANSLATIONS)) {
      const orphans = leafPaths(dictionary).filter((path) => !english.has(path));
      expect(orphans, `${code} has keys English does not`).toEqual([]);
    }
  });

  it('translates the skip link in every language rather than leaving English', () => {
    const englishLabel = TRANSLATIONS[DEFAULT_LANGUAGE].nav.skipToContent;
    expect(englishLabel).toBeTruthy();
    for (const [code, dictionary] of Object.entries(TRANSLATIONS)) {
      expect(dictionary.nav.skipToContent, code).toBeTruthy();
      if (code !== DEFAULT_LANGUAGE) expect(dictionary.nav.skipToContent, code).not.toBe(englishLabel);
    }
  });
});
