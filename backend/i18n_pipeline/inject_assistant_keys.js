// Injects the new /assistant page + nav.assistant keys into every language
// block of frontend/lib/i18n/translations.js. English values come straight
// from assistant_strings.json; every other language's values come from
// translate_assistant_keys.py's output (Google Translate/MyMemory, never
// hand-translated) -- this script only reshapes JSON into the nested
// TRANSLATIONS[lang] shape, it does not translate anything itself.
const fs = require('fs');
const path = require('path');

const TRANSLATIONS_PATH = path.join(__dirname, '..', '..', 'frontend', 'lib', 'i18n', 'translations.js');
const ALL_LANGS = ['en', 'hi', 'bn', 'mr', 'te', 'ta', 'gu', 'ur', 'kn', 'or', 'ml'];

function loadFlat(lang) {
  if (lang === 'en') {
    return JSON.parse(fs.readFileSync(path.join(__dirname, 'assistant_strings.json'), 'utf-8'));
  }
  // `lang` only ever comes from the hardcoded ALL_LANGS array below (never
  // external input), but re-checking that here -- instead of trusting the
  // caller -- is what makes the path.join below provably safe rather than
  // merely "safe today by construction." The rule below pattern-matches the
  // path.join(..., `template ${var}`) shape itself and can't see that the
  // preceding allowlist check already rejects anything but a known-safe
  // literal -- same false-positive-after-a-real-mitigation situation as
  // inject_frontend.js's nosemgrep comment documents for a different rule.
  if (!ALL_LANGS.includes(lang)) {
    throw new Error(`Unsupported language code: ${lang}`);
  }
  return JSON.parse(
    fs.readFileSync(path.join(__dirname, `assistant_${lang}.json`), 'utf-8') // nosemgrep: javascript.lang.security.audit.path-traversal.path-join-resolve-traversal.path-join-resolve-traversal
  );
}

// Same null-prototype guard as inject_frontend.js's unflatten(), for the
// same prototype-pollution-loop reason (Semgrep flags the loop shape even
// though a prototype-less node can't be polluted).
function setNested(root, dotPath, value) {
  const segments = dotPath.split('.');
  let node = root;
  for (let i = 0; i < segments.length - 1; i++) {
    const seg = segments[i];
    if (typeof node[seg] !== 'object' || node[seg] === null) {
      node[seg] = Object.create(null);
    }
    node = node[seg]; // nosemgrep: javascript.lang.security.audit.prototype-pollution.prototype-pollution-loop.prototype-pollution-loop
  }
  node[segments[segments.length - 1]] = value;
}

function evalTranslations(src) {
  const stripped = src.replace(/export const/g, 'const');
  const wrapped = stripped + '\nmodule.exports = { LANGUAGES, DEFAULT_LANGUAGE, TRANSLATIONS };\n';
  const Module = require('module');
  const m = new Module('translations-eval-assistant');
  m._compile(wrapped, 'translations-eval-assistant.js');
  return m.exports;
}

function main() {
  const src = fs.readFileSync(TRANSLATIONS_PATH, 'utf-8');
  const { LANGUAGES, TRANSLATIONS } = evalTranslations(src);

  for (const lang of ALL_LANGS) {
    const flat = loadFlat(lang);
    if (!TRANSLATIONS[lang]) TRANSLATIONS[lang] = {};
    for (const [dotPath, value] of Object.entries(flat)) {
      setNested(TRANSLATIONS[lang], dotPath, value);
    }
    console.log(`merged assistant keys into '${lang}'`);
  }

  const header = `// Static UI-chrome translations only (nav labels, buttons, headings, form
// labels, static copy) -- never AI-generated content (quiz questions, gap
// analysis text), which still comes back from the backend in whatever
// language it was generated in. See LanguageContext.jsx for the lookup.
//
// Non-English blocks below (everything except 'en') were machine-translated
// via translate.py's calls to Google Translate's public endpoint, then
// merged with an English fallback for any key the translator failed to
// return -- see backend/i18n_pipeline/. Not hand-translated by an assistant,
// per the project's "don't burn tokens hand-translating, use a real
// translator" instruction; treat these as a first pass a native speaker
// should review, same as any machine translation.
export const LANGUAGES = ${JSON.stringify(LANGUAGES, null, 2).replace(/"([a-zA-Z_$][a-zA-Z0-9_$]*)":/g, '$1:')};

export const DEFAULT_LANGUAGE = 'en';

export const TRANSLATIONS = ${JSON.stringify(TRANSLATIONS, null, 2)};
`;

  fs.writeFileSync(TRANSLATIONS_PATH, header, 'utf-8');
  console.log(`Wrote ${TRANSLATIONS_PATH}`);
}

main();
