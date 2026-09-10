"""Translates backend_strings.json (small dicts embedded in
services/learning_catalog.py, services/learning_engine.py, and
routes/learning_analytics.py) into each target language via Google
Translate (translate.py's translate_one). PLACEHOLDER0/PLACEHOLDER1 markers
stand in for {label}/{types}/{version} format placeholders -- Google
Translate mangles literal "{word}" braces (translates the word inside them,
breaking str.format() call sites), but leaves an all-caps token untouched,
confirmed by hand before writing this. This script restores the real
placeholder names after translation using PLACEHOLDER_MAP below.

Run from this directory: python translate_backend_strings.py <lang_code> [...]
Writes backend_<lang>.json for a human to paste into the three source files'
existing per-language dict literals (small enough to review each entry
directly rather than regex-injecting into Python source).
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from translate import translate_one  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE_PATH = os.path.join(HERE, "backend_strings.json")

PLACEHOLDER_MAP = {
    "catalog.title_internal_practice": ["{label}"],
    "catalog.title_igot": ["{label}"],
    "catalog.title_nssta": ["{label}"],
    "engine.evidence_unscored": ["{types}", "{version}"],
}


def restore_placeholders(key: str, text: str) -> str:
    names = PLACEHOLDER_MAP.get(key)
    if not names:
        return text
    for i, name in enumerate(names):
        text = text.replace(f"PLACEHOLDER{i}", name)
    return text


def main():
    target_langs = sys.argv[1:]
    if not target_langs:
        print("usage: python translate_backend_strings.py <lang_code> [...]")
        sys.exit(1)

    with open(SOURCE_PATH, "r", encoding="utf-8") as f:
        source = json.load(f)

    for lang in target_langs:
        print(f"Translating backend strings into '{lang}'...")
        result = {}
        for key, text in source.items():
            translated = translate_one(text, lang)
            result[key] = restore_placeholders(key, translated)
            time.sleep(0.1)
        out_path = os.path.join(HERE, f"backend_{lang}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  wrote {out_path}")


if __name__ == "__main__":
    main()
