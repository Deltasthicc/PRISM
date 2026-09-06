"""Fixed role and category vocabulary for the demo.

The learner picks a role from `ROLES` instead of typing free text. That is a
deliberate demo-scope decision, not a claim that the platform cannot accept
free text: `learner_profiles.job_role`/`designation`/`department`/
`current_assignment` are free-text columns and always were. Constraining the
*input* is what makes the rest of the loop deterministic -- a picked role maps
to exactly one known set of competencies, so the pathway, the documents and
the quiz are all reproducible for a judge, with no inference step in between.

When free text comes back, the intended shape is: normalize the text to one of
these `role_id`s, show the learner what was inferred, let them confirm, and
only then run the deterministic pipeline below. The inference layer proposes a
role; it never sets a target level. `CLAUDE.md` invariant: "Deterministic rules
own authorization, target selection, status, provenance and workflow."

Role definitions are team-authored. The cadre names, grades and department
names are real (SRC-01, the MoSPI/NSSTA training calendar; SRC-02's grade
bands), but which competencies a role needs -- and to what level -- is our
judgment. Every role therefore carries assurance PROVISIONAL and no approver,
exactly like `services/role_targets.py`.
"""
from __future__ import annotations

from services.curricula import CURRICULA

PROVISIONAL = "PROVISIONAL"
ROLE_CATALOGUE_VERSION = "prototype-v1"

# The four categories named in docs/SIH26101_PROBLEM_STATEMENT.md's "Explicit
# competency scope" table. These are the problem statement's own words, so the
# keys are fixed and must not be renamed to suit a UI label.
STATISTICAL = "statistical"
TECHNICAL = "technical"
DIGITAL_GOVERNANCE = "digital_governance"
BEHAVIOURAL_MANAGERIAL = "behavioural_managerial"

CATEGORY_LABELS = {
    STATISTICAL: "Statistical",
    TECHNICAL: "Technical",
    DIGITAL_GOVERNANCE: "Digital Governance",
    BEHAVIOURAL_MANAGERIAL: "Behavioural and Managerial",
}

# competency_id -> category. Mirrors services/ps02_coverage.py's mapping of the
# problem statement's named items, extended to the competencies that sit in the
# same category but are not individually named there (e.g. os_data_collection).
# ps02_coverage.py stays the authority on the *named* scope; this map is the
# broader "which bucket does this competency live in" view the UI groups by.
COMPETENCY_CATEGORY: dict[str, str] = {
    # Statistical
    "os_statistical_foundations": STATISTICAL,
    "os_data_collection": STATISTICAL,
    "os_sampling_design": STATISTICAL,
    "os_data_quality": STATISTICAL,
    "os_official_statistics": STATISTICAL,
    "os_survey_design": STATISTICAL,
    "os_national_accounts": STATISTICAL,
    "os_price_statistics": STATISTICAL,
    "os_labour_statistics": STATISTICAL,
    "os_agricultural_statistics": STATISTICAL,
    "os_industrial_statistics": STATISTICAL,
    "os_sdg_indicators": STATISTICAL,
    "os_metadata_standards": STATISTICAL,
    # Technical
    "os_statistical_programming": TECHNICAL,
    "os_data_management_sql": TECHNICAL,
    "os_visualization": TECHNICAL,
    "os_gis": TECHNICAL,
    "os_big_data": TECHNICAL,
    "os_ml": TECHNICAL,
    "os_apis_interoperability": TECHNICAL,
    "os_open_data": TECHNICAL,
    # Digital governance
    "dl_cyber_hygiene": DIGITAL_GOVERNANCE,
    "dl_data_privacy": DIGITAL_GOVERNANCE,
    "dl_digital_signatures": DIGITAL_GOVERNANCE,
    "dl_government_cloud": DIGITAL_GOVERNANCE,
    "dl_digital_public_infrastructure": DIGITAL_GOVERNANCE,
    "dl_digital_foundations": DIGITAL_GOVERNANCE,
    "dl_collaboration": DIGITAL_GOVERNANCE,
    "dl_spreadsheets": DIGITAL_GOVERNANCE,
    "dl_data_literacy": DIGITAL_GOVERNANCE,
    "dl_ai_literacy": DIGITAL_GOVERNANCE,
    "dl_responsible_ai": DIGITAL_GOVERNANCE,
    # Behavioural and managerial
    "pa_leadership": BEHAVIOURAL_MANAGERIAL,
    "pa_communication": BEHAVIOURAL_MANAGERIAL,
    "pa_program_management": BEHAVIOURAL_MANAGERIAL,
    "pa_ethics": BEHAVIOURAL_MANAGERIAL,
    "pa_decision_making": BEHAVIOURAL_MANAGERIAL,
    "pa_change_management": BEHAVIOURAL_MANAGERIAL,
    "pa_governance_foundations": BEHAVIOURAL_MANAGERIAL,
    "pa_policy_design": BEHAVIOURAL_MANAGERIAL,
    "pa_public_finance": BEHAVIOURAL_MANAGERIAL,
    "pa_monitoring_evaluation": BEHAVIOURAL_MANAGERIAL,
    "pa_impact_evaluation": BEHAVIOURAL_MANAGERIAL,
    "pa_data_storytelling": BEHAVIOURAL_MANAGERIAL,
}


def _role(
    role_id,
    designation,
    job_role,
    department,
    current_assignment,
    experience_level,
    cadre,
    focus,
    targets,
):
    return {
        "role_id": role_id,
        "designation": designation,
        "job_role": job_role,
        "department": department,
        "current_assignment": current_assignment,
        "experience_level": experience_level,
        "cadre": cadre,
        "focus_categories": list(focus),
        "competency_targets": dict(targets),
        "assurance": PROVISIONAL,
        "approved_by": None,
        "framework_version": ROLE_CATALOGUE_VERSION,
    }


# The eight demo roles. Designations, cadres and department names come from
# SRC-01 and SRC-02; the competency targets are ours.
ROLES: dict[str, dict] = {
    "jso_field": _role(
        "jso_field",
        designation="Junior Statistical Officer",
        job_role="Field survey operations",
        department="Field Operations Division, NSO",
        current_assignment="Household survey round",
        experience_level="beginner",
        cadre="Subordinate Statistical Service (SSS)",
        focus=[STATISTICAL, DIGITAL_GOVERNANCE],
        targets={
            "os_statistical_foundations": 3,
            "os_data_collection": 4,
            "os_sampling_design": 3,
            "os_data_quality": 3,
            "dl_cyber_hygiene": 3,
            "dl_data_privacy": 3,
        },
    ),
    "sso_price": _role(
        "sso_price",
        designation="Senior Statistical Officer",
        job_role="Price statistics compilation",
        department="Price Statistics Division, NSO",
        current_assignment="CPI compilation",
        experience_level="intermediate",
        cadre="Subordinate Statistical Service (SSS)",
        focus=[STATISTICAL, TECHNICAL],
        targets={
            "os_price_statistics": 4,
            "os_official_statistics": 4,
            "os_data_quality": 4,
            "os_statistical_foundations": 4,
            "os_metadata_standards": 3,
            "os_statistical_programming": 3,
        },
    ),
    "iss_probationer": _role(
        "iss_probationer",
        designation="Assistant Director (Probationer)",
        job_role="Official statistics generalist",
        department="National Statistical Office",
        current_assignment="ISS probationary training",
        experience_level="beginner",
        cadre="Indian Statistical Service (ISS)",
        focus=[STATISTICAL, TECHNICAL],
        targets={
            "os_statistical_foundations": 4,
            "os_official_statistics": 4,
            "os_sampling_design": 4,
            "os_national_accounts": 3,
            "os_labour_statistics": 3,
            "os_statistical_programming": 3,
        },
    ),
    "deputy_director_nas": _role(
        "deputy_director_nas",
        designation="Deputy Director",
        job_role="National accounts compilation",
        department="National Accounts Division, NSO",
        current_assignment="GDP estimation cycle",
        experience_level="advanced",
        cadre="Indian Statistical Service (ISS)",
        focus=[STATISTICAL, TECHNICAL],
        targets={
            "os_national_accounts": 5,
            "os_official_statistics": 4,
            "os_industrial_statistics": 4,
            "os_data_quality": 4,
            "os_metadata_standards": 4,
        },
    ),
    "joint_director_survey": _role(
        "joint_director_survey",
        designation="Joint Director",
        job_role="Survey design and methodology",
        department="Survey Design and Research Division, NSO",
        current_assignment="Large-scale sample survey planning",
        experience_level="advanced",
        cadre="Indian Statistical Service (ISS)",
        focus=[STATISTICAL, TECHNICAL, BEHAVIOURAL_MANAGERIAL],
        targets={
            "os_survey_design": 5,
            "os_sampling_design": 5,
            "os_data_collection": 4,
            "os_data_quality": 4,
            "pa_program_management": 4,
            "pa_leadership": 4,
        },
    ),
    "data_analyst_dqa": _role(
        "data_analyst_dqa",
        designation="Statistical Analyst",
        job_role="Data analysis and dissemination",
        department="Data Quality Assurance Division, NSO",
        current_assignment="SDG indicator reporting",
        experience_level="intermediate",
        cadre="Subordinate Statistical Service (SSS)",
        focus=[TECHNICAL, STATISTICAL],
        targets={
            "os_statistical_programming": 4,
            "os_data_management_sql": 4,
            "os_visualization": 4,
            "os_sdg_indicators": 4,
            "os_open_data": 3,
            "os_ml": 3,
        },
    ),
    "state_des_officer": _role(
        "state_des_officer",
        designation="Deputy Director",
        job_role="State statistical coordination",
        department="Directorate of Economics and Statistics (State)",
        current_assignment="State domestic product estimation",
        experience_level="intermediate",
        cadre="State statistical service",
        focus=[STATISTICAL, DIGITAL_GOVERNANCE, BEHAVIOURAL_MANAGERIAL],
        targets={
            "os_national_accounts": 4,
            "os_agricultural_statistics": 4,
            "os_official_statistics": 4,
            "pa_communication": 3,
            "dl_data_privacy": 3,
        },
    ),
    "programme_manager": _role(
        "programme_manager",
        designation="Director",
        job_role="Programme management and capacity building",
        department="Data Informatics and Innovation Division",
        current_assignment="Capacity-building programme delivery",
        experience_level="advanced",
        cadre="Indian Statistical Service (ISS)",
        focus=[BEHAVIOURAL_MANAGERIAL, DIGITAL_GOVERNANCE],
        targets={
            "pa_leadership": 5,
            "pa_program_management": 5,
            "pa_change_management": 4,
            "pa_decision_making": 4,
            "pa_communication": 4,
            "dl_ai_literacy": 3,
        },
    ),
}


def list_roles() -> list[dict]:
    """Everything a role picker needs to render, without the target numbers."""
    return [
        {
            "role_id": role["role_id"],
            "designation": role["designation"],
            "job_role": role["job_role"],
            "department": role["department"],
            "current_assignment": role["current_assignment"],
            "cadre": role["cadre"],
            "experience_level": role["experience_level"],
            "focus_categories": [CATEGORY_LABELS[c] for c in role["focus_categories"]],
        }
        for role in ROLES.values()
    ]


def get_role(role_id: str) -> dict | None:
    role = ROLES.get(role_id)
    return dict(role) if role else None


def categories_for_role(role_id: str) -> dict[str, list[str]]:
    """The role's competencies grouped by the four problem-statement
    categories. Empty categories are omitted rather than shown as zero -- a
    role genuinely has no target there."""
    role = ROLES.get(role_id)
    if not role:
        return {}
    grouped: dict[str, list[str]] = {}
    for competency_id in role["competency_targets"]:
        category = COMPETENCY_CATEGORY.get(competency_id)
        if category:
            grouped.setdefault(category, []).append(competency_id)
    return grouped


def validate_role_catalogue() -> None:
    """Fail at import on a role pointing at a competency that does not exist,
    a target outside 1-5, or a competency missing from the category map."""
    known = {
        competency["id"]
        for curriculum in CURRICULA.values()
        for competency in curriculum["competencies"]
    }
    uncategorized = sorted(set(COMPETENCY_CATEGORY) - known)
    if uncategorized:
        raise ValueError(f"COMPETENCY_CATEGORY names unknown competencies: {uncategorized}")

    for role_id, role in ROLES.items():
        if role["experience_level"] not in {"beginner", "intermediate", "advanced", "expert"}:
            raise ValueError(f"{role_id} has an invalid experience_level")
        for competency_id, level in role["competency_targets"].items():
            if competency_id not in known:
                raise ValueError(f"{role_id} targets unknown competency {competency_id}")
            if not isinstance(level, int) or not 1 <= level <= 5:
                raise ValueError(f"{role_id}:{competency_id} target {level} is outside 1-5")
            if competency_id not in COMPETENCY_CATEGORY:
                raise ValueError(f"{competency_id} has no category; add it to COMPETENCY_CATEGORY")
        for category in role["focus_categories"]:
            if category not in CATEGORY_LABELS:
                raise ValueError(f"{role_id} has unknown focus category {category}")


validate_role_catalogue()
