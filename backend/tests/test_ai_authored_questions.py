"""services/ai_authored_questions.py -- the model-written counterpart to
services/hand_authored_questions.py. See that module's docstring for why the
two are kept separate: hand_authored_questions.json specifically claims
nothing in it is model-generated, so new AI-written items go here instead,
honestly labeled generation_mode="ai-source-grounded", while still being
held to the same non-negotiable check -- every doc_id must be real."""
import json

import pytest

import services.ai_authored_questions as ai_authored_questions
from services.ai_authored_questions import (
    GENERATION_MODE,
    _validate_ai_authored_item,
    ai_authored_doc_ids,
    questions_for_competency,
)
from services.competency_docs import all_documents
from services.curricula import CURRICULA

KNOWN_COMPETENCIES = {
    competency["id"]
    for curriculum in CURRICULA.values()
    for competency in curriculum["competencies"]
}


def _valid_item(**overrides) -> dict:
    item = {
        "item_id": "ai_test_item_1",
        "doc_id": "dpdp_act_2023",
        "competency_id": "dl_data_privacy",
        "difficulty": "easy",
        "bloom_level": "remember",
        "locator": "test",
        "source_excerpt": "irrelevant for this test",
        "question": "A placeholder question?",
        "options": ["A", "B", "C", "D"],
        "answer_index": 0,
        "explanation": "test",
    }
    item.update(overrides)
    return item


def test_generation_mode_is_honestly_distinct_from_hand_transcribed():
    assert GENERATION_MODE == "ai-source-grounded"
    assert GENERATION_MODE != "hand-transcribed"


def test_every_ai_authored_doc_id_is_a_real_corpus_document():
    corpus_ids = {doc["doc_id"] for doc in all_documents()}
    assert ai_authored_doc_ids() <= corpus_ids


def test_every_ai_authored_competency_id_is_a_known_competency():
    # questions_for_competency() only filters; walk every known competency so
    # an item with a typo'd competency_id (silently never served) is caught.
    from services.ai_authored_questions import _all_questions

    seen = {
        item["item_id"]
        for competency_id in KNOWN_COMPETENCIES
        for item in questions_for_competency(competency_id)
    }
    assert seen == {item["item_id"] for item in _all_questions()}


def test_validate_rejects_unknown_doc_id():
    with pytest.raises(ValueError, match="not in document_corpus.json"):
        _validate_ai_authored_item(_valid_item(doc_id="not-a-real-doc-id"))


def test_loader_rejects_item_id_without_ai_prefix(tmp_path, monkeypatch):
    # Enforced in _all_questions() (a whole-file invariant), not per-item
    # validation -- exercise it through a scratch file so the two id
    # namespaces (hand-authored "ha_", ai-authored "ai_") can never collide.
    bad_path = tmp_path / "ai_authored_questions.json"
    bad_path.write_text(
        json.dumps({"questions": [_valid_item(item_id="ha_wrong_prefix")]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(ai_authored_questions, "QUESTIONS_PATH", bad_path)
    monkeypatch.setattr(ai_authored_questions, "_questions_cache", None)

    with pytest.raises(ValueError, match="prefixed 'ai_'"):
        ai_authored_questions._all_questions()


def test_validate_rejects_bad_difficulty():
    with pytest.raises(ValueError, match="difficulty"):
        _validate_ai_authored_item(_valid_item(difficulty="impossible"))


def test_validate_rejects_wrong_option_count():
    with pytest.raises(ValueError, match="exactly 4"):
        _validate_ai_authored_item(_valid_item(options=["A", "B"]))


def test_validate_rejects_out_of_range_answer_index():
    with pytest.raises(ValueError, match="out of range"):
        _validate_ai_authored_item(_valid_item(answer_index=7))


def test_validate_rejects_missing_required_field():
    item = _valid_item()
    del item["explanation"]
    with pytest.raises(ValueError, match="missing fields"):
        _validate_ai_authored_item(item)


def test_validate_fill_in_blank_requires_blank_marker():
    item = _valid_item(
        question_type="fill_in_blank",
        question="No marker here.",
        accepted_answers=["something"],
    )
    del item["options"]
    del item["answer_index"]
    with pytest.raises(ValueError, match="blank marker"):
        _validate_ai_authored_item(item)


def test_validate_fill_in_blank_requires_nonempty_accepted_answers():
    item = _valid_item(
        question_type="fill_in_blank",
        question="Has a _____ marker.",
        accepted_answers=[],
    )
    del item["options"]
    del item["answer_index"]
    with pytest.raises(ValueError, match="accepted_answers"):
        _validate_ai_authored_item(item)
