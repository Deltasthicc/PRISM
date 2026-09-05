"""Direct Pydantic-validation tests for Lane 2-owned schema files that have
no route-level test exercising them (schemas/accuracy.py, schemas/question.py)
-- these are unit tests of the schema classes themselves, not of the routes
that happen to use them (which belong to Lane 5's own test files)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.accuracy import AccuracyHistoryResponse
from schemas.question import (
    QuestionFullResponse,
    QuestionGenerateRequest,
    QuestionResponse,
)


# --- schemas.accuracy.AccuracyHistoryResponse ---


def test_accuracy_history_response_accepts_a_full_valid_payload():
    response = AccuracyHistoryResponse(
        topic="arrays", attempts=10, correct=7, recent_accuracy=0.7,
        last_5_results=[True, True, False, True, False],
    )
    assert response.attempts == 10
    assert response.last_5_results == [True, True, False, True, False]


def test_accuracy_history_response_defaults_last_5_results_to_an_empty_list():
    # Field(default_factory=list) -- must be a fresh list per instance, not
    # a single shared mutable default every response object aliases.
    first = AccuracyHistoryResponse(topic="arrays", attempts=0, correct=0, recent_accuracy=0.0)
    second = AccuracyHistoryResponse(topic="graphs", attempts=0, correct=0, recent_accuracy=0.0)
    assert first.last_5_results == []
    first.last_5_results.append(True)
    assert second.last_5_results == []  # unaffected by mutating the other instance's list


def test_accuracy_history_response_rejects_a_non_numeric_recent_accuracy():
    with pytest.raises(ValidationError):
        AccuracyHistoryResponse(
            topic="arrays", attempts=1, correct=1, recent_accuracy="mostly good"
        )


def test_accuracy_history_response_reads_from_orm_attributes():
    class _FakeOrmRow:
        topic = "arrays"
        attempts = 3
        correct = 2
        recent_accuracy = 0.66
        last_5_results = [True, False, True]

    response = AccuracyHistoryResponse.model_validate(_FakeOrmRow())
    assert response.topic == "arrays"
    assert response.correct == 2


# --- schemas.question.QuestionGenerateRequest ---


def test_question_generate_request_applies_documented_defaults():
    request = QuestionGenerateRequest(player_id="p1", topic="arrays")
    assert request.difficulty == "medium"
    assert request.domain == "Data Structures & Algorithms"


def test_question_generate_request_accepts_an_explicit_difficulty_and_domain():
    request = QuestionGenerateRequest(
        player_id="p1", topic="sampling", difficulty="hard", domain="Official Statistics"
    )
    assert request.difficulty == "hard"
    assert request.domain == "Official Statistics"


def test_question_generate_request_requires_player_id_and_topic():
    with pytest.raises(ValidationError):
        QuestionGenerateRequest(topic="arrays")
    with pytest.raises(ValidationError):
        QuestionGenerateRequest(player_id="p1")


# --- schemas.question.QuestionResponse / QuestionFullResponse ---
# The split between these two schemas is a real security boundary (see
# schemas/question.py's own "expected_answer is intentionally NOT sent to
# the client" comment) -- these tests pin that boundary as an executable
# fact about the schema, not just a comment a future edit could silently
# invalidate.


def test_question_response_has_no_expected_answer_field():
    assert "expected_answer" not in QuestionResponse.model_fields


def test_question_response_silently_drops_an_expected_answer_key_from_orm_data():
    class _FakeOrmRow:
        question_id = "q1"
        question = "What is O(n log n)?"
        hint = None
        topic = "sorting"
        difficulty = "medium"
        expected_answer = "merge sort's complexity"  # must never surface

    response = QuestionResponse.model_validate(_FakeOrmRow())
    assert not hasattr(response, "expected_answer")
    assert "expected_answer" not in response.model_dump()


def test_question_full_response_does_include_expected_answer_field():
    assert "expected_answer" in QuestionFullResponse.model_fields


def test_question_full_response_requires_expected_answer():
    with pytest.raises(ValidationError):
        QuestionFullResponse(
            question_id="q1", question="text", topic="sorting", difficulty="medium"
        )
