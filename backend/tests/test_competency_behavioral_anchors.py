"""Tests for services/behavioral_anchors.py and its wiring into
services/learning_engine.py -- Lane 3's "sourced MoSPI pilot taxonomy with
competency-specific L1-L5 behavioural anchors" deliverable
(SIH26101_TEAM_ORCHESTRATION.md section 5, Lane 3 immediate package).

Anchors are per-item records ({descriptor, source, status, reviewed_by,
version}), not a single blanket note for the whole file -- per the same
section's Lane 3 acceptance evidence: "Every competency/target has source,
authoring status and version." This lets a future domain reviewer approve
one anchor at a time without a data-model change.
"""
from services.behavioral_anchors import (
    ANCHORED_CURRICULUM,
    BEHAVIORAL_ANCHORS,
    DEFAULT_SOURCE,
    DEFAULT_STATUS,
    get_anchor,
    unanchored_competencies,
    validate_anchors,
)
from services.curricula import CURRICULA
from services.learning_engine import analyse_competencies


# ─── behavioral_anchors.py ───

def test_validate_anchors_passes_on_reimport():
    # Already ran once at module import time; re-running must never raise.
    validate_anchors()


def test_every_anchor_points_at_a_real_competency():
    # Coverage may be partial, but never wrong -- an anchor for an ID outside
    # the anchored curriculum means curricula.py and this file have drifted.
    official_statistics_ids = {item["id"] for item in CURRICULA[ANCHORED_CURRICULUM]["competencies"]}
    assert set(BEHAVIORAL_ANCHORS) <= official_statistics_ids


def test_the_canonical_demo_competencies_are_all_anchored():
    # The three-minute judge path runs on these nine; they must stay anchored
    # even as PS-02 breadth competencies are added around them.
    canonical = {
        "os_statistical_foundations",
        "os_data_collection",
        "os_sampling_design",
        "os_data_quality",
        "os_official_statistics",
        "os_visualization",
        "os_gis",
        "os_big_data",
        "os_ml",
    }
    assert canonical <= set(BEHAVIORAL_ANCHORS)


def test_unanchored_competencies_are_reported_not_hidden():
    unanchored = unanchored_competencies()
    # PS-02 breadth added competencies without anchor prose; that gap must be
    # inspectable rather than silently absent.
    assert "os_price_statistics" in unanchored
    assert all(cid not in BEHAVIORAL_ANCHORS for cid in unanchored)


def test_every_anchor_record_has_source_status_version():
    # Direct check of the acceptance-evidence requirement, not just the
    # validator's own internal logic.
    for competency_id, levels in BEHAVIORAL_ANCHORS.items():
        for level, record in levels.items():
            assert record["descriptor"].strip(), f"{competency_id} level {level} missing descriptor"
            assert record["source"] == DEFAULT_SOURCE
            assert record["status"] == DEFAULT_STATUS
            assert record["version"] >= 1
            assert record["reviewed_by"] is None  # nothing has been reviewed yet


def test_get_anchor_rounds_half_up():
    assert get_anchor("os_sampling_design", 3.5)["descriptor"] == BEHAVIORAL_ANCHORS["os_sampling_design"][4]["descriptor"]
    assert get_anchor("os_sampling_design", 2.4)["descriptor"] == BEHAVIORAL_ANCHORS["os_sampling_design"][2]["descriptor"]


def test_get_anchor_clamps_to_five():
    assert get_anchor("os_data_quality", 6.0)["descriptor"] == BEHAVIORAL_ANCHORS["os_data_quality"][5]["descriptor"]


def test_get_anchor_returns_none_below_one():
    # Nothing observed yet -- there's nothing to describe.
    assert get_anchor("os_data_quality", 0.4) is None


def test_get_anchor_returns_none_for_uncovered_curriculum():
    # "arrays" is a real DSA competency, just not one this module covers yet.
    assert get_anchor("arrays", 3.0) is None


def test_get_anchor_returns_a_copy_not_the_canonical_record():
    record = get_anchor("os_gis", 3.0)
    record["descriptor"] = "mutated"
    assert BEHAVIORAL_ANCHORS["os_gis"][3]["descriptor"] != "mutated"


# ─── learning_engine.py wiring ───

def test_analyse_competencies_includes_anchor_records_for_official_statistics():
    result = analyse_competencies(
        "official-statistics",
        self_ratings={"os_sampling_design": 4.0},
        measured_scores={},
        experience_level="expert",
    )
    row = next(r for r in result["competencies"] if r["competency_id"] == "os_sampling_design")
    assert row["observed_anchor"]["descriptor"] == BEHAVIORAL_ANCHORS["os_sampling_design"][4]["descriptor"]
    assert row["observed_anchor"]["source"] == DEFAULT_SOURCE
    assert row["observed_anchor"]["status"] == DEFAULT_STATUS
    assert row["target_anchor"] is not None


def test_analyse_competencies_omits_anchors_outside_coverage():
    result = analyse_competencies("dsa-fundamentals", {"arrays": 4.0}, {}, "expert")
    assert ANCHORED_CURRICULUM != "dsa-fundamentals"
    assert all(r["observed_anchor"] is None for r in result["competencies"])
    assert all(r["target_anchor"] is None for r in result["competencies"])


def test_unassessed_competency_has_no_observed_anchor():
    # No evidence -- observed_level is 0, so there is nothing to describe yet,
    # even though this curriculum has anchor coverage.
    result = analyse_competencies("official-statistics", {}, {}, "beginner")
    row = next(r for r in result["competencies"] if r["competency_id"] == "os_data_quality")
    assert row["priority"] == "unassessed"
    assert row["observed_anchor"] is None
    # The target itself is still known and describable, even without evidence.
    assert row["target_anchor"] is not None


def test_method_exposes_anchor_defaults():
    result = analyse_competencies("official-statistics", {}, {}, "beginner")
    assert result["method"]["behavioral_anchor_default_source"] == DEFAULT_SOURCE
    assert result["method"]["behavioral_anchor_default_status"] == DEFAULT_STATUS
    assert DEFAULT_STATUS == "unreviewed-pending-domain-expert"
