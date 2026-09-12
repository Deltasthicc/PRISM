"""Real, persisted exam-integrity signal logging for a competency-quiz
attempt.

The actual face/phone detection runs entirely client-side
(frontend/components/ProctoringMonitor.jsx, via real in-browser ML models --
blazeface for face count, coco-ssd for phone detection) plus two
non-camera browser signals (tab-switch, fullscreen-exit). This route only
records the resulting events; no video frame or image is ever sent here --
see models/proctoring.py for the full privacy rationale.

This is intentionally a plain event log, not a pass/fail gate: a prototype
webcam classifier will produce false positives (poor lighting, a second
person briefly visible), so the honest behavior is to surface a violation
count for the learner/reviewer to weigh, never to auto-fail an attempt on
a single client-reported event.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from db.database import get_db
from models.proctoring import VIOLATION_TYPES, ProctoringEvent
from routes.authorization import require_own_player, require_permission_dependency
from routes.learning_common import player_or_404
from security.rbac import BoundPrincipal, Permission

router = APIRouter(prefix="/learning/proctoring", tags=["Exam Proctoring"])


class ViolationRequest(BaseModel):
    player_id: str
    attempt_id: str = Field(min_length=1, max_length=120)
    violation_type: str
    detail: str | None = Field(default=None, max_length=500)


def _serialize(row: ProctoringEvent) -> dict:
    return {
        "event_id": row.event_id,
        "attempt_id": row.attempt_id,
        "violation_type": row.violation_type,
        "detail": row.detail,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


@router.post("/violations")
async def report_violation(
    body: ViolationRequest,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.PRACTICE_SELF_WRITE)
    ),
):
    require_own_player(principal, body.player_id)
    player_or_404(db, body.player_id)

    if body.violation_type not in VIOLATION_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"violation_type must be one of {sorted(VIOLATION_TYPES)}",
        )

    event = ProctoringEvent(
        player_id=body.player_id,
        attempt_id=body.attempt_id,
        violation_type=body.violation_type,
        detail=body.detail,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    attempt_violation_count = (
        db.query(func.count(ProctoringEvent.event_id))
        .filter(
            ProctoringEvent.player_id == body.player_id,
            ProctoringEvent.attempt_id == body.attempt_id,
        )
        .scalar()
    )

    return {**_serialize(event), "attempt_violation_count": attempt_violation_count}


@router.get("/violations")
async def list_violations(
    player_id: str,
    attempt_id: str,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.PRACTICE_SELF_WRITE)
    ),
):
    require_own_player(principal, player_id)
    player_or_404(db, player_id)

    rows = (
        db.query(ProctoringEvent)
        .filter(
            ProctoringEvent.player_id == player_id,
            ProctoringEvent.attempt_id == attempt_id,
        )
        .order_by(ProctoringEvent.created_at.asc())
        .all()
    )
    return {"violations": [_serialize(row) for row in rows]}
