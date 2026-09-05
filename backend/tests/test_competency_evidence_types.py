"""Tests for separated evidence types across the five storage kinds.

SIH26101_TEAM_ORCHESTRATION.md section 5, Lane 3 next package: "Separate
self-report, diagnostic, observed-practice, reviewer and provider evidence."
The requirement is *separation*, not blending -- there are no validated
weights for the three non-scoring types, so they are recorded and shown
individually while deliberately leaving observed_level alone.
"""
import pytest

from models.governance import EVIDENCE_TYPES
from services.learning_engine import (
    ASSESSMENT_POLICY_VERSION,
    EVIDENCE_TYPE_ORDER,
    SCORING_EVIDENCE_TYPES,
    UNSCORED_EVIDENCE_TYPES,
    analyse_competencies,
)


def _row(result, competency_id):
    return next(c for c in result["competencies"] if c["competency_id"] == competency_id)


# ─── vocabulary stays aligned with Lane 2's storage layer ───

def test_engine_covers_exactly_lane_2s_evidence_vocabulary():
    # If Lane 2 adds a sixth type, this fails rather than silently ignoring it.
    assert set(EVIDENCE_TYPE_ORDER) == set(EVIDENCE_TYPES)
    assert set(SCORING_EVIDENCE_TYPES) | set(UNSCORED_EVIDENCE_TYPES) == set(EVIDENCE_TYPES)
    assert not set(SCORING_EVIDENCE_TYPES) & set(UNSCORED_EVIDENCE_TYPES)


# ─── separation: each type visible on its own ───

def test_each_evidence_type_is_reported_separately():
    result = analyse_competencies(
        "official-statistics", {}, {}, "expert",
        evidence={
            "os_data_quality": {
                "self_report": {"value": 2, "recorded_at": "2026-09-01T00:00:00+00:00", "detail": ""},
                "reviewer": {"value": None, "recorded_at": "2026-09-02T00:00:00+00:00", "detail": "Panel note"},
                "provider_imported": {"value": 3, "recorded_at": None, "detail": "iGOT completion"},
            }
        },
    )
    row = _row(result, "os_data_quality")
    by_type = {r["evidence_type"]: r for r in row["evidence_records"]}
    assert set(by_type) == {"self_report", "reviewer", "provider_imported"}
    assert by_type["reviewer"]["value"] is None          # qualitative note, not a zero
    assert by_type["reviewer"]["detail"] == "Panel note"
    assert by_type["provider_imported"]["scored"] is False
    assert by_type["self_report"]["scored"] is True


def test_unscored_evidence_does_not_move_the_score():
    scored_only = analyse_competencies(
        "official-statistics", {"os_data_quality": 2.0}, {}, "expert",
    )
    with_extra = analyse_competencies(
        "official-statistics", {"os_data_quality": 2.0}, {}, "expert",
        evidence={
            "os_data_quality": {
                "reviewer": {"value": 5, "recorded_at": None, "detail": ""},
                "diagnostic": {"value": 5, "recorded_at": None, "detail": ""},
            }
        },
    )
    # Reviewer and diagnostic both claiming 5 must not drag the level upward
    # while their weights are unvalidated.
    assert _row(scored_only, "os_data_quality")["observed_level"] == _row(with_extra, "os_data_quality")["observed_level"]
    assert _row(with_extra, "os_data_quality")["gap"] == _row(scored_only, "os_data_quality")["gap"]


# ─── invariant #3 under the new types ───

def test_only_unscored_evidence_still_reads_as_unassessed():
    # A learner carrying just a qualitative reviewer note has evidence but no
    # rating. Deriving "critical" from a 0.0 placeholder would be exactly the
    # unsupported low-ability judgment CLAUDE.md invariant #3 forbids.
    result = analyse_competencies(
        "official-statistics", {}, {}, "beginner",
        evidence={"os_ml": {"reviewer": {"value": None, "recorded_at": None, "detail": "Observed in review"}}},
    )
    row = _row(result, "os_ml")
    assert row["has_evidence"] is True            # something is on file
    assert row["has_scored_evidence"] is False    # but nothing rateable
    assert row["priority"] == "unassessed"
    assert row["observed_level"] == 0.0
    assert "not scored" in row["evidence"]
    assert ASSESSMENT_POLICY_VERSION in row["evidence"]


def test_no_evidence_state_is_reserved_for_genuinely_nothing():
    result = analyse_competencies(
        "official-statistics", {}, {}, "beginner",
        evidence={"os_ml": {"diagnostic": {"value": None, "recorded_at": None, "detail": "scheduled"}}},
    )
    assert _row(result, "os_ml")["evidence_state"] is None       # something on file
    assert _row(result, "os_gis")["evidence_state"] == "NO EVIDENCE"  # truly nothing


# ─── stored rows outrank the legacy arguments ───

def test_stored_evidence_row_overrides_the_legacy_argument():
    result = analyse_competencies(
        "official-statistics", {"os_data_quality": 1.0}, {}, "expert",
        evidence={"os_data_quality": {"self_report": {"value": 4, "recorded_at": None, "detail": ""}}},
    )
    # The auditable EvidenceRecord wins over the loose self_ratings input.
    assert _row(result, "os_data_quality")["observed_level"] == 4.0


def test_null_valued_row_does_not_override_a_real_argument():
    result = analyse_competencies(
        "official-statistics", {"os_data_quality": 3.0}, {}, "expert",
        evidence={"os_data_quality": {"self_report": {"value": None, "recorded_at": None, "detail": ""}}},
    )
    assert _row(result, "os_data_quality")["observed_level"] == 3.0


# ─── confidence and validation ───

def test_confidence_rises_above_low_when_a_stronger_type_exists():
    result = analyse_competencies(
        "official-statistics", {"os_data_quality": 2.0}, {}, "expert",
        evidence={"os_data_quality": {"diagnostic": {"value": 3, "recorded_at": None, "detail": ""}}},
    )
    assert _row(result, "os_data_quality")["confidence"] == "moderate"


def test_confidence_still_never_claims_high():
    result = analyse_competencies(
        "official-statistics", {"os_data_quality": 5.0}, {"os_data_quality": 5.0}, "expert",
        evidence={
            "os_data_quality": {t: {"value": 5, "recorded_at": None, "detail": ""} for t in EVIDENCE_TYPES}
        },
    )
    assert all(c["confidence"] != "high" for c in result["competencies"])


def test_evidence_outside_the_curriculum_is_rejected():
    with pytest.raises(ValueError, match="Evidence contains competencies outside"):
        analyse_competencies(
            "official-statistics", {}, {}, "beginner",
            evidence={"arrays": {"self_report": {"value": 3, "recorded_at": None, "detail": ""}}},
        )


def test_method_block_declares_which_types_are_scored():
    method = analyse_competencies("official-statistics", {}, {}, "beginner")["method"]
    assert method["scored_evidence_types"] == list(SCORING_EVIDENCE_TYPES)
    assert method["recorded_unscored_evidence_types"] == list(UNSCORED_EVIDENCE_TYPES)
    assert "does not move observed_level" in method["unscored_note"]
