"""Tests for backend/labs/sampling_lab.py -- Lane 3's PS-08 deliverable:
"one bounded CPI, sampling or data-quality lab with deterministic expected
output" (SIH26101_TEAM_ORCHESTRATION.md section 5).

Acceptance evidence being proven here (same section): "The lab has resource
bounds, learning feedback and no arbitrary code execution on the API host."
"""
import pytest

from labs.sampling_lab import (
    COMPETENCY_ID,
    LAB_ID,
    LAB_VERSION,
    MAX_ANSWER,
    TASKS,
    LabInputError,
    evaluate_submission,
    evidence_payload,
    expected_answer,
    list_tasks,
)
from services.behavioral_anchors import BEHAVIORAL_ANCHORS
from services.curricula import CURRICULA


# ─── determinism: the exact expected outputs, pinned ───

def test_simple_sample_size_expected_value():
    # z=1.96, p=0.5, e=0.05 -> 3.8416 * 0.25 / 0.0025 = 384.16 -> ceil 385
    expected, steps = expected_answer("srs-basic")
    assert expected == 385
    assert len(steps) == 3


def test_finite_population_correction_expected_value():
    # 384.16 / (1 + 383.16/50000) = 381.24 -> ceil 382
    expected, steps = expected_answer("srs-finite-population")
    assert expected == 382
    # FPC must reduce the required sample below the uncorrected figure.
    assert expected < expected_answer("srs-basic")[0]
    assert len(steps) == 4


def test_proportional_allocation_expected_value():
    # 1200 * (45000/100000) = 540
    expected, _ = expected_answer("proportional-allocation")
    assert expected == 540


def test_expected_answer_is_stable_across_calls():
    # "Deterministic expected output" -- same task, same number, every time.
    assert expected_answer("srs-basic")[0] == expected_answer("srs-basic")[0]
    assert expected_answer("srs-finite-population")[0] == 382


# ─── grading and learning feedback ───

def test_correct_submission_yields_evidence_at_the_task_level():
    result = evaluate_submission("srs-basic", 385)
    assert result["correct"] is True
    assert result["demonstrated_level"] == TASKS["srs-basic"]["demonstrated_level"]
    assert result["evidence"] == {
        "competency_id": COMPETENCY_ID,
        "evidence_type": "observed_practice",
        "value": 2,
        "detail": f"{LAB_ID}:srs-basic",
    }
    assert result["lab_version"] == LAB_VERSION


def test_wrong_submission_records_no_evidence():
    # A failed attempt must never become a recorded low-ability judgment
    # (CLAUDE.md architectural invariant #3).
    result = evaluate_submission("srs-basic", 100)
    assert result["correct"] is False
    assert result["evidence"] is None
    assert result["demonstrated_level"] is None


def test_steps_are_returned_even_when_wrong():
    # The learning feedback is the point of a lab, not the verdict.
    result = evaluate_submission("srs-basic", 100)
    assert len(result["steps"]) == 3
    assert "too small" in result["feedback"].lower()


def test_oversized_submission_is_flagged_as_wasteful_not_wrong_math():
    result = evaluate_submission("srs-basic", 900)
    assert result["correct"] is False
    assert "larger than required" in result["feedback"].lower()


def test_tolerance_accepts_off_by_one_rounding():
    # 384 vs the exact 385 is a rounding convention difference, not a
    # misunderstanding of the formula.
    assert evaluate_submission("srs-basic", 384)["correct"] is True
    assert evaluate_submission("srs-basic", 383)["correct"] is False


# ─── bounds and safety (no code execution, nothing unbounded) ───

def test_rejects_non_numeric_submission():
    with pytest.raises(LabInputError, match="must be a number"):
        evaluate_submission("srs-basic", "385; import os")


def test_rejects_boolean_submission():
    # bool is an int subclass in Python -- must not sneak through as 0/1.
    with pytest.raises(LabInputError, match="must be a number"):
        evaluate_submission("srs-basic", True)


def test_rejects_infinite_and_nan_submissions():
    with pytest.raises(LabInputError, match="finite"):
        evaluate_submission("srs-basic", float("inf"))
    with pytest.raises(LabInputError, match="finite"):
        evaluate_submission("srs-basic", float("nan"))


def test_rejects_out_of_range_submissions():
    with pytest.raises(LabInputError, match="between 0"):
        evaluate_submission("srs-basic", MAX_ANSWER + 1)
    with pytest.raises(LabInputError, match="between 0"):
        evaluate_submission("srs-basic", -5)


def test_rejects_unknown_task():
    with pytest.raises(LabInputError, match="Unknown lab task"):
        evaluate_submission("not-a-real-task", 385)
    with pytest.raises(LabInputError, match="Unknown lab task"):
        expected_answer("not-a-real-task")


def test_list_tasks_never_leaks_expected_answers():
    for task in list_tasks():
        assert "expected" not in task
        assert "parameters" not in task
        assert task["competency_id"] == COMPETENCY_ID


# ─── taxonomy linkage: the lab must attach to a real competency ───

def test_lab_competency_exists_in_the_curriculum():
    official_statistics_ids = {item["id"] for item in CURRICULA["official-statistics"]["competencies"]}
    assert COMPETENCY_ID in official_statistics_ids


def test_every_task_level_has_a_behavioral_anchor():
    # A task claiming to demonstrate level N is only meaningful if level N is
    # actually defined for this competency.
    for task in TASKS.values():
        assert task["demonstrated_level"] in BEHAVIORAL_ANCHORS[COMPETENCY_ID]


def test_basic_task_matches_its_level_2_anchor():
    # The srs-basic task exists specifically to test os_sampling_design's
    # level 2 anchor text; if that anchor is reworded away from sample-size
    # calculation, this task needs revisiting too.
    anchor = BEHAVIORAL_ANCHORS[COMPETENCY_ID][2]["descriptor"].lower()
    assert "sample size" in anchor
    assert TASKS["srs-basic"]["demonstrated_level"] == 2


def test_evidence_payload_shape_matches_lane_2_evidence_record():
    payload = evidence_payload("proportional-allocation")
    assert set(payload) == {"competency_id", "evidence_type", "value", "detail"}
    # "observed_practice" is one of Lane 2's EVIDENCE_TYPES and the same
    # vocabulary learning_engine.py's evidence_sources uses.
    assert payload["evidence_type"] == "observed_practice"
