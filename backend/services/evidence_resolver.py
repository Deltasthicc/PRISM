"""Reads a learner's separated evidence rows and hands the gap engine plain data.

`SIH26101_TEAM_ORCHESTRATION.md` section 5, Lane 3 next package: "Separate
self-report, diagnostic, observed-practice, reviewer and provider evidence."
Lane 2 owns the storage (`models/governance.py`'s `EvidenceRecord`) and the
ordering rules (`db/repositories.py`'s `get_latest_evidence`); this module
owns which types to ask for and how the result is shaped for
`services/learning_engine.py`. That split is Lane 2's own instruction in
`docs/contracts/data-authorization.md` section 4.1: "Weighting self-report,
diagnostic, observed-practice, reviewer and provider-imported evidence
remains Lane 3's versioned policy."

**Why this lives here and not inside the engine.** `analyse_competencies()`
is a pure function -- no database, no HTTP -- which is what lets the golden
fixtures pin its output exactly (`docs/contracts/competency-evidence.md`
section 5.1) and what `CLAUDE.md` invariant #2 requires ("domain logic lives
in services, persistence ... in models"). So this module follows the pattern
`routes/learning.py` already uses for `AccuracyHistory`: resolve rows against
the database here, hand the engine plain data, keep the engine pure.

**Authorization is not inferred here.** Exactly as Lane 2's repositories
state, accepting a `player_id` proves nothing about the caller. Per
`docs/contracts/data-authorization.md` section 4.1's security boundary, a
Lane 5 route must verify the token, resolve an active local binding, require
the relevant permission and enforce own-player scope *before* calling this.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from db.repositories import get_latest_evidence
from models.governance import EVIDENCE_TYPES


def resolve_evidence(
    db: Session,
    player_id: str,
    competency_ids: list[str],
    *,
    evidence_types: tuple[str, ...] = EVIDENCE_TYPES,
) -> dict[str, dict[str, dict]]:
    """Return `{competency_id: {evidence_type: {value, recorded_at, detail}}}`.

    Only types with a stored row appear -- an absent type is absent, never a
    zero. `value` stays `None` where the row carries one (Lane 2 documents
    `reviewer` evidence as possibly qualitative-only), so a caller can tell
    "reviewed, no numeric rating" apart from "rated zero".
    """
    resolved: dict[str, dict[str, dict]] = {}
    for competency_id in competency_ids:
        per_type: dict[str, dict] = {}
        for evidence_type in evidence_types:
            record = get_latest_evidence(db, player_id, competency_id, evidence_type)
            if record is None:
                continue
            per_type[evidence_type] = {
                "value": record.value,
                "recorded_at": record.recorded_at.isoformat() if record.recorded_at else None,
                "detail": record.detail or "",
            }
        if per_type:
            resolved[competency_id] = per_type
    return resolved
