"""Real trainer/content-reviewer approval workflow for AI-generated quizzes.

Before this route existed, a learner's own generated quiz (routes/
learning_content.py's POST /learning/quiz/generate) was permanently
private to its creator -- there was no way for a trainer to see it, and no
shared library of vetted, AI-generated quizzes other learners could
discover. There was also an existing, fully-built but completely unwired
per-item review state machine (ai/quiz_engine.py's QuizReviewWorkflow,
exposed statelessly at POST /ai/quiz/review with zero database behind
it -- confirmed by grep, nothing in this repo ever called it). This module
is the real, persisted version of that: a creator submits their quiz for
review, a content_reviewer/trainer approves or rejects it, and only an
approved quiz appears in the shared library other learners can browse and
take.

Deliberately scoped so existing self-serve behavior never changes: a
private quiz (the default, and the only state that existed before this
route) is exactly as before -- generate it, take it, done. This workflow
is opt-in, for a learner who wants to publish their quiz for others.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db
from models.learning import GeneratedQuiz, GeneratedQuizAttempt
from routes.authorization import (
    require_own_player,
    require_permission_dependency,
    require_principal,
)
from routes.learning_common import player_or_404
from security.rbac import BoundPrincipal, Permission

router = APIRouter(prefix="/learning/quiz", tags=["Quiz Review Workflow"])

# Either permission is sufficient to review/approve -- mirrors the existing
# (unwired) gate in routes/ai_real.py's quiz_review_item for the same two
# permissions, kept consistent rather than inventing a third rule.
_REVIEW_PERMISSIONS = {Permission.CONTENT_REVIEW, Permission.CONTENT_APPROVE}


def _require_reviewer(principal: BoundPrincipal) -> None:
    from security.rbac import permissions_for

    if not (permissions_for(principal) & _REVIEW_PERMISSIONS):
        raise HTTPException(status_code=403, detail="Access denied")


def _quiz_or_404(db: Session, quiz_id: str) -> GeneratedQuiz:
    quiz = db.query(GeneratedQuiz).filter(GeneratedQuiz.quiz_id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz


class SubmitForReviewRequest(BaseModel):
    player_id: str


@router.post("/{quiz_id}/submit-for-review")
async def submit_for_review(
    quiz_id: str,
    body: SubmitForReviewRequest,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.CONTENT_DRAFT_CREATE)
    ),
):
    require_own_player(principal, body.player_id)
    player_or_404(db, body.player_id)

    quiz = _quiz_or_404(db, quiz_id)
    if quiz.player_id != body.player_id:
        raise HTTPException(status_code=403, detail="This quiz belongs to a different player")
    if quiz.review_status not in ("private", "rejected"):
        raise HTTPException(
            status_code=422,
            detail=f"Quiz is already '{quiz.review_status}' -- only a private or rejected quiz can be submitted for review",
        )

    quiz.review_status = "pending_review"
    quiz.submitted_for_review_at = datetime.now(timezone.utc)
    quiz.reviewed_by = None
    quiz.reviewed_at = None
    quiz.reviewer_notes = None
    db.commit()
    return {"quiz_id": quiz.quiz_id, "review_status": quiz.review_status}


@router.get("/review/queue")
async def review_queue(
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(require_principal),
):
    """Every quiz awaiting a trainer/content_reviewer's decision -- full
    question content included, since a reviewer needs to actually read the
    questions to approve or reject them (unlike the learner-facing list
    endpoints, which never leak another player's quiz content)."""
    _require_reviewer(principal)
    quizzes = (
        db.query(GeneratedQuiz)
        .filter(GeneratedQuiz.review_status == "pending_review")
        .order_by(GeneratedQuiz.submitted_for_review_at.asc())
        .all()
    )
    return {
        "quizzes": [
            {
                "quiz_id": quiz.quiz_id,
                "title": quiz.title,
                "difficulty": quiz.difficulty,
                "language": quiz.language,
                "generation_mode": quiz.generation_mode,
                "questions": quiz.questions,
                "submitted_for_review_at": quiz.submitted_for_review_at.isoformat()
                if quiz.submitted_for_review_at
                else None,
            }
            for quiz in quizzes
        ]
    }


class ReviewDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    notes: str | None = Field(default=None, max_length=2000)


@router.post("/{quiz_id}/review")
async def review_quiz(
    quiz_id: str,
    body: ReviewDecisionRequest,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(require_principal),
):
    _require_reviewer(principal)
    quiz = _quiz_or_404(db, quiz_id)
    if quiz.review_status != "pending_review":
        raise HTTPException(
            status_code=422,
            detail=f"Quiz is '{quiz.review_status}', not pending review",
        )

    quiz.review_status = "published" if body.decision == "approve" else "rejected"
    quiz.reviewed_by = principal.audit_actor
    quiz.reviewed_at = datetime.now(timezone.utc)
    quiz.reviewer_notes = body.notes
    db.commit()
    return {
        "quiz_id": quiz.quiz_id,
        "review_status": quiz.review_status,
        "reviewed_by": quiz.reviewed_by,
        "reviewed_at": quiz.reviewed_at.isoformat(),
        "reviewer_notes": quiz.reviewer_notes,
    }


@router.get("/review/library")
async def quiz_library(
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(require_principal),
):
    """Every published quiz, browsable by any authenticated learner -- the
    real shared library the trainer-review workflow exists to feed."""
    quizzes = (
        db.query(GeneratedQuiz)
        .filter(GeneratedQuiz.review_status == "published")
        .order_by(GeneratedQuiz.reviewed_at.desc())
        .all()
    )
    return {
        "quizzes": [
            {
                "quiz_id": quiz.quiz_id,
                "title": quiz.title,
                "difficulty": quiz.difficulty,
                "language": quiz.language,
                "question_count": len(quiz.questions or []),
                "generation_mode": quiz.generation_mode,
                "reviewed_at": quiz.reviewed_at.isoformat() if quiz.reviewed_at else None,
            }
            for quiz in quizzes
        ]
    }


@router.get("/{quiz_id}/attempts")
async def list_attempts(
    quiz_id: str,
    player_id: str,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.PROFILE_SELF_READ)
    ),
):
    """A learner's own attempt history at one quiz -- distinct from
    GeneratedQuiz.best_score/last_attempted_at, which only ever reflects the
    quiz's original creator (see models/learning.py's GeneratedQuizAttempt
    docstring)."""
    require_own_player(principal, player_id)
    player_or_404(db, player_id)
    _quiz_or_404(db, quiz_id)

    rows = (
        db.query(GeneratedQuizAttempt)
        .filter(
            GeneratedQuizAttempt.quiz_id == quiz_id,
            GeneratedQuizAttempt.player_id == player_id,
        )
        .order_by(GeneratedQuizAttempt.attempted_at.desc())
        .all()
    )
    return {
        "attempts": [
            {
                "attempt_id": row.attempt_id,
                "correct_count": row.correct_count,
                "total_questions": row.total_questions,
                "weighted_score": row.weighted_score,
                "attempted_at": row.attempted_at.isoformat() if row.attempted_at else None,
            }
            for row in rows
        ]
    }
