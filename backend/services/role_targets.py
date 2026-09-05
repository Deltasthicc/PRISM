"""Versioned role-target selection -- the seam that lets learning_engine.py
stop hardcoding a single experience-level cap as "the target", without
waiting on Lane 2's `RoleTarget` table (backend/models/governance.py) to
merge to main first.

Lane 2's model documents the same precedence this module implements: `role`
is free-text (a designation or job_role string, or "*" for a role-agnostic
default) because no approved role catalog exists yet
(docs/SIH26101_PROBLEM_STATEMENT.md). When that table lands, the intended
migration is to swap `resolve_role_target`'s body for a DB lookup ordered by
`valid_from`/`valid_to` and keep this exact return shape, so
learning_engine.py's call site does not need to change.

`ROLE_TARGET_OVERRIDES` is a small, honest demonstration set for the
canonical Official Statistics and Public Policy domains
(SIH26101_MASTER_CHECKLIST.md section 3.3) -- not an MoSPI/CBC-approved role
catalog. Every value returned here carries assurance="PROVISIONAL" and
approved_by=None; only a named domain reviewer changes that.

Two known gaps against SIH26101_MASTER_CHECKLIST.md section 4.1's target
record ("framework_version, role, activity, competency, target_level, source,
approved_by, valid_from and valid_to"), recorded here rather than faked:

- **No `activity` layer.** FRAC is role -> activity -> competency; this
  module (and Lane 2's `RoleTarget` table) both jump role -> competency.
  Adding it is a cross-lane schema change, not a Lane 3 edit, so it belongs
  in a contract proposal.
- **No `valid_from`/`valid_to`.** A module-level dict has no validity window;
  those arrive with Lane 2's table. Until then a target is simply "in effect
  now", and no caller may claim dated target history.
"""

from __future__ import annotations

FRAMEWORK_VERSION = "prototype-v1"

# The documented assurance vocabulary is fixed: SIMULATED, CATALOGUE, LIVE,
# PROVISIONAL, NO EVIDENCE (CODEX.md / CLAUDE.md architectural invariants,
# "use ... precisely"). Every target here is team-authored and unvalidated,
# which SIH26101_MASTER_CHECKLIST.md section 3.3 requires be labelled exactly
# PROVISIONAL: "label any team-authored target as PROVISIONAL".
PROVISIONAL = "PROVISIONAL"

# Ceiling applied on top of any role target, per the learner's self-declared
# experience -- kept from the prior EXPERIENCE_TARGET_CAP so pathway_target
# behavior (min(role_target, experience_cap)) is unchanged for callers that
# pass no role/designation.
EXPERIENCE_TARGET_CAP = {
    "beginner": 3,
    "intermediate": 4,
    "advanced": 5,
    "expert": 5,
}

# key (lowercased) -> {competency_id: target_level}. SIH26101_MASTER_CHECKLIST.md
# section 4.1 requires all four profile fields to select a target -- "use
# designation/job role/department/assignment to choose an explicit versioned
# role target" -- so a key here may be any of those four, matched
# case-insensitively in RESOLUTION_ORDER's specificity order. A key absent
# here, or present but silent on a given competency, falls back to that
# competency's own curriculum-wide target_level (source="curriculum-default").
#
# Cross-lane note: Lane 2's RoleTarget.role is documented as "a designation or
# job_role string" only. Persisting department/assignment targets to that
# table needs either a widened `role` definition or a key-type column -- a
# contract proposal against docs/contracts/data-authorization.md, not a
# unilateral Lane 3 change.
ROLE_TARGET_OVERRIDES: dict[str, dict[str, int]] = {
    "statistical officer": {
        "os_statistical_foundations": 4,
        "os_data_collection": 4,
        "os_sampling_design": 4,
        "os_data_quality": 4,
        "os_official_statistics": 5,
    },
    "data analyst": {
        "os_statistical_foundations": 4,
        "os_visualization": 4,
        "os_data_quality": 4,
        "os_big_data": 4,
        "os_ml": 4,
    },
    "programme manager": {
        "pa_governance_foundations": 3,
        "pa_policy_design": 4,
        "pa_program_management": 5,
        "pa_monitoring_evaluation": 4,
    },
    # Department-level target: broader than a role, used when no specific
    # role/designation target covers the competency.
    "statistics division": {
        "os_official_statistics": 4,
        "os_data_quality": 4,
    },
    # Assignment-level target: what the learner's current posting demands.
    "household survey round": {
        "os_sampling_design": 4,
        "os_data_collection": 4,
    },
}

# Most specific selector first. A job role describes what the learner does; a
# designation is their rank; a current assignment is the posting they are on
# now; a department is the broadest bucket. Documented explicitly so a target
# is always explainable ("this target came from your designation, not your
# department") rather than the result of dict ordering.
RESOLUTION_ORDER = ("job_role", "designation", "current_assignment", "department")


def experience_cap(experience_level: str) -> int:
    return EXPERIENCE_TARGET_CAP.get(experience_level, 3)


def role_candidates(
    job_role: str = "",
    designation: str = "",
    current_assignment: str = "",
    department: str = "",
) -> list[tuple[str, str]]:
    """Return `[(profile_field, normalized_role_key), ...]` in precedence order,
    skipping blanks.

    This is the single definition of Lane 3's precedence policy. Both the
    in-memory path below and the database-backed path in
    services/role_target_resolver.py consume it, so the two can never drift
    apart -- and Lane 2's `get_current_role_target` deliberately implements
    none of it ("Role/designation/department precedence, aliases and the `\"*\"`
    fallback are Lane 3 policy", docs/contracts/data-authorization.md 4.1).
    """
    supplied = {
        "job_role": job_role,
        "designation": designation,
        "current_assignment": current_assignment,
        "department": department,
    }
    ordered = []
    for field in RESOLUTION_ORDER:
        key = (supplied[field] or "").strip().lower()
        if key:
            ordered.append((field, key))
    return ordered


def assurance_for(approved_by: str | None) -> str | None:
    """`PROVISIONAL` while nobody has signed a target off; `None` once someone
    has.

    SIH26101_MASTER_CHECKLIST.md 3.3 requires a team-authored target to be
    labelled exactly `PROVISIONAL`, and the fixed vocabulary (`SIMULATED`,
    `CATALOGUE`, `LIVE`, `PROVISIONAL`, `NO EVIDENCE`) offers no term for
    "approved" -- so an approved target carries no assurance label rather than
    an invented one, exactly as `evidence_state` stays null instead of
    inventing a positive counterpart to `NO EVIDENCE`. `approved_by` itself
    tells the consumer who signed it.
    """
    return PROVISIONAL if approved_by is None else None


def curriculum_default_target(competency_id: str, curriculum_default: float) -> dict:
    """The role-agnostic fallback record, used when no role key matches."""
    return {
        "target_level": float(curriculum_default),
        "source": "curriculum-default",
        "assurance": PROVISIONAL,
        "framework_version": FRAMEWORK_VERSION,
        "approved_by": None,
        "matched_role": "*",
        "matched_field": None,
    }


def resolve_role_target(
    competency_id: str,
    curriculum_default: float,
    job_role: str = "",
    designation: str = "",
    current_assignment: str = "",
    department: str = "",
) -> dict:
    """Resolve one competency's target from the in-memory demonstration set.

    Return shape: {target_level, source, assurance, framework_version,
    approved_by, matched_role, matched_field}. `matched_field` says which
    profile field produced the target, so a UI can explain the selection
    instead of just asserting it.

    This is the no-database path, kept so the engine stays pure and its golden
    fixtures stay exact. The database-backed equivalent lives in
    services/role_target_resolver.py and returns the same shape.
    """
    for field, key in role_candidates(job_role, designation, current_assignment, department):
        override = ROLE_TARGET_OVERRIDES.get(key, {})
        if competency_id in override:
            return {
                "target_level": float(override[competency_id]),
                "source": "internal-prototype",
                "assurance": PROVISIONAL,
                "framework_version": FRAMEWORK_VERSION,
                "approved_by": None,
                "matched_role": key,
                "matched_field": field,
            }

    return curriculum_default_target(competency_id, curriculum_default)
