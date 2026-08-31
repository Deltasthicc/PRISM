"""Lane 2 shared read-only repository queries.

Other lanes should call these instead of re-deriving ordering/tie-breaking
rules from a model directly -- docs/contracts/data-authorization.md is the
authoritative semantics document; this module is the single implementation
of it. Nothing here is a route. Lane 5 owns wiring a query like
get_latest_assessment() into an actual HTTP endpoint
(docs/contracts/data-authorization.md section 4's contracted
`GET /learning/assessment/{player_id}/latest` is not implemented yet) and
into backend/routes/learning.py's existing pathway lookup, which today
orders by `created_at` only and does not yet use the `assessment_id`
tie-breaker below -- see LANE2_SYNC.md's Package H entry.
"""
from __future__ import annotations

from sqlalchemy import case
from sqlalchemy.orm import Session

from models.learning import CompetencyAssessment


def get_latest_assessment(
    db: Session, player_id: str, curriculum_slug: str
) -> CompetencyAssessment | None:
    """Return the single latest assessment row for one (player_id,
    curriculum_slug) stream, per docs/contracts/data-authorization.md
    section 4's exact ordering:

    1. non-null `created_at` sorts before null `created_at`;
    2. `created_at` descending; then
    3. `assessment_id` descending as the final, always-deterministic
       tie-breaker.

    Returns None when the stream has no assessment at all -- callers must
    not treat that the same as an assessment with zero self-ratings
    (CODEX.md "Architecture invariants": "no evidence" is not low ability).
    """
    return (
        db.query(CompetencyAssessment)
        .filter(
            CompetencyAssessment.player_id == player_id,
            CompetencyAssessment.curriculum_slug == curriculum_slug,
        )
        .order_by(
            case((CompetencyAssessment.created_at.is_(None), 1), else_=0).asc(),
            CompetencyAssessment.created_at.desc(),
            CompetencyAssessment.assessment_id.desc(),
        )
        .first()
    )
