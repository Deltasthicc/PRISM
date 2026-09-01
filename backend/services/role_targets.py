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
catalog. Every value returned here carries source="internal-prototype" and
approved_by=None; only a named domain reviewer changes that.
"""

from __future__ import annotations

FRAMEWORK_VERSION = "prototype-v1"

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

# role (lowercased) -> {competency_id: target_level}. Roles are matched
# case-insensitively against job_role first, then designation. A role absent
# here, or present but silent on a given competency, falls back to that
# competency's own curriculum-wide target_level (source="curriculum-default").
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
}


def experience_cap(experience_level: str) -> int:
    return EXPERIENCE_TARGET_CAP.get(experience_level, 3)


def resolve_role_target(
    competency_id: str,
    curriculum_default_target: float,
    job_role: str = "",
    designation: str = "",
) -> dict:
    """Return {target_level, source, framework_version, approved_by,
    matched_role} for one competency.

    Precedence: job_role override, then designation override, then the
    curriculum's own role-agnostic target_level. This mirrors the precedence
    a future RoleTarget DB lookup would use with role="*" as the agnostic
    fallback row.
    """
    for candidate in (job_role, designation):
        key = (candidate or "").strip().lower()
        if not key:
            continue
        override = ROLE_TARGET_OVERRIDES.get(key, {})
        if competency_id in override:
            return {
                "target_level": float(override[competency_id]),
                "source": "internal-prototype",
                "framework_version": FRAMEWORK_VERSION,
                "approved_by": None,
                "matched_role": key,
            }

    return {
        "target_level": float(curriculum_default_target),
        "source": "curriculum-default",
        "framework_version": FRAMEWORK_VERSION,
        "approved_by": None,
        "matched_role": "*",
    }
