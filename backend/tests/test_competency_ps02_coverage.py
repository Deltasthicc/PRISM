"""Acceptance tests for PS-02's named competency scope.

`docs/SIH26101_PROBLEM_STATEMENT.md` requires the `PS-*` identifiers to be
usable "in issues, PRs, acceptance tests and the final evidence matrix", and
records that the original four curricula "do not yet cover this complete
list". These tests are that acceptance check: they fail if any named
competency loses its representation.
"""
import pytest

from services.curricula import CURRICULA, public_curricula
from services.ps02_coverage import (
    PS02_COVERAGE,
    PS02_NAMED_SCOPE,
    coverage_report,
    validate_ps02_coverage,
)


def _all_competency_ids() -> set[str]:
    return {
        competency["id"]
        for curriculum in CURRICULA.values()
        for competency in curriculum["competencies"]
    }


def test_validate_ps02_coverage_passes_on_reimport():
    validate_ps02_coverage()


def test_all_four_named_categories_are_represented():
    assert set(PS02_NAMED_SCOPE) == {
        "Statistical",
        "Technical",
        "Digital Governance",
        "Behavioural and Managerial",
    }


def test_every_named_competency_maps_to_an_existing_competency():
    known = _all_competency_ids()
    for category, items in PS02_NAMED_SCOPE.items():
        for item in items:
            assert item in PS02_COVERAGE, f"{category}: '{item}' has no mapping"
            assert PS02_COVERAGE[item] in known, f"{category}: '{item}' maps to a missing competency"


def test_named_scope_matches_the_problem_statement_counts():
    # 10 statistical + 12 technical + 5 digital governance + 6 behavioural.
    assert [len(items) for items in PS02_NAMED_SCOPE.values()] == [10, 12, 5, 6]
    assert sum(len(items) for items in PS02_NAMED_SCOPE.values()) == 33


def test_previously_missing_competencies_now_exist():
    # The specific gaps docs/SIH26101_PROBLEM_STATEMENT.md called out.
    known = _all_competency_ids()
    for competency_id in (
        "os_price_statistics",
        "os_national_accounts",
        "os_labour_statistics",
        "os_agricultural_statistics",
        "os_industrial_statistics",
        "os_sdg_indicators",
        "os_metadata_standards",
        "os_survey_design",
        "pa_leadership",
        "pa_ethics",
        "pa_decision_making",
        "pa_change_management",
        "dl_data_privacy",
        "dl_digital_public_infrastructure",
    ):
        assert competency_id in known


def test_grouped_tools_share_one_competency_deliberately():
    # Python/R/Stata/SPSS/SAS are one skill, not five competencies -- the
    # mapping records that openly so a reviewer can challenge it.
    grouped = {PS02_COVERAGE[tool] for tool in ("Python", "R", "Stata", "SPSS", "SAS")}
    assert grouped == {"os_statistical_programming"}


def test_coverage_report_is_complete_and_labelled_provisional():
    report = coverage_report()
    assert report["requirement"] == "PS-02"
    assert report["named_total"] == 33
    for category, rows in report["categories"].items():
        assert len(rows) == len(PS02_NAMED_SCOPE[category])
        for row in rows:
            assert row["label"]
            assert row["curriculum_slug"] in {c["slug"] for c in public_curricula()}
            # Representation is not validation.
            assert row["authoring_status"] == "PROVISIONAL"


def test_stale_mapping_is_rejected(monkeypatch):
    monkeypatch.setitem(PS02_COVERAGE, "Sampling", "os_not_a_real_competency")
    with pytest.raises(ValueError, match="unknown competency IDs"):
        validate_ps02_coverage()


def test_dropped_mapping_is_rejected(monkeypatch):
    monkeypatch.delitem(PS02_COVERAGE, "Leadership")
    with pytest.raises(ValueError, match="no mapping"):
        validate_ps02_coverage()
