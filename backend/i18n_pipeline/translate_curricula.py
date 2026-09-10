"""Machine-translates services/curricula.py's learner-facing fields (name,
domain, description, audience, level_band per curriculum; label/description
per competency) into each target language, writing curricula_<lang>.json
next to the hand-translated curricula_hi.json. Mirrors
scripts/generate_curricula_hi.py's field selection and shape, but calls
Google Translate per-string (via translate.py's translate_one) instead of
Gemini, since no working GEMINI_API_KEY is available in this environment.

Deliberately does NOT touch COMPETENCY_SOURCES citation excerpts or SOURCES
title/publisher -- same reasoning as generate_curricula_hi.py: those are
literal references to real government documents and are not shown to a
learner today.

Run from this directory: python translate_curricula.py <lang_code> [...]
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.curricula import CURRICULA  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from translate import translate_one  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
CURRICULUM_FIELDS = ["name", "domain", "description", "audience", "level_band"]
COMPETENCY_FIELDS = ["label", "description"]


def build_source_payload() -> dict:
    payload = {}
    for slug, curriculum in CURRICULA.items():
        payload[slug] = {field: curriculum[field] for field in CURRICULUM_FIELDS}
        payload[slug]["competencies"] = {
            item["id"]: {field: item[field] for field in COMPETENCY_FIELDS}
            for item in curriculum["competencies"]
        }
    return payload


def translate_payload(payload: dict, lang: str) -> dict:
    out = {}
    total = sum(
        len(CURRICULUM_FIELDS) + len(c.get("competencies", {})) * len(COMPETENCY_FIELDS)
        for c in payload.values()
    )
    done = 0
    for slug, curriculum in payload.items():
        out[slug] = {}
        for field in CURRICULUM_FIELDS:
            out[slug][field] = translate_one(curriculum[field], lang)
            done += 1
            time.sleep(0.1)
        out[slug]["competencies"] = {}
        for comp_id, comp in curriculum["competencies"].items():
            out[slug]["competencies"][comp_id] = {
                field: translate_one(comp[field], lang) for field in COMPETENCY_FIELDS
            }
            done += len(COMPETENCY_FIELDS)
            time.sleep(0.1)
        print(f"  [{lang}] {done}/{total}")
    return out


def main():
    target_langs = sys.argv[1:]
    if not target_langs:
        print("usage: python translate_curricula.py <lang_code> [...]")
        sys.exit(1)

    source = build_source_payload()
    for lang in target_langs:
        print(f"Translating curricula into '{lang}'...")
        translated = translate_payload(source, lang)
        out_path = os.path.join(
            os.path.dirname(HERE), "services", f"curricula_{lang}.json"
        )
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(translated, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print(f"  wrote {out_path}")


if __name__ == "__main__":
    main()
