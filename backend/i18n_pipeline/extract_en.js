// One-off extraction script: pulls TRANSLATIONS.en out of the frontend's
// translations.js as a flat { "dot.path": "string" } JSON map, so the
// translation pipeline can operate on plain strings without touching JS
// syntax. Run with: node extract_en.js > en_flat.json
const fs = require('fs');
const path = require('path');

const src = fs.readFileSync(
  path.join(__dirname, '..', '..', 'frontend', 'lib', 'i18n', 'translations.js'),
  'utf-8'
);
const stripped = src.replace(/export const/g, 'const');
const wrapped = stripped + '\nmodule.exports = { LANGUAGES, DEFAULT_LANGUAGE, TRANSLATIONS };\n';

const Module = require('module');
const m = new Module('translations-eval');
m._compile(wrapped, 'translations-eval.js');
const { TRANSLATIONS } = m.exports;

const flat = {};
function walk(node, prefix) {
  for (const key of Object.keys(node)) {
    const value = node[key];
    const nextPrefix = prefix ? `${prefix}.${key}` : key;
    if (typeof value === 'string') {
      flat[nextPrefix] = value;
    } else if (value && typeof value === 'object') {
      walk(value, nextPrefix);
    }
  }
}
walk(TRANSLATIONS.en, '');

fs.writeFileSync(
  path.join(__dirname, 'en_flat.json'),
  JSON.stringify(flat, null, 2),
  'utf-8'
);
console.log(`Extracted ${Object.keys(flat).length} leaf strings to en_flat.json`);
