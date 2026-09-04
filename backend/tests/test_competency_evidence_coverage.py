"""Tests for evidence-coverage labeling in services/learning_engine.py --
CLAUDE.md architectural invariant #3: "'No evidence' never means low
competency." A competency with zero self-rating and zero measured score must
be distinguishable from one that was actually assessed and scored low.
"""
from services.learning_engine import ASSESSMENT_POLICY_VERSION, analyse_competencies


def test_no_evidence_yields_unassessed_priority_not_critical():
    # Beginner, nothing rated, nothing measured -- os_ml has a large role
    # target (5) so its gap would be "critical" under gap-only logic. It
    # must instead read as "unassessed", never a demonstrated failure.
    result = analyse_competencies("official-statistics", {}, {}, "beginner")
    row = next(r for r in result["competencies"] if r["competency_id"] == "os_ml")
    assert row["has_evidence"] is False
    assert row["evidence_sources"] == []
    assert row["priority"] == "unassessed"
    assert row["gap"] > 0  # gap is still computed and still drives sort order


def test_self_report_only_still_gets_gap_based_priority():
    result = analyse_competencies(
        "official-statistics",
        self_ratings={"os_ml": 0.5},
        measured_scores={},
        experience_level="expert",
    )
    row = next(r for r in result["competencies"] if r["competency_id"] == "os_ml")
    assert row["has_evidence"] is True
    assert row["evidence_sources"] == ["self_report"]
    assert row["priority"] != "unassessed"
    assert row["priority"] == "critical"  # gap of 4.5 on a 0-5 scale


def test_measured_only_evidence_labeled_observed_practice():
    result = analyse_competencies(
        "official-statistics",
        self_ratings={},
        measured_scores={"os_statistical_foundations": 3.0},
        experience_level="beginner",
    )
    row = next(r for r in result["competencies"] if r["competency_id"] == "os_statistical_foundations")
    assert row["evidence_sources"] == ["observed_practice"]
    assert row["has_evidence"] is True


def test_both_sources_present_preserves_order():
    result = analyse_competencies(
        "official-statistics",
        self_ratings={"os_statistical_foundations": 4.0},
        measured_scores={"os_statistical_foundations": 2.0},
        experience_level="beginner",
    )
    row = next(r for r in result["competencies"] if r["competency_id"] == "os_statistical_foundations")
    assert row["evidence_sources"] == ["observed_practice", "self_report"]


def test_policy_version_is_exposed_and_versioned():
    result = analyse_competencies("official-statistics", {}, {}, "beginner")
    assert result["method"]["policy_version"] == ASSESSMENT_POLICY_VERSION
    assert ASSESSMENT_POLICY_VERSION == "prototype-v1"


def test_unassessed_items_still_appear_in_skill_gaps_and_pathway():
    # Option B from the design discussion: unassessed items are recolored,
    # not dropped -- they must remain visible as "go get assessed" action
    # items, not silently disappear from the pathway.
    result = analyse_competencies("official-statistics", {}, {}, "beginner")
    unassessed_ids = {r["competency_id"] for r in result["competencies"] if r["priority"] == "unassessed"}
    assert unassessed_ids  # every competency is unassessed with no input at all
    pathway_ids = {step["competency_id"] for step in result["pathway"]}
    assert unassessed_ids & pathway_ids


def test_unassessed_pathway_step_recommends_a_baseline_diagnostic():
    result = analyse_competencies("official-statistics", {}, {}, "beginner")
    unassessed_step = next(step for step in result["pathway"] if step["priority"] == "unassessed")
    assert "baseline" in unassessed_step["recommended_action"].lower()
    assert "foundation module" not in unassessed_step["recommended_action"].lower()
