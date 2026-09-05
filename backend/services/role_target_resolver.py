"""Resolves role targets from Lane 2's `role_targets` table for the gap engine.

This is the database-backed counterpart to `services/role_targets.py`'s
in-memory demonstration set. It applies exactly the same Lane 3 precedence
policy -- both call `role_candidates()`, so the two paths cannot drift -- and
returns exactly the same record shape, so `analyse_competencies()` consumes
either without caring which produced it.

The split of responsibilities is Lane 2's own, stated in
`docs/contracts/data-authorization.md` section 4.1: `get_current_role_target`
"deliberately does not normalize aliases, choose among profile fields or fall
back to role `"*"`: those are Lane 3 policy decisions." Storage owns validity
windows and deterministic ordering; this module owns which role keys to try,
in what order, and what to do when none match.

**Why this is not inside the engine.** `analyse_competencies()` is pure -- no
database, no HTTP, no clock -- which is what lets the golden fixtures pin its
output exactly and what `CLAUDE.md` invariant #2 requires. So this module
resolves rows here and hands the engine plain data, the same pattern
`routes/learning_common.py` already uses for `AccuracyHistory`.

**Authorization is not inferred here.** Accepting a role string or player id
proves nothing about the caller. Per `data-authorization.md` section 4.1's
security boundary, a Lane 5 route must verify the token, resolve an active
local binding, require the relevant permission and enforce scope *before*
calling this.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from db.repositories import get_current_role_target
from services.curricula import get_curriculum
from services.role_targets import (
    FRAMEWORK_VERSION,
    assurance_for,
    curriculum_default_target,
    role_candidates,
)

# The role-agnostic fallback key. Lane 2 stores it as an ordinary role value;
# treating it as "the default row" is Lane 3 policy, which is why the lookup
# for it lives here and not in the repository.
AGNOSTIC_ROLE = "*"


def _record(row, matched_role: str, matched_field: str | None) -> dict:
    return {
        "target_level": float(row.target_level),
        "source": row.source,
        "assurance": assurance_for(row.approved_by),
        "framework_version": row.framework_version or FRAMEWORK_VERSION,
        "approved_by": row.approved_by,
        "matched_role": matched_role,
        "matched_field": matched_field,
    }


def resolve_role_targets(
    db: Session,
    curriculum_slug: str,
    *,
    job_role: str = "",
    designation: str = "",
    current_assignment: str = "",
    department: str = "",
    as_of: datetime | None = None,
) -> dict[str, dict]:
    """Return `{competency_id: target_record}` covering every competency in the
    curriculum, ready to hand to `analyse_competencies(role_targets=...)`.

    Per competency the precedence is: each supplied profile field in
    `RESOLUTION_ORDER`, then a stored role-agnostic `"*"` row, then the
    curriculum's own `target_level`. The map is always complete -- a
    competency with no stored row still gets its curriculum default -- so the
    engine never has to mix this source with any other.

    Raises `ValueError` for an unknown curriculum, matching the engine.
    """
    curriculum = get_curriculum(curriculum_slug)
    if not curriculum:
        raise ValueError(f"Unknown curriculum: {curriculum_slug}")

    candidates = role_candidates(job_role, designation, current_assignment, department)

    resolved: dict[str, dict] = {}
    for item in curriculum["competencies"]:
        competency_id = item["id"]
        record = None

        for field, key in candidates:
            row = get_current_role_target(db, key, competency_id, as_of=as_of)
            if row is not None:
                record = _record(row, matched_role=key, matched_field=field)
                break

        if record is None:
            # A stored agnostic default still beats the curriculum's own
            # number: someone deliberately recorded it, with a validity window
            # and an approver field.
            agnostic = get_current_role_target(db, AGNOSTIC_ROLE, competency_id, as_of=as_of)
            if agnostic is not None:
                record = _record(agnostic, matched_role=AGNOSTIC_ROLE, matched_field=None)

        if record is None:
            record = curriculum_default_target(competency_id, item.get("target_level", 3))

        resolved[competency_id] = record

    return resolved
