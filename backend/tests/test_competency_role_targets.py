"""Tests for the versioned role-target seam (services/role_targets.py) and its
wiring into services/learning_engine.py -- Lane 3's immediate-package item:
"replace experience-only targeting with an explicit versioned role-target
selection contract" (SIH26101_TEAM_ORCHESTRATION.md section 5).
"""
import pytest

from services.learning_engine import analyse_competencies
from services.role_targets import (
    FRAMEWORK_VERSION,
    PROVISIONAL,
    RESOLUTION_ORDER,
    experience_cap,
    resolve_role_target,
)


# ─── role_targets.py ───

def test_resolve_role_target_matches_job_role_case_insensitively():
    result = resolve_role_target("os_official_statistics", 3, job_role="Statistical Officer")
    assert result["target_level"] == 5
    assert result["source"] == "internal-prototype"
    assert result["framework_version"] == FRAMEWORK_VERSION
    assert result["approved_by"] is None
    assert result["matched_role"] == "statistical officer"
    assert result["matched_field"] == "job_role"


def test_every_target_is_labelled_provisional():
    # SIH26101_MASTER_CHECKLIST.md section 3.3: "label any team-authored
    # target as PROVISIONAL" -- true for both an override and the fallback.
    override = resolve_role_target("os_official_statistics", 3, job_role="statistical officer")
    fallback = resolve_role_target("os_gis", 4)
    assert override["assurance"] == PROVISIONAL == "PROVISIONAL"
    assert fallback["assurance"] == PROVISIONAL


def test_current_assignment_and_department_also_select_targets():
    # SIH26101_MASTER_CHECKLIST.md section 4.1 requires all four profile
    # fields to be usable, not just job role and designation.
    by_assignment = resolve_role_target(
        "os_sampling_design", 3, current_assignment="Household Survey Round"
    )
    assert by_assignment["target_level"] == 4
    assert by_assignment["matched_field"] == "current_assignment"

    by_department = resolve_role_target("os_official_statistics", 3, department="Statistics Division")
    assert by_department["target_level"] == 4
    assert by_department["matched_field"] == "department"


def test_resolution_order_prefers_the_more_specific_field():
    # Both keys carry a target for this competency; the job role must win
    # over the broader department bucket.
    result = resolve_role_target(
        "os_official_statistics",
        3,
        job_role="statistical officer",
        department="statistics division",
    )
    assert result["target_level"] == 5  # the role's value, not the department's 4
    assert result["matched_field"] == "job_role"
    assert RESOLUTION_ORDER.index("job_role") < RESOLUTION_ORDER.index("department")


def test_resolve_role_target_falls_back_to_designation_when_job_role_silent():
    # job_role is a real override role, but has no entry for this specific
    # competency, so designation is tried next.
    result = resolve_role_target(
        "pa_program_management", 3, job_role="data analyst", designation="Programme Manager"
    )
    assert result["target_level"] == 5
    assert result["matched_role"] == "programme manager"


def test_resolve_role_target_falls_back_to_curriculum_default_for_unknown_role():
    result = resolve_role_target("os_gis", 4, job_role="Field Enumerator")
    assert result["target_level"] == 4
    assert result["source"] == "curriculum-default"
    assert result["matched_role"] == "*"
    assert result["matched_field"] is None


def test_resolve_role_target_ignores_blank_role_strings():
    result = resolve_role_target("os_statistical_foundations", 3, job_role="", designation="")
    assert result["source"] == "curriculum-default"
    assert result["matched_role"] == "*"


def test_experience_cap_known_and_unknown_levels():
    assert experience_cap("beginner") == 3
    assert experience_cap("expert") == 5
    assert experience_cap("not-a-real-level") == 3


# ─── learning_engine.py wiring ───

def test_analyse_competencies_uses_job_role_target_when_present():
    result = analyse_competencies(
        "official-statistics",
        self_ratings={},
        measured_scores={},
        experience_level="expert",  # cap of 5 -- wide enough not to mask the role target
        job_role="statistical officer",
    )
    row = next(r for r in result["competencies"] if r["competency_id"] == "os_official_statistics")
    assert row["role_target"] == 5
    assert row["role_target_source"] == "internal-prototype"
    assert row["matched_role"] == "statistical officer"
    assert result["job_role"] == "statistical officer"
    assert result["method"]["role_target_framework_version"] == FRAMEWORK_VERSION


def test_analyse_competencies_defaults_to_curriculum_target_without_role():
    result = analyse_competencies("official-statistics", {}, {}, "expert")
    row = next(r for r in result["competencies"] if r["competency_id"] == "os_official_statistics")
    # curricula.py's own target_level for this competency is 4.
    assert row["role_target"] == 4
    assert row["role_target_source"] == "curriculum-default"


def test_analyse_competencies_still_caps_pathway_target_by_experience():
    # A role target of 5 must still be capped by a "beginner" experience
    # ceiling of 3 -- role targeting adds a ceiling, it never removes the
    # experience-level one (pre-existing behavior, must not regress).
    result = analyse_competencies(
        "official-statistics", {}, {}, "beginner", job_role="statistical officer"
    )
    row = next(r for r in result["competencies"] if r["competency_id"] == "os_official_statistics")
    assert row["role_target"] == 5
    assert row["pathway_target"] <= 3


def test_analyse_competencies_backward_compatible_without_role_kwargs():
    # Existing call sites (routes/learning.py, test_learning_platform.py) call
    # this with only four positional args -- must keep working unchanged.
    result = analyse_competencies("official-statistics", {}, {}, "beginner")
    assert result["job_role"] == ""
    assert result["designation"] == ""
