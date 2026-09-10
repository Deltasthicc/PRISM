"""Inserts the 9 new languages' small template-string dicts (translated via
translate_backend_strings.py) into services/learning_catalog.py,
services/learning_engine.py, and routes/learning_analytics.py, right after
each dict's existing "hi": {...} (or "hi": "...") entry -- mirroring the
existing en/hi structure exactly. Every value written here is copied
verbatim from backend_<lang>.json, itself copied verbatim from a real
translator's response (see translate_backend_strings.py); nothing here is
hand-translated.
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(HERE)
LANGS = ["bn", "mr", "te", "ta", "gu", "ur", "kn", "or", "ml"]

translations = {lang: json.load(open(os.path.join(HERE, f"backend_{lang}.json"), encoding="utf-8")) for lang in LANGS}


def py_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def insert_dict_block(src: str, anchor_hi_block: str, keys: list, prefix: str, indent: str = "    ") -> str:
    idx = src.index(anchor_hi_block)
    insert_at = idx + len(anchor_hi_block)
    pieces = []
    for lang in LANGS:
        t = translations[lang]
        lines = [f'{indent}"{lang}": {{']
        for py_key, t_key in keys:
            value = t.get(f"{prefix}.{t_key}") if t_key else None
            if value is None:
                raise KeyError(f"missing {prefix}.{t_key} for {lang}")
            lines.append(f'{indent}    "{py_key}": {py_str(value)},')
        lines.append(f"{indent}}},")
        pieces.append("\n" + "\n".join(lines))
    return src[:insert_at] + "".join(pieces) + src[insert_at:]


def insert_string_entries(src: str, anchor_hi_line: str, t_key: str) -> str:
    idx = src.index(anchor_hi_line)
    insert_at = idx + len(anchor_hi_line)
    pieces = []
    for lang in LANGS:
        value = translations[lang].get(t_key)
        if value is None:
            raise KeyError(f"missing {t_key} for {lang}")
        pieces.append(f'\n    "{lang}": {py_str(value)},')
    return src[:insert_at] + "".join(pieces) + src[insert_at:]


def process_learning_catalog():
    path = os.path.join(BACKEND_DIR, "services", "learning_catalog.py")
    src = open(path, encoding="utf-8").read()

    # 1) top status-detail dict's "hi": {...} block
    hi_status_block = re.search(
        r'    "hi": \{\n(?:.*\n)*?    \},\n', src
    ).group(0)
    src = insert_dict_block(
        src,
        hi_status_block,
        [
            ("igot_live", "igot_live"),
            ("igot_error", "igot_error"),
            ("igot_fallback", "igot_fallback"),
            ("nssta_live", "nssta_live"),
            ("nssta_error", "nssta_error"),
            ("nssta_fallback", "nssta_fallback"),
        ],
        "catalog",
    )

    # 2) _PROVIDER_NAME's hi line (single-line dict)
    provider_hi_line = '    "hi": {"internal-practice": "आंतरिक अभ्यास", "igot": "iGOT कर्मयोगी", "nssta": "NSSTA / TPAC"},\n'
    assert provider_hi_line in src, "provider hi line not found verbatim"
    pieces = []
    for lang in LANGS:
        t = translations[lang]
        internal = py_str(t["catalog.provider_internal_practice"])
        igot = py_str(t["catalog.provider_igot"])
        pieces.append(f'    "{lang}": {{"internal-practice": {internal}, "igot": {igot}, "nssta": "NSSTA / TPAC"}},\n')
    src = src.replace(provider_hi_line, provider_hi_line + "".join(pieces))

    # 3) _TITLE_TEMPLATE's hi block
    title_hi_block = re.search(
        r'    "hi": \{\n        "internal-practice": "अनुकूली अभ्यास: \{label\}",\n(?:.*\n)*?    \},\n', src
    ).group(0)
    src = insert_dict_block(
        src,
        title_hi_block,
        [
            ("internal-practice", "title_internal_practice"),
            ("igot", "title_igot"),
            ("nssta", "title_nssta"),
        ],
        "catalog",
    )

    # 4) _INTERNAL_PRACTICE_NOTE single-string hi entry
    note_hi_line = '    "hi": "इस ऐप के अपने अनुकूली प्रश्न इंजन द्वारा मांग पर उत्पन्न।",\n'
    assert note_hi_line in src, "internal practice note hi line not found verbatim"
    src = insert_string_entries(src, note_hi_line, "catalog.internal_practice_note")

    open(path, "w", encoding="utf-8").write(src)
    print(f"updated {path}")


def process_learning_engine():
    path = os.path.join(BACKEND_DIR, "services", "learning_engine.py")
    src = open(path, encoding="utf-8").read()

    level_hi_block = re.search(r'    "hi": \{\n        "not_yet_evidenced".*?\n(?:.*\n)*?    \},\n', src).group(0)
    src = insert_dict_block(
        src,
        level_hi_block,
        [
            ("not_yet_evidenced", "level_not_yet_evidenced"),
            ("foundation", "level_foundation"),
            ("working_knowledge", "level_working_knowledge"),
            ("practitioner", "level_practitioner"),
            ("advanced", "level_advanced"),
            ("expert", "level_expert"),
        ],
        "engine",
    )

    evtype_hi_block = re.search(r'    "hi": \{\n        "reviewer".*?\n(?:.*\n)*?    \},\n', src).group(0)
    src = insert_dict_block(
        src,
        evtype_hi_block,
        [
            ("reviewer", "evidence_type_reviewer"),
            ("diagnostic", "evidence_type_diagnostic"),
            ("observed_practice", "evidence_type_observed_practice"),
            ("provider_imported", "evidence_type_provider_imported"),
            ("self_report", "evidence_type_self_report"),
        ],
        "engine",
    )

    evsent_hi_block = re.search(r'    "hi": \{\n        "both".*?\n(?:.*\n)*?    \},\n', src).group(0)
    src = insert_dict_block(
        src,
        evsent_hi_block,
        [
            ("both", "evidence_both"),
            ("measured_only", "evidence_measured_only"),
            ("self_only", "evidence_self_only"),
            ("unscored", "evidence_unscored"),
            ("none", "evidence_none"),
        ],
        "engine",
    )

    action_hi_block = re.search(r'    "hi": \{\n        "unassessed".*?\n(?:.*\n)*?    \},\n', src).group(0)
    src = insert_dict_block(
        src,
        action_hi_block,
        [
            ("unassessed", "action_unassessed"),
            ("foundation", "action_foundation"),
            ("targeted", "action_targeted"),
        ],
        "engine",
    )

    method_hi_line = re.search(r'    "hi": ".*",\n\}\n\n\ndef _level_label', src).group(0)
    method_hi_line = method_hi_line.split("\n")[0] + "\n"
    src = insert_string_entries(src, method_hi_line, "engine.method_note")

    open(path, "w", encoding="utf-8").write(src)
    print(f"updated {path}")


def process_learning_analytics():
    path = os.path.join(BACKEND_DIR, "routes", "learning_analytics.py")
    src = open(path, encoding="utf-8").read()
    privacy_hi_line = re.search(r'    "hi": ".*",\n', src).group(0)
    src = insert_string_entries(src, privacy_hi_line, "analytics.privacy_note")
    open(path, "w", encoding="utf-8").write(src)
    print(f"updated {path}")


if __name__ == "__main__":
    process_learning_catalog()
    process_learning_engine()
    process_learning_analytics()
