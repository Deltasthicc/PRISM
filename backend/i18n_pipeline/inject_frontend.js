// Reassembles each <lang>_flat.json (dot-path -> translated string) back
// into the nested TRANSLATIONS[lang] shape and writes the whole, updated
// translations.js. Every translated string here came from translate.py's
// Google Translate calls -- this script only reshapes JSON, it does not
// translate anything itself.
const fs = require('fs');
const path = require('path');

const TRANSLATIONS_PATH = path.join(__dirname, '..', '..', 'frontend', 'lib', 'i18n', 'translations.js');
const EN_FLAT_PATH = path.join(__dirname, 'en_flat.json');

const NEW_LANGUAGES = [
  { code: 'bn', label: 'বাংলা' },
  { code: 'mr', label: 'मराठी' },
  { code: 'te', label: 'తెలుగు' },
  { code: 'ta', label: 'தமிழ்' },
  { code: 'gu', label: 'ગુજરાતી' },
  { code: 'ur', label: 'اردو' },
  { code: 'kn', label: 'ಕನ್ನಡ' },
  { code: 'or', label: 'ଓଡ଼ିଆ' },
  { code: 'ml', label: 'മലയാളം' },
];

// Keys here are en_flat.json's own dot-paths (derived from this app's own
// translations.js, not external input), but every level is built with
// Object.create(null) regardless -- one of Semgrep's own documented
// mitigations for this shape ("using an object without prototypes"). A
// prototype-less node has no inherited __proto__/constructor to hit, so
// `node = node[seg]` can never walk into Object.prototype no matter what
// `seg` is.
function unflatten(flat) {
  const root = Object.create(null);
  for (const [dotPath, value] of Object.entries(flat)) {
    const segments = dotPath.split('.');
    let node = root;
    for (let i = 0; i < segments.length - 1; i++) {
      const seg = segments[i];
      if (typeof node[seg] !== 'object' || node[seg] === null) {
        node[seg] = Object.create(null);
      }
      node = node[seg];
    }
    node[segments[segments.length - 1]] = value;
  }
  return root;
}

function loadSrc() {
  return fs.readFileSync(TRANSLATIONS_PATH, 'utf-8');
}

function evalTranslations(src) {
  const stripped = src.replace(/export const/g, 'const');
  const wrapped = stripped + '\nmodule.exports = { LANGUAGES, DEFAULT_LANGUAGE, TRANSLATIONS };\n';
  const Module = require('module');
  const m = new Module('translations-eval-2');
  m._compile(wrapped, 'translations-eval-2.js');
  return m.exports;
}

function main() {
  const src = loadSrc();
  const { TRANSLATIONS: existing, LANGUAGES: existingLanguages } = evalTranslations(src);
  const enFlat = JSON.parse(fs.readFileSync(EN_FLAT_PATH, 'utf-8'));

  const addedLanguages = [];
  for (const { code, label } of NEW_LANGUAGES) {
    const flatPath = path.join(__dirname, `${code}_flat.json`);
    if (!fs.existsSync(flatPath)) {
      console.log(`skip ${code}: no ${code}_flat.json`);
      continue;
    }
    const translatedFlat = JSON.parse(fs.readFileSync(flatPath, 'utf-8'));
    // Fill any failed/missing key with the English source so lookup() never
    // needs to fall back mid-sentence -- a whole-string English fallback is
    // more honest than a half-translated sentence.
    const merged = { ...enFlat, ...translatedFlat };
    existing[code] = unflatten(merged);
    addedLanguages.push({ code, label });
    console.log(`merged ${code}: ${Object.keys(translatedFlat).length}/${Object.keys(enFlat).length} translated, rest English fallback`);
  }

  const finalLanguages = [...existingLanguages];
  for (const lang of addedLanguages) {
    if (!finalLanguages.some((l) => l.code === lang.code)) finalLanguages.push(lang);
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
export const LANGUAGES = ${JSON.stringify(finalLanguages, null, 2).replace(/"([a-zA-Z_$][a-zA-Z0-9_$]*)":/g, '$1:')};

export const DEFAULT_LANGUAGE = 'en';

export const TRANSLATIONS = ${JSON.stringify(existing, null, 2)};
`;

  fs.writeFileSync(TRANSLATIONS_PATH, header, 'utf-8');
  console.log(`Wrote ${TRANSLATIONS_PATH}`);
}

main();
