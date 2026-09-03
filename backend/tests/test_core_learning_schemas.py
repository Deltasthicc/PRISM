"""Direct Pydantic-validation tests for schemas/learning.py -- no route-level
test in this repo currently exercises its validators (bounded lists, capped
self-ratings, the experience_level enum pattern) directly, so a regression
in any of them would only surface as a route returning an unexpected 422,
not as a focused failure naming which rule broke."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemas.learning import (
    CompetencyAssessmentRequest,
    LearnerProfileUpsert,
    QuizQuestion,
    QuizResponse,
)


# --- LearnerProfileUpsert defaults ---


def test_learner_profile_upsert_applies_all_documented_defaults():
    profile = LearnerProfileUpsert()
    assert profile.designation == ""
    assert profile.years_experience == 0
    assert profile.previous_trainings == []
    assert profile.preferred_language == "English"
    assert profile.experience_level == "beginner"
    assert profile.target_domains == []


# --- years_experience bounds (Field(0, ge=0, le=60)) ---


@pytest.mark.parametrize("years", [0, 30, 60])
def test_years_experience_accepts_the_documented_range(years):
    assert LearnerProfileUpsert(years_experience=years).years_experience == years


@pytest.mark.parametrize("years", [-1, 61])
def test_years_experience_rejects_outside_the_documented_range(years):
    with pytest.raises(ValidationError):
        LearnerProfileUpsert(years_experience=years)


# --- experience_level pattern ---


@pytest.mark.parametrize("level", ["beginner", "intermediate", "advanced", "expert"])
def test_experience_level_accepts_every_documented_value(level):
    assert LearnerProfileUpsert(experience_level=level).experience_level == level


def test_experience_level_rejects_a_value_outside_the_enum_pattern():
    with pytest.raises(ValidationError):
        LearnerProfileUpsert(experience_level="master")


# --- _bounded_list validator (previous_trainings, target_domains) ---


def test_bounded_list_strips_whitespace_and_drops_blank_entries():
    profile = LearnerProfileUpsert(previous_trainings=["  Python  ", "", "   ", "SQL"])
    assert profile.previous_trainings == ["Python", "SQL"]


def test_bounded_list_rejects_more_than_forty_entries():
    with pytest.raises(ValidationError, match="too many entries"):
        LearnerProfileUpsert(target_domains=[f"domain-{i}" for i in range(41)])


def test_bounded_list_accepts_exactly_forty_entries():
    profile = LearnerProfileUpsert(target_domains=[f"domain-{i}" for i in range(40)])
    assert len(profile.target_domains) == 40


def test_bounded_list_applies_independently_to_both_list_fields():
    # A regression that accidentally shared validator state (e.g. a mutable
    # default, or a validator that only ran once per class) would show up
    # as one field's entries leaking into or capping the other.
    profile = LearnerProfileUpsert(
        previous_trainings=["a", "b"], target_domains=["x", "y", "z"]
    )
    assert profile.previous_trainings == ["a", "b"]
    assert profile.target_domains == ["x", "y", "z"]


# --- CompetencyAssessmentRequest ---


def test_competency_assessment_request_requires_a_curriculum_slug_of_minimum_length():
    with pytest.raises(ValidationError):
        CompetencyAssessmentRequest(curriculum_slug="a")  # below min_length=2


def test_competency_assessment_request_rejects_a_curriculum_slug_over_max_length():
    with pytest.raises(ValidationError):
        CompetencyAssessmentRequest(curriculum_slug="x" * 121)


def test_competency_assessment_request_accepts_valid_self_ratings():
    request = CompetencyAssessmentRequest(
        curriculum_slug="official-statistics", self_ratings={"survey-design": 3.5, "sampling": 0}
    )
    assert request.self_ratings["survey-design"] == 3.5


@pytest.mark.parametrize("bad_score", [-0.1, 5.1, -10, 100])
def test_competency_assessment_request_rejects_a_self_rating_outside_zero_to_five(bad_score):
    with pytest.raises(ValidationError, match="between 0 and 5"):
        CompetencyAssessmentRequest(
            curriculum_slug="official-statistics", self_ratings={"survey-design": bad_score}
        )


def test_competency_assessment_request_rejects_more_than_one_hundred_self_ratings():
    with pytest.raises(ValidationError, match="Too many self-ratings"):
        CompetencyAssessmentRequest(
            curriculum_slug="official-statistics",
            self_ratings={f"competency-{i}": 1.0 for i in range(101)},
        )


def test_competency_assessment_request_defaults_self_ratings_to_an_empty_dict():
    first = CompetencyAssessmentRequest(curriculum_slug="official-statistics")
    second = CompetencyAssessmentRequest(curriculum_slug="public-policy")
    assert first.self_ratings == {}
    first.self_ratings["x"] = 1.0
    assert second.self_ratings == {}  # not a shared mutable default


# --- QuizQuestion / QuizResponse construction ---


def test_quiz_question_requires_every_field():
    with pytest.raises(ValidationError):
        QuizQuestion(question="What is O(n)?", options=["a", "b"], answer_index=0)


def test_quiz_response_round_trips_a_full_valid_payload():
    quiz = QuizResponse(
        quiz_id="quiz-1",
        material_id="mat-1",
        title="Arrays quiz",
        difficulty="medium",
        language="en",
        generation_mode="cited",
        questions=[
            QuizQuestion(
                question="What is O(n)?", options=["linear", "log"], answer_index=0,
                explanation="Because...", source_excerpt="...", competency="arrays",
                bloom_level="remember",
            )
        ],
    )
    assert len(quiz.questions) == 1
    assert quiz.questions[0].answer_index == 0
