"""Trainer-authored course catalog (SIH26075 CC-03/CC-06/CC-09).

A trainer drafts a course, then publishes it once ready; a trainee browses
only published courses. Enrollment in one of these lives in
`routes/course_enrollment.py` (the `"internal::<course_id>"` provider path
added there), not here -- this file only owns the course record itself.

Every write route checks the acting principal actually owns the course
being modified, the same shape `require_own_player_dependency` already
establishes for players -- `Permission.COURSE_MANAGE` says "this principal
may manage *a* course", never "this principal may manage *any* course".
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db
from models.course import Course
from routes.authorization import require_permission_dependency
from security.rbac import BoundPrincipal, Permission

router = APIRouter(prefix="/learning/courses", tags=["Course Catalog"])


class CourseCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=300)
    description: str = Field("", max_length=5000)
    competency_id: str = Field(..., min_length=1, max_length=200)


class CourseResponse(BaseModel):
    course_id: str
    trainer_id: str
    title: str
    description: str
    competency_id: str
    is_published: bool
    created_at: datetime
    updated_at: datetime


def _serialize(course: Course) -> CourseResponse:
    return CourseResponse(
        course_id=course.course_id,
        trainer_id=course.trainer_id,
        title=course.title,
        description=course.description,
        competency_id=course.competency_id,
        is_published=course.is_published,
        created_at=course.created_at,
        updated_at=course.updated_at,
    )


def _own_course_or_404(db: Session, course_id: str, principal: BoundPrincipal) -> Course:
    course = db.query(Course).filter(Course.course_id == course_id).one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    if course.trainer_id != principal.player_id:
        # Deliberately identical to a not-found response: a trainer probing
        # course ids they don't own should learn nothing about whether the
        # id exists, matching this codebase's existing "Access denied" /
        # object-scope conventions elsewhere (routes/authorization.py).
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.post("", response_model=CourseResponse)
def create_course(
    body: CourseCreateRequest,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.COURSE_MANAGE)),
    db: Session = Depends(get_db),
) -> CourseResponse:
    if principal.player_id is None:
        raise HTTPException(status_code=422, detail="Principal has no bound player to author as")
    course = Course(
        trainer_id=principal.player_id,
        title=body.title.strip(),
        description=body.description.strip(),
        competency_id=body.competency_id.strip(),
        is_published=False,
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    return _serialize(course)


@router.post("/{course_id}/publish", response_model=CourseResponse)
def publish_course(
    course_id: str,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.COURSE_MANAGE)),
    db: Session = Depends(get_db),
) -> CourseResponse:
    course = _own_course_or_404(db, course_id, principal)
    course.is_published = True
    db.commit()
    db.refresh(course)
    return _serialize(course)


@router.post("/{course_id}/unpublish", response_model=CourseResponse)
def unpublish_course(
    course_id: str,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.COURSE_MANAGE)),
    db: Session = Depends(get_db),
) -> CourseResponse:
    course = _own_course_or_404(db, course_id, principal)
    course.is_published = False
    db.commit()
    db.refresh(course)
    return _serialize(course)


@router.get("/mine", response_model=list[CourseResponse])
def list_my_courses(
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.COURSE_MANAGE)),
    db: Session = Depends(get_db),
) -> list[CourseResponse]:
    rows = (
        db.query(Course)
        .filter(Course.trainer_id == principal.player_id)
        .order_by(Course.created_at.desc())
        .all()
    )
    return [_serialize(row) for row in rows]


@router.get("", response_model=list[CourseResponse])
def list_published_courses(
    competency_id: str | None = None,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.COURSE_READ)),
    db: Session = Depends(get_db),
) -> list[CourseResponse]:
    query = db.query(Course).filter(Course.is_published.is_(True))
    if competency_id:
        query = query.filter(Course.competency_id == competency_id)
    rows = query.order_by(Course.created_at.desc()).all()
    return [_serialize(row) for row in rows]


@router.get("/{course_id}", response_model=CourseResponse)
def get_published_course(
    course_id: str,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.COURSE_READ)),
    db: Session = Depends(get_db),
) -> CourseResponse:
    course = (
        db.query(Course)
        .filter(Course.course_id == course_id, Course.is_published.is_(True))
        .one_or_none()
    )
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return _serialize(course)
