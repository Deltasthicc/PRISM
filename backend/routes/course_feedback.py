"""Real trainee feedback on a course (SIH26075 CC-05).

Upsert semantics implement the "one submission per trainee/content, with
edit rules" policy SIH26075_MASTER_CHECKLIST.md's PS75-06 calls for --
enforced at the database level too (models/feedback.py's unique
constraint), not only by this route's own lookup-then-branch.

The aggregate view deliberately never discloses which player wrote which
comment: this is a course-quality signal for anyone who can browse the
course (a trainee comparing options, the owning trainer, an admin), not a
per-reviewer identity disclosure. A player's own submission is only ever
returned to that same player, through the separate own-feedback route
below.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db
from models.course import Course
from models.course_enrollment import CourseEnrollment
from models.feedback import CourseFeedback
from routes.authorization import require_own_player, require_permission_dependency
from routes.learning_common import player_or_404
from security.rbac import BoundPrincipal, Permission

router = APIRouter(prefix="/learning/courses", tags=["Course Feedback"])


class FeedbackSubmitRequest(BaseModel):
    player_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: str = Field("", max_length=2000)


class FeedbackResponse(BaseModel):
    feedback_id: str
    course_id: str
    rating: int
    comment: str
    created_at: datetime
    updated_at: datetime


class FeedbackSummary(BaseModel):
    course_id: str
    average_rating: float | None
    count: int
    comments: list[str]


def _serialize(row: CourseFeedback) -> FeedbackResponse:
    return FeedbackResponse(
        feedback_id=row.feedback_id,
        course_id=row.course_id,
        rating=row.rating,
        comment=row.comment,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _course_or_404(db: Session, course_id: str) -> Course:
    course = db.query(Course).filter(Course.course_id == course_id).one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.post("/{course_id}/feedback", response_model=FeedbackResponse)
def submit_feedback(
    course_id: str,
    body: FeedbackSubmitRequest,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.COURSE_FEEDBACK_WRITE)),
    db: Session = Depends(get_db),
) -> FeedbackResponse:
    require_own_player(principal, body.player_id)
    player_or_404(db, body.player_id)
    _course_or_404(db, course_id)

    # Feedback is scoped to a genuine learner of this course -- anyone can
    # browse a course (Permission.COURSE_READ), but leaving feedback
    # requires having actually enrolled in it, any status. This is an
    # anti-abuse gate, not an evidence claim: enrollment alone, like
    # everywhere else in this codebase, is never treated as completion.
    enrolled = (
        db.query(CourseEnrollment)
        .filter(
            CourseEnrollment.player_id == body.player_id,
            CourseEnrollment.course_id == f"internal::{course_id}",
        )
        .first()
    )
    if enrolled is None:
        raise HTTPException(status_code=403, detail="Enroll in this course before leaving feedback")

    existing = (
        db.query(CourseFeedback)
        .filter(CourseFeedback.player_id == body.player_id, CourseFeedback.course_id == course_id)
        .one_or_none()
    )
    if existing is not None:
        existing.rating = body.rating
        existing.comment = body.comment.strip()
        db.commit()
        db.refresh(existing)
        return _serialize(existing)

    row = CourseFeedback(
        player_id=body.player_id,
        course_id=course_id,
        rating=body.rating,
        comment=body.comment.strip(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.get("/{course_id}/feedback/mine", response_model=FeedbackResponse | None)
def get_my_feedback(
    course_id: str,
    player_id: str,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.COURSE_FEEDBACK_WRITE)),
    db: Session = Depends(get_db),
) -> FeedbackResponse | None:
    require_own_player(principal, player_id)
    row = (
        db.query(CourseFeedback)
        .filter(CourseFeedback.player_id == player_id, CourseFeedback.course_id == course_id)
        .one_or_none()
    )
    return _serialize(row) if row is not None else None


@router.get("/{course_id}/feedback", response_model=FeedbackSummary)
def get_feedback_summary(
    course_id: str,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.COURSE_READ)),
    db: Session = Depends(get_db),
) -> FeedbackSummary:
    _course_or_404(db, course_id)
    rows = db.query(CourseFeedback).filter(CourseFeedback.course_id == course_id).all()
    if not rows:
        return FeedbackSummary(course_id=course_id, average_rating=None, count=0, comments=[])
    average = sum(row.rating for row in rows) / len(rows)
    comments = [row.comment for row in rows if row.comment]
    return FeedbackSummary(course_id=course_id, average_rating=round(average, 2), count=len(rows), comments=comments)
