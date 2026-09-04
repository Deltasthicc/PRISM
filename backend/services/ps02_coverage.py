"""PS-02 traceability: every competency named in the problem statement, mapped
to the competency ID that represents it.

`docs/SIH26101_PROBLEM_STATEMENT.md` lists four categories with named examples
under "Explicit competency scope", and records the gap plainly: "The current
repository's four curricula/34 competencies do not yet cover this complete list
and are not an MoSPI-approved framework." That file also requires the `PS-*`
identifiers to be usable "in issues, PRs, acceptance tests and the final
evidence matrix" -- so coverage is expressed here as data and enforced by
`validate_ps02_coverage()` at import, rather than asserted in a slide.

Two honest limits on what this module proves:

- It proves *representation*, not validation. Every mapped competency is still
  `PROVISIONAL` (services/curricula.py); PS-02's production boundary is
  "Authorized MoSPI/CBC/NSSTA validation", which remains BLOCKED-EXTERNAL.
- Several named items intentionally share one competency (Python, R, Stata,
  SPSS and SAS all map to `os_statistical_programming`). That is a deliberate
  grouping of tools under one skill, not five competencies pretending to be
  one; the mapping below is explicit so a domain reviewer can challenge any
  grouping they disagree with.
"""
from __future__ import annotations

from services.curricula import CURRICULA

# Verbatim from docs/SIH26101_PROBLEM_STATEMENT.md, "Explicit competency scope".
# Do not reword: this is the requirement text, and drift here would quietly
# weaken what validate_ps02_coverage() actually checks.
PS02_NAMED_SCOPE: dict[str, tuple[str, ...]] = {
    "Statistical": (
        "Survey Design",
        "Sampling",
        "National Accounts",
        "Price Statistics",
        "Labour Statistics",
        "Agricultural Statistics",
        "Industrial Statistics",
        "SDG Indicators",
        "Metadata Standards",
        "Data Quality Frameworks",
    ),
    "Technical": (
        "Python",
        "R",
        "SQL",
        "Stata",
        "SPSS",
        "SAS",
        "GIS",
        "Data Visualization",
        "AI/ML",
        "Cloud Computing",
        "APIs",
        "Open Data",
    ),
    "Digital Governance": (
        "Cybersecurity",
        "Data Privacy",
        "Digital Signatures",
        "Government Cloud",
        "Digital Public Infrastructure",
    ),
    "Behavioural and Managerial": (
        "Leadership",
        "Communication",
        "Project Management",
        "Ethics",
        "Decision Making",
        "Change Management",
    ),
}

# Named item -> the competency ID in services/curricula.py that represents it.
PS02_COVERAGE: dict[str, str] = {
    # Statistical
    "Survey Design": "os_survey_design",
    "Sampling": "os_sampling_design",
    "National Accounts": "os_national_accounts",
    "Price Statistics": "os_price_statistics",
    "Labour Statistics": "os_labour_statistics",
    "Agricultural Statistics": "os_agricultural_statistics",
    "Industrial Statistics": "os_industrial_statistics",
    "SDG Indicators": "os_sdg_indicators",
    "Metadata Standards": "os_metadata_standards",
    "Data Quality Frameworks": "os_data_quality",
    # Technical
    "Python": "os_statistical_programming",
    "R": "os_statistical_programming",
    "Stata": "os_statistical_programming",
    "SPSS": "os_statistical_programming",
    "SAS": "os_statistical_programming",
    "SQL": "os_data_management_sql",
    "GIS": "os_gis",
    "Data Visualization": "os_visualization",
    "AI/ML": "os_ml",
    "Cloud Computing": "os_big_data",
    "APIs": "os_apis_interoperability",
    "Open Data": "os_open_data",
    # Digital Governance
    "Cybersecurity": "dl_cyber_hygiene",
    "Data Privacy": "dl_data_privacy",
    "Digital Signatures": "dl_digital_signatures",
    "Government Cloud": "dl_government_cloud",
    "Digital Public Infrastructure": "dl_digital_public_infrastructure",
    # Behavioural and Managerial
    "Leadership": "pa_leadership",
    "Communication": "pa_communication",
    "Project Management": "pa_program_management",
    "Ethics": "pa_ethics",
    "Decision Making": "pa_decision_making",
    "Change Management": "pa_change_management",
}


def _competency_index() -> dict[str, tuple[str, dict]]:
    return {
        competency["id"]: (slug, competency)
        for slug, curriculum in CURRICULA.items()
        for competency in curriculum["competencies"]
    }


def validate_ps02_coverage() -> None:
    """Fail fast if a named PS-02 competency loses its mapping, or if a mapping
    points at a competency ID that no longer exists."""
    named = {item for items in PS02_NAMED_SCOPE.values() for item in items}

    unmapped = named - set(PS02_COVERAGE)
    if unmapped:
        raise ValueError(f"PS-02 named competencies with no mapping: {', '.join(sorted(unmapped))}")

    stale = set(PS02_COVERAGE) - named
    if stale:
        raise ValueError(f"PS-02 mappings for competencies not in the problem statement: {', '.join(sorted(stale))}")

    known = _competency_index()
    dangling = {name: cid for name, cid in PS02_COVERAGE.items() if cid not in known}
    if dangling:
        detail = ", ".join(f"{name} -> {cid}" for name, cid in sorted(dangling.items()))
        raise ValueError(f"PS-02 mappings pointing at unknown competency IDs: {detail}")


def coverage_report() -> dict:
    """Per-category traceability for the admin/evidence view: which competency
    represents each named PS-02 item, and where it lives.

    Returned rather than printed so Lane 5 can expose it and Lane 6 can use it
    as evidence-matrix input (docs/contracts/competency-evidence.md section 9).
    """
    known = _competency_index()
    categories = {}
    for category, items in PS02_NAMED_SCOPE.items():
        rows = []
        for item in items:
            competency_id = PS02_COVERAGE[item]
            curriculum_slug, competency = known[competency_id]
            rows.append(
                {
                    "named_competency": item,
                    "competency_id": competency_id,
                    "label": competency["label"],
                    "curriculum_slug": curriculum_slug,
                    "authoring_status": competency["authoring_status"],
                }
            )
        categories[category] = rows

    return {
        "requirement": "PS-02",
        "source": "docs/SIH26101_PROBLEM_STATEMENT.md",
        "named_total": sum(len(items) for items in PS02_NAMED_SCOPE.values()),
        "categories": categories,
        "note": (
            "Representation only. Every mapped competency is PROVISIONAL; "
            "authorized MoSPI/CBC/NSSTA validation remains BLOCKED-EXTERNAL."
        ),
    }


validate_ps02_coverage()
