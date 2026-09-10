"""Translates en_flat.json into each target language using two free,
no-API-key translation backends -- Google Translate's public endpoint first,
MyMemory (api.mymemory.translated.net, a real translation-memory + neural MT
service) as a fallback when Google is rate-limited. GEMINI_API_KEY is not
configured/working in this environment (confirmed by hand before writing
this), so neither backend is an LLM call from this assistant -- every string
is copied verbatim from one of these two translators' responses, per the
project's "use a real translator, don't hand-translate" instruction.

Google's free client=gtx endpoint 429s after a burst of a few hundred rapid
requests and needs a real cooldown (confirmed by hand: it stayed blocked
across a 6-step, ~5min backoff ladder). Rather than stall a whole language on
that, translate_one falls back to MyMemory per-string once Google's retries
are exhausted, so a single rate-limited burst doesn't block the run.

Run from this directory: python translate.py <lang_code> [<lang_code> ...]
Writes <lang>_flat.json (dict of dot-path -> translated string) next to
en_flat.json, plus <lang>_failed.json listing any key neither backend could
translate (left untranslated -- English fallback already covers missing keys
via LanguageContext.jsx and inject_frontend.js, so a failed key is not a
blocker).
"""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
EN_FLAT_PATH = os.path.join(HERE, "en_flat.json")
USER_AGENT = "Mozilla/5.0"
GOOGLE_RETRIES = 2
RATE_LIMIT_BACKOFF = [5, 15]
REQUEST_DELAY = 0.4
MYMEMORY_RETRIES = 3


def _translate_google(text: str, target_lang: str) -> str:
    q = urllib.parse.quote(text)
    url = (
        "https://translate.googleapis.com/translate_a/single"
        f"?client=gtx&sl=en&tl={target_lang}&dt=t&q={q}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_exc = None
    for attempt in range(GOOGLE_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return "".join(segment[0] for segment in data[0])
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code == 429:
                time.sleep(RATE_LIMIT_BACKOFF[min(attempt, len(RATE_LIMIT_BACKOFF) - 1)])
            else:
                time.sleep(1.0 * (attempt + 1))
        except Exception as exc:  # noqa: BLE001 - retry any transient failure
            last_exc = exc
            time.sleep(1.0 * (attempt + 1))
    raise last_exc


def _translate_mymemory(text: str, target_lang: str) -> str:
    q = urllib.parse.quote(text)
    url = f"https://api.mymemory.translated.net/get?q={q}&langpair=en|{target_lang}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_exc = None
    for attempt in range(MYMEMORY_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            if data.get("responseStatus") != 200:
                raise RuntimeError(f"MyMemory status {data.get('responseStatus')}")
            translated = data.get("responseData", {}).get("translatedText", "")
            if not translated:
                raise RuntimeError("MyMemory returned empty translation")
            return translated
        except Exception as exc:  # noqa: BLE001 - retry any transient failure
            last_exc = exc
            time.sleep(2.0 * (attempt + 1))
    raise last_exc


def translate_one(text: str, target_lang: str) -> str:
    try:
        return _translate_google(text, target_lang)
    except Exception:
        return _translate_mymemory(text, target_lang)


def translate_language(target_lang: str, en_flat: dict) -> tuple:
    result = {}
    failed = []
    total = len(en_flat)
    for i, (key, text) in enumerate(en_flat.items()):
        try:
            translated = translate_one(text, target_lang)
            if translated.strip():
                result[key] = translated
            else:
                failed.append(key)
        except Exception as exc:
            print(f"  [{target_lang}] key {key} failed: {exc}")
            failed.append(key)
        if (i + 1) % 50 == 0:
            print(f"  [{target_lang}] {i + 1}/{total}")
        time.sleep(REQUEST_DELAY)
    return result, failed


def main():
    target_langs = sys.argv[1:]
    if not target_langs:
        print("usage: python translate.py <lang_code> [<lang_code> ...]")
        sys.exit(1)

    with open(EN_FLAT_PATH, "r", encoding="utf-8") as f:
        en_flat = json.load(f)

    for lang in target_langs:
        print(f"Translating {len(en_flat)} keys into '{lang}'...")
        result, failed = translate_language(lang, en_flat)
        out_path = os.path.join(HERE, f"{lang}_flat.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        if failed:
            fail_path = os.path.join(HERE, f"{lang}_failed.json")
            with open(fail_path, "w", encoding="utf-8") as f:
                json.dump(failed, f, ensure_ascii=False, indent=2)
        print(f"  {lang}: {len(result)}/{len(en_flat)} translated, {len(failed)} failed")


if __name__ == "__main__":
    main()
