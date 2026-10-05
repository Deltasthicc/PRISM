"""Real enroll/complete lifecycle for two distinct kinds of course.

1. "igot"/"nssta" -- services/learning_catalog.py::recommend_courses()
   output. Computed correctly but, before this route existed, nothing in
   the app ever called it from a route or rendered its output in the
   frontend; a learner could never actually see, let alone act on, a single
   recommendation. This closes both ends: the route here, and
   frontend/components/RecommendedCourses.jsx on the UI side. These go
   through integrations/provider.py's SimulatedIGOTAdapter, which is
   honestly and permanently labeled SIMULATED -- no real iGOT/NSSTA
   endpoint contract exists yet (see README's Known limitations).
2. "internal" -- a real, trainer-authored `models.course.Course` row
   (routes/course_catalog.py). Not imported, not simulated: this platform
   is the source of truth, so enrolling/completing one is a plain database
   write with no adapter call at all.

Both write evidence_type="provider_imported", which
learning_engine.py's UNSCORED_EVIDENCE_TYPES deliberately excludes from
competency scoring. For the "internal" case this is a deliberate, narrower
choice than it might look: an internal course is more verifiable than an
external import, but whether completing one should carry real scoring
weight is a scoring-policy decision this project requires to be an
explicit, versioned choice (see CLAUDE.md's "65/35 blend... remain
versioned prototype policies until validated"), not something to fold in
quietly as a side effect of adding the model. Recorded for transparency,
not scored, until that policy decision is made on its own.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.database import get_db
from integrations.provider import SimulatedIGOTAdapter
from models.certificate import Certificate
from models.course import Course
from models.course_enrollment import CourseEnrollment
from models.governance import EvidenceRecord
from routes.authorization import require_own_player, require_permission_dependency
from routes.learning_common import player_or_404
from security.rbac import BoundPrincipal, Permission

router = APIRouter(prefix="/learning/catalogue", tags=["Course Enrollment"])

_PROVIDER_PREFIXES = ("igot::", "nssta::", "internal::")


def _parse_course_id(course_id: str) -> tuple[str, str]:
    """course_id is always "<provider>::<value>". For "igot"/"nssta" that
    value is a competency_id, exactly as
    services/learning_catalog.py::recommend_courses() generates it. For
    "internal" it is a real `courses.course_id` primary key instead (see
    `_resolve_internal_course`). Raises ValueError for anything else (e.g.
    an internal-practice recommendation course_id, which has nothing to
    enroll in)."""
    for prefix in _PROVIDER_PREFIXES:
        if course_id.startswith(prefix):
            return prefix.rstrip(":"), course_id[len(prefix):]
    raise ValueError(f"Not an enrollable provider course_id: {course_id!r}")


def _resolve_internal_course(db: Session, course_id: str) -> Course:
    _, real_course_id = _parse_course_id(course_id)
    course = (
        db.query(Course)
        .filter(Course.course_id == real_course_id, Course.is_published.is_(True))
        .one_or_none()
    )
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found or not published")
    return course


def _find_enrollment(db: Session, player_id: str, course_id: str) -> CourseEnrollment | None:
    return (
        db.query(CourseEnrollment)
        .filter(CourseEnrollment.player_id == player_id, CourseEnrollment.course_id == course_id)
        .first()
    )


def _find_owned_enrollment(db: Session, enrollment_id: str, player_id: str) -> CourseEnrollment | None:
    return (
        db.query(CourseEnrollment)
        .filter(CourseEnrollment.enrollment_id == enrollment_id, CourseEnrollment.player_id == player_id)
        .first()
    )


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
        provider, _ = _parse_course_id(body.course_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    existing = _find_enrollment(db, body.player_id, body.course_id)
    if existing:
        return _serialize(existing)

    if provider == "internal":
        course = _resolve_internal_course(db, body.course_id)
        competency_id = course.competency_id
        title = course.title
    else:
        adapter = SimulatedIGOTAdapter()
        result = adapter.request_enrolment(body.course_id, idempotency_key=str(uuid.uuid4()))
        if not result.data.get("accepted"):
            raise HTTPException(status_code=502, detail="Provider declined the enrolment request")
        _, competency_id = _parse_course_id(body.course_id)
        title = body.title

    enrollment = CourseEnrollment(
        player_id=body.player_id,
        course_id=body.course_id,
        provider=provider,
        competency_id=competency_id,
        title=title,
        status="enrolled",
    )
    db.add(enrollment)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent request (double-click, retry) inserted the same
        # (player, course) row between the check above and this commit; the
        # unique constraint is the real guard, so enrolling stays idempotent
        # instead of surfacing a 500.
        db.rollback()
        winner = _find_enrollment(db, body.player_id, body.course_id)
        if winner is None:
            raise
        return _serialize(winner)
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

    enrollment = _find_owned_enrollment(db, enrollment_id, body.player_id)
    if not enrollment:
        raise HTTPException(status_code=404, detail="Enrollment not found")
    if enrollment.status == "completed":
        return _serialize(enrollment)

    if enrollment.provider != "internal":
        adapter = SimulatedIGOTAdapter()
        result = adapter.report_completion(enrollment.course_id)
        if not result.data.get("completed"):
            raise HTTPException(status_code=502, detail="Provider did not confirm completion")

    # Atomic claim: only the one request that flips status away from
    # "completed" goes on to write evidence and issue the certificate. A
    # concurrent duplicate sees zero rows updated and just returns the
    # already-completed enrollment, so completion never double-records.
    claimed = (
        db.query(CourseEnrollment)
        .filter(
            CourseEnrollment.enrollment_id == enrollment_id,
            CourseEnrollment.player_id == body.player_id,
            CourseEnrollment.status != "completed",
        )
        .update(
            {"status": "completed", "completed_at": datetime.now(timezone.utc)},
            synchronize_session=False,
        )
    )
    if claimed == 0:
        db.rollback()
        db.expire_all()
        return _serialize(_find_owned_enrollment(db, enrollment_id, body.player_id))

    db.add(
        EvidenceRecord(
            player_id=body.player_id,
            competency_id=enrollment.competency_id,
            evidence_type="provider_imported",
            value=None,
            detail=f"{enrollment.provider}:{enrollment.course_id}",
        )
    )
    if enrollment.provider == "internal":
        # A real completion certificate, not a claim -- issued exactly once
        # per (player, course) here at the moment completion is first
        # recorded above (this whole branch is unreachable on a repeat
        # call: the `enrollment.status == "completed"` check earlier in
        # this function already returned). title is a snapshot, not a live
        # join, so the certificate stays valid and readable even if the
        # source course is later renamed or unpublished (see
        # models/certificate.py's docstring). Stored as the bare
        # `courses.course_id` (stripping the "internal::" enrollment
        # prefix, which only exists to disambiguate a provider inside
        # CourseEnrollment), matching how models/feedback.py's real FK
        # references the same course -- so a certificate's course_id and a
        # feedback row's course_id for "the same course" are always the
        # identical string.
        _, real_course_id = _parse_course_id(enrollment.course_id)
        db.add(
            Certificate(
                player_id=body.player_id,
                course_id=real_course_id,
                title=enrollment.title,
            )
        )
    db.commit()
    db.expire_all()
    return _serialize(_find_owned_enrollment(db, enrollment_id, body.player_id))


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
