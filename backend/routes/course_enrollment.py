"""Real enroll/complete lifecycle for services/learning_catalog.py's
recommend_courses() output.

Before this route existed, recommend_courses() computed real, gap-ranked,
provider-tagged course recommendations -- correctly -- but nothing in the
app ever called it from a route, and nothing rendered its output in the
frontend. A learner could never actually see, let alone act on, a single
recommendation. This closes both ends: the route here, and
frontend/components/RecommendedCourses.jsx on the UI side.

"igot"/"nssta" courses go through integrations/provider.py's
SimulatedIGOTAdapter, which is honestly and permanently labeled SIMULATED --
no real iGOT/NSSTA endpoint contract exists yet (see README's Known
limitations). A completed course writes evidence_type="provider_imported",
which learning_engine.py's UNSCORED_EVIDENCE_TYPES deliberately excludes
from competency scoring (recorded for transparency, not scored) -- exactly
the same "don't fabricate psychometric precision" boundary the rest of this
project holds everywhere else.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from integrations.provider import SimulatedIGOTAdapter
from models.course_enrollment import CourseEnrollment
from models.governance import EvidenceRecord
from routes.authorization import require_own_player, require_permission_dependency
from routes.learning_common import player_or_404
from security.rbac import BoundPrincipal, Permission

router = APIRouter(prefix="/learning/catalogue", tags=["Course Enrollment"])

_PROVIDER_PREFIXES = ("igot::", "nssta::")


def _parse_course_id(course_id: str) -> tuple[str, str]:
    """course_id is always "<provider>::<competency_id>", exactly as
    services/learning_catalog.py::recommend_courses() generates it -- no
    separate lookup table needed. Raises ValueError for anything else
    (e.g. an internal-practice course_id, which has nothing to enroll in)."""
    for prefix in _PROVIDER_PREFIXES:
        if course_id.startswith(prefix):
            return prefix.rstrip(":"), course_id[len(prefix):]
    raise ValueError(f"Not an enrollable provider course_id: {course_id!r}")


class EnrollRequest(BaseModel):
    player_id: str
    course_id: str
    title: str


@router.post("/enroll")
async def enroll(
    body: EnrollRequest,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.PRACTICE_SELF_WRITE)
    ),
):
    require_own_player(principal, body.player_id)
    player_or_404(db, body.player_id)

    try:
        provider, competency_id = _parse_course_id(body.course_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    existing = (
        db.query(CourseEnrollment)
        .filter(
            CourseEnrollment.player_id == body.player_id,
            CourseEnrollment.course_id == body.course_id,
        )
        .first()
    )
    if existing:
        return _serialize(existing)

    adapter = SimulatedIGOTAdapter()
    result = adapter.request_enrolment(body.course_id, idempotency_key=str(uuid.uuid4()))
    if not result.data.get("accepted"):
        raise HTTPException(status_code=502, detail="Provider declined the enrolment request")

    enrollment = CourseEnrollment(
        player_id=body.player_id,
        course_id=body.course_id,
        provider=provider,
        competency_id=competency_id,
        title=body.title,
        status="enrolled",
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)
    return _serialize(enrollment)


class CompleteRequest(BaseModel):
    player_id: str


@router.post("/enrollments/{enrollment_id}/complete")
async def complete(
    enrollment_id: str,
    body: CompleteRequest,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.PRACTICE_SELF_WRITE)
    ),
):
    require_own_player(principal, body.player_id)
    player_or_404(db, body.player_id)

    enrollment = (
        db.query(CourseEnrollment)
        .filter(
            CourseEnrollment.enrollment_id == enrollment_id,
            CourseEnrollment.player_id == body.player_id,
        )
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    if enrollment.status == "completed":
        return _serialize(enrollment)

    adapter = SimulatedIGOTAdapter()
    result = adapter.report_completion(enrollment.course_id)
    if not result.data.get("completed"):
        raise HTTPException(status_code=502, detail="Provider did not confirm completion")

    from datetime import datetime, timezone

    enrollment.status = "completed"
    enrollment.completed_at = datetime.now(timezone.utc)

    db.add(
        EvidenceRecord(
            player_id=body.player_id,
            competency_id=enrollment.competency_id,
            evidence_type="provider_imported",
            value=None,
            detail=f"{enrollment.provider}:{enrollment.course_id}",
        )
    )
    db.commit()
    db.refresh(enrollment)
    return _serialize(enrollment)


@router.get("/enrollments")
async def list_enrollments(
    player_id: str,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.PRACTICE_SELF_WRITE)
    ),
):
    require_own_player(principal, player_id)
    player_or_404(db, player_id)
    rows = db.query(CourseEnrollment).filter(CourseEnrollment.player_id == player_id).all()
    return {"enrollments": [_serialize(row) for row in rows]}


def _serialize(row: CourseEnrollment) -> dict:
    return {
        "enrollment_id": row.enrollment_id,
        "course_id": row.course_id,
        "provider": row.provider,
        "competency_id": row.competency_id,
        "title": row.title,
        "status": row.status,
        "enrolled_at": row.enrolled_at.isoformat() if row.enrolled_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
    }
