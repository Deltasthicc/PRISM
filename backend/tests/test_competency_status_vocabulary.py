"""Guards the fixed status vocabulary across every Lane 3 output.

CODEX.md and CLAUDE.md architectural invariants both require SIMULATED,
CATALOGUE, LIVE, PROVISIONAL and NO EVIDENCE to be used "precisely", and
SIH26101_TEAM_ORCHESTRATION.md section 5 puts Lane 1 on the hook to render
exactly those states. Lane 3 therefore must not invent near-miss spellings
("provisional", "no_evidence", "unreviewed") in the fields Lane 1 reads --
these tests fail if it starts to.
"""
from labs.sampling_lab import LEVEL_CLAIM_ASSURANCE, evaluate_submission, list_tasks
from services.behavioral_anchors import BEHAVIORAL_ANCHORS, get_anchor
from services.curricula import CURRICULA, public_curricula
from services.learning_engine import NO_EVIDENCE, analyse_competencies

# The exact spellings the docs fix. Lane 3 only ever emits two of these
# (PROVISIONAL, NO EVIDENCE); the provider-status three belong to Lane 5.
DOCUMENTED_STATES = {"SIMULATED", "CATALOGUE", "LIVE", "PROVISIONAL", "NO EVIDENCE"}


def test_no_evidence_uses_the_documented_spelling():
    assert NO_EVIDENCE == "NO EVIDENCE"
    assert NO_EVIDENCE in DOCUMENTED_STATES


def test_competency_without_evidence_carries_the_no_evidence_state():
    result = analyse_competencies("official-statistics", {}, {}, "beginner")
    row = next(r for r in result["competencies"] if r["competency_id"] == "os_ml")
    assert row["evidence_state"] == NO_EVIDENCE
    assert row["confidence"] == "none"


def test_competency_with_evidence_has_no_evidence_state():
    # The vocabulary defines no positive counterpart, so the field is null
    # rather than an invented term like "HAS EVIDENCE".
    result = analyse_competencies("official-statistics", {"os_ml": 3.0}, {}, "expert")
    row = next(r for r in result["competencies"] if r["competency_id"] == "os_ml")
    assert row["evidence_state"] is None
    assert row["evidence_sources"] == ["self_report"]


def test_role_targets_are_labelled_with_a_documented_state():
    result = analyse_competencies("official-statistics", {}, {}, "beginner", job_role="data analyst")
    for row in result["competencies"]:
        assert row["role_target_assurance"] in DOCUMENTED_STATES


def test_every_behavioural_anchor_is_labelled_with_a_documented_state():
    for levels in BEHAVIORAL_ANCHORS.values():
        for record in levels.values():
            assert record["assurance"] in DOCUMENTED_STATES


def test_anchor_records_returned_to_callers_keep_their_assurance():
    record = get_anchor("os_sampling_design", 3.0)
    assert record["assurance"] == "PROVISIONAL"


def test_lab_level_claim_is_labelled_with_a_documented_state():
    assert LEVEL_CLAIM_ASSURANCE in DOCUMENTED_STATES
    assert all(task["level_claim_assurance"] in DOCUMENTED_STATES for task in list_tasks())
    assert evaluate_submission("srs-basic", 385)["level_claim_assurance"] in DOCUMENTED_STATES


# ─── per-competency provenance (orchestration section 5 acceptance) ───

def test_every_competency_has_source_authoring_status_and_version():
    # "Every competency/target has source, authoring status and version."
    for slug, curriculum in CURRICULA.items():
        for competency in curriculum["competencies"]:
            assert competency["source"], f"{slug}:{competency['id']} has no source"
            assert competency["authoring_status"] in DOCUMENTED_STATES
            assert competency["version"] >= 1


def test_public_curricula_exposes_competency_provenance():
    # Lane 1/5 read this payload, so provenance has to survive the public
    # serialization, not just live on the internal dict.
    for curriculum in public_curricula():
        for competency in curriculum["competencies"]:
            assert competency["authoring_status"] == "PROVISIONAL"
            assert "source" in competency
            assert "version" in competency


# ─── uncertainty display (master checklist section 4.1) ───

def test_confidence_band_reflects_evidence_coverage():
    result = analyse_competencies(
        "official-statistics",
        self_ratings={"os_data_quality": 3.0},
        measured_scores={"os_visualization": 3.0},
        experience_level="expert",
    )
    rows = {r["competency_id"]: r for r in result["competencies"]}
    assert rows["os_data_quality"]["confidence"] == "low"        # self-report only
    assert rows["os_visualization"]["confidence"] == "moderate"  # demonstrated
    assert rows["os_gis"]["confidence"] == "none"                # nothing at all


def test_confidence_never_claims_high():
    # "high" would imply a validated instrument; CLAUDE.md invariant #4 keeps
    # this policy provisional until one exists.
    result = analyse_competencies(
        "official-statistics",
        self_ratings={"os_data_quality": 5.0},
        measured_scores={"os_data_quality": 5.0},
        experience_level="expert",
    )
    assert all(r["confidence"] != "high" for r in result["competencies"])
