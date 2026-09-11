"""AI-authored MCQs grounded in the same hash-verified corpus as
services.hand_authored_questions, added to reach a practical per-competency
question count without waiting on a human transcriber for every item.

This is a deliberately distinct pool from hand_authored_questions.json.
That file's own docstring makes a specific, load-bearing claim -- "Nothing
here is model-generated" -- backed by tests
(test_competency_hand_authored.py) that pin its exact doc_id set and
provenance. Mixing AI-authored items into that file, or reusing its
generation_mode value, would make that claim false. Every item here instead
carries generation_mode="ai-source-grounded": written by a model, but citing
a real doc_id that must exist in data/document_corpus.json (validated below,
same enforcement as the hand-authored loader), with a source_excerpt grounded
in that document's actual, verifiable subject matter -- not independently
transcribed against page images the way the UPSC items are, and not claiming
to be. Status stays DRAFT pending human review, same as the hand-authored
bank and for the same reason (CLAUDE.md invariant 9).

Item shape mirrors hand_authored_questions.py exactly (same "mcq"/
"fill_in_blank" question_type split, same required fields) so
routes/competency_quiz.py can merge both pools transparently. item_id here
is always prefixed "ai_" (vs. hand-authored's "ha_") so the two pools can
never collide on id even though both loaders build their own separate
duplicate-item-id/duplicate-question-text checks independently -- see
tests/test_ai_authored_questions.py for the cross-pool check.

Content is split across multiple ai_authored_questions*.json files (one per
authoring batch/curriculum-slice) rather than one ever-growing array, purely
so independent batches can be added as separate, non-conflicting PRs -- two
branches both appending to the same JSON array's tail produce a merge
conflict on every subsequent PR, while two branches each adding their own
new file merge cleanly. All matching files are loaded and validated together
below; there is no meaning to which file a given item lives in beyond that.
"""
from __future__ import annotations

import json
from pathlib import Path

from services.competency_docs import get_document

DATA_DIRECTORY = Path(__file__).resolve().parent.parent / "data"
QUESTIONS_GLOB = "ai_authored_questions*.json"

GENERATION_MODE = "ai-source-grounded"

_COMMON_REQUIRED_FIELDS = {
    "item_id", "doc_id", "competency_id", "difficulty", "bloom_level",
    "locator", "source_excerpt", "question", "explanation",
}
_MCQ_REQUIRED_FIELDS = {"options", "answer_index"}
_FILL_IN_BLANK_REQUIRED_FIELDS = {"accepted_answers"}
_QUESTION_TYPES = {"mcq", "fill_in_blank"}

_questions_cache: list[dict] | None = None


def _all_questions() -> list[dict]:
    global _questions_cache
    if _questions_cache is None:
        questions: list[dict] = []
        for path in sorted(DATA_DIRECTORY.glob(QUESTIONS_GLOB)):
            with path.open(encoding="utf-8") as handle:
                payload = json.load(handle)
            questions.extend(payload["questions"])
        for item in questions:
            item.setdefault("question_type", "mcq")
            item["generation_mode"] = GENERATION_MODE
            _validate_ai_authored_item(item)
        item_ids = [item["item_id"] for item in questions]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("ai_authored_questions*.json files contain duplicate item_id values")
        if any(not item_id.startswith("ai_") for item_id in item_ids):
            raise ValueError("ai_authored_questions*.json item_id values must be prefixed 'ai_'")
        normalized_text = [" ".join(item["question"].lower().split()) for item in questions]
        if len(normalized_text) != len(set(normalized_text)):
            raise ValueError("ai_authored_questions*.json files contain duplicate question text")
        _questions_cache = questions
    return _questions_cache


def _validate_ai_authored_item(item: dict) -> None:
    """Same "fail loudly at load time" posture as
    hand_authored_questions._validate_hand_authored_item(), including the
    same non-negotiable check: doc_id must be a real entry in
    document_corpus.json, so every citation here is checkable against a
    real, hash-verified record."""
    question_type = item.get("question_type", "mcq")
    if question_type not in _QUESTION_TYPES:
        raise ValueError(f"{item.get('item_id')}: question_type must be one of {_QUESTION_TYPES}")
    type_fields = _MCQ_REQUIRED_FIELDS if question_type == "mcq" else _FILL_IN_BLANK_REQUIRED_FIELDS
    missing = (_COMMON_REQUIRED_FIELDS | type_fields) - item.keys()
    if missing:
        raise ValueError(f"ai_authored_questions.json item {item.get('item_id')!r} missing fields: {missing}")
    if question_type == "mcq":
        if len(item["options"]) != 4:
            raise ValueError(f"{item['item_id']}: options must have exactly 4 entries")
        if not 0 <= item["answer_index"] < 4:
            raise ValueError(f"{item['item_id']}: answer_index out of range")
    else:
        if not item["accepted_answers"] or not all(isinstance(a, str) and a.strip() for a in item["accepted_answers"]):
            raise ValueError(f"{item['item_id']}: accepted_answers must be a non-empty list of non-empty strings")
        if "_____" not in item["question"]:
            raise ValueError(f"{item['item_id']}: fill_in_blank question must contain a '_____' blank marker")
    if item["difficulty"] not in {"easy", "medium", "hard"}:
        raise ValueError(f"{item['item_id']}: difficulty must be easy|medium|hard")
    if get_document(item["doc_id"]) is None:
        raise ValueError(f"{item['item_id']}: doc_id {item['doc_id']!r} is not in document_corpus.json")


def ai_authored_doc_ids() -> set[str]:
    return {item["doc_id"] for item in _all_questions()}


def questions_for_competency(competency_id: str) -> list[dict]:
    return [item for item in _all_questions() if item["competency_id"] == competency_id]
