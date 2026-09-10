// One-off: inserts the 10 new dsaSandboxPage keys (searchPlaceholder,
// noMatches, examples, example, input, output, constraints, solutionOutline,
// reset, testResults) -- added by codex/dsa-sandbox-polish for en/hi only --
// into the other 9 languages' dsaSandboxPage blocks, translated via
// translate.py (see sandbox_new_keys_translated.json). Keeps the exact key
// order Codex used (right after "problemsHeading", before "run") so every
// language's dsaSandboxPage block has the same key order.
const fs = require('fs');
const path = require('path');

const TRANSLATIONS_PATH = path.join(__dirname, '..', '..', 'frontend', 'lib', 'i18n', 'translations.js');
const translated = JSON.parse(fs.readFileSync(path.join(__dirname, 'sandbox_new_keys_translated.json'), 'utf-8'));

const KEY_ORDER = [
  'searchPlaceholder', 'noMatches', 'examples', 'example', 'input',
  'output', 'constraints', 'solutionOutline', 'reset', 'testResults',
];

let src = fs.readFileSync(TRANSLATIONS_PATH, 'utf-8');

// The file uses CRLF line endings -- match "\r?\n" everywhere a bare "\n"
// would otherwise silently fail to match.
for (const lang of Object.keys(translated)) {
  // Find this language's dsaSandboxPage block and its problemsHeading line specifically.
  const langBlockRe = new RegExp(`("${lang}": \\{[\\s\\S]*?"dsaSandboxPage": \\{[\\s\\S]*?"problemsHeading": "[^"]*",\\r?\\n)`);
  const match = src.match(langBlockRe);
  if (!match) {
    throw new Error(`could not find dsaSandboxPage.problemsHeading for lang ${lang}`);
  }
  const insertAt = match.index + match[0].length;
  const indent = '      ';
  const lines = KEY_ORDER.map((key) => `${indent}"${key}": ${JSON.stringify(translated[lang][key])},\r\n`).join('');
  src = src.slice(0, insertAt) + lines + src.slice(insertAt);
}

fs.writeFileSync(TRANSLATIONS_PATH, src, 'utf-8');
console.log('Inserted sandbox keys for:', Object.keys(translated).join(', '));
