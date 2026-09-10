"""Translates voice_strings.json (the new /voice page + nav label) into hi
plus the 9 non-English languages, via translate.py's translate_one (Google
Translate / MyMemory fallback -- never an LLM, never hand-translated).

Run from this directory: python translate_voice_keys.py
Writes voice_<lang>.json for each of hi, bn, mr, te, ta, gu, ur, kn, or, ml.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from translate import translate_one  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
LANGS = ["hi", "bn", "mr", "te", "ta", "gu", "ur", "kn", "or", "ml"]


def main():
    with open(os.path.join(HERE, "voice_strings.json"), encoding="utf-8") as f:
        source = json.load(f)

    for lang in LANGS:
        print(f"Translating voice strings into '{lang}'...")
        result = {}
        for key, text in source.items():
            result[key] = translate_one(text, lang)
            time.sleep(0.3)
        out_path = os.path.join(HERE, f"voice_{lang}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  wrote {out_path}")


if __name__ == "__main__":
    main()
