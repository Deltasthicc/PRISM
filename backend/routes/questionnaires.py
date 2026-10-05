"""Trainer-authored questionnaires with deadlines (SIH26075 PS75-08).

A trainer authors an MCQ questionnaire aimed at one of their own cohorts or
courses, publishes it, and trainees in that audience attempt it once before
the deadline. The trainer then sees participation and scores for their own
audience only.

Rules this module enforces (each has a test in tests/test_questionnaires.py):

- Identity: every route takes an explicit `trainer_id` / `player_id` and
  validates it with `require_own_player` (the DISABLE_AUTH demo principal
  has `player_id=None`, so identity is never read off the principal).
- Object scope: a questionnaire, cohort or course the caller does not own
  is a 404, never a 403, so probing reveals nothing.
- Lifecycle: draft -> published. Questions, audience and `due_at` can be
  edited only while unpublished AND with zero attempts. Once published the
  only mutation is `extend-deadline` (forward only). Publishing requires a
  `due_at` in the future on the server clock; creating a draft with a past
  `due_at` is allowed (the trainer fixes it before publishing).
- Time: the server clock only, via the single injectable `utcnow()` below.
  The client never supplies a timestamp that the server trusts. The
  deadline is inclusive: `now == due_at` is accepted, `now > due_at` is not.
- One attempt per trainee: a UNIQUE (questionnaire_id, player_id)
  constraint is the real guard; a repeat submit (or a lost insert race)
  returns the existing attempt unchanged.
- Confidentiality: `correct_index` is never serialized to a trainee until
  that trainee has submitted. A trainee never sees another trainee's data.

Scores are plain correct/total counts. They are deliberately NOT written as
competency `EvidenceRecord` rows: whether and how a trainer-authored
questionnaire should count toward competency is a separate, versioned
scoring-policy decision (CLAUDE.md), not something to fold in here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import AwareDatetime, BaseModel, Field, field_validator, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.database import get_db
from models.cohort import Cohort, CohortMembership
from models.course import Course
from models.course_enrollment import CourseEnrollment
from models.player import Player
from models.questionnaire import Questionnaire, QuestionnaireAttempt, QuestionnaireQuestion
from routes.authorization import require_own_player, require_permission_dependency
from routes.learning_common import player_or_404
from security.rbac import BoundPrincipal, Permission

router = APIRouter(prefix="/learning/questionnaires", tags=["Questionnaires"])

MAX_QUESTIONS = 50
MIN_OPTIONS = 2
MAX_OPTIONS = 6


def utcnow() -> datetime:
    """The one clock every deadline decision in this module reads.

    Tests replace this (`monkeypatch.setattr(routes.questionnaires, "utcnow",
    ...)`); nothing client-supplied ever substitutes for it.
    """
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes for timezone-aware columns; every
    value is stored as UTC, so a naive value is UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class QuestionInput(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=1000)
    options: list[str] = Field(..., min_length=MIN_OPTIONS, max_length=MAX_OPTIONS)
    correct_index: int = Field(..., ge=0)

    @field_validator("prompt")
    @classmethod
    def _prompt_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("prompt must not be blank")
        return value

    @field_validator("options")
    @classmethod
    def _options_clean(cls, value: list[str]) -> list[str]:
        cleaned = [option.strip() for option in value]
        if any(not option for option in cleaned):
            raise ValueError("options must be non-empty")
        if any(len(option) > 500 for option in cleaned):
            raise ValueError("each option must be at most 500 characters")
        return cleaned

    @model_validator(mode="after")
    def _correct_index_in_range(self) -> "QuestionInput":
        if self.correct_index >= len(self.options):
            raise ValueError("correct_index must point at one of the options")
        return self


class QuestionnaireWriteRequest(BaseModel):
    trainer_id: str
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field("", max_length=2000)
    audience_type: Literal["cohort", "course"]
    audience_id: str = Field(..., min_length=1, max_length=200)
    opens_at: AwareDatetime | None = None
    due_at: AwareDatetime
    questions: list[QuestionInput] = Field(..., min_length=1, max_length=MAX_QUESTIONS)

    @field_validator("title")
    @classmethod
    def _title_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("title must not be blank")
        return value

    @model_validator(mode="after")
    def _due_after_opens(self) -> "QuestionnaireWriteRequest":
        if self.opens_at is not None and self.due_at <= self.opens_at:
            raise ValueError("due_at must be later than opens_at")
        return self


class TrainerScopedRequest(BaseModel):
    trainer_id: str


class ExtendDeadlineRequest(BaseModel):
    trainer_id: str
    due_at: AwareDatetime


class SubmitRequest(BaseModel):
    player_id: str
    answers: dict[str, int]


class TrainerQuestion(BaseModel):
    question_id: str
    position: int
    prompt: str
    options: list[str]
    correct_index: int


class QuestionnaireResponse(BaseModel):
    """Trainer's own view; includes the answer key, so it is only ever
    returned to the owning trainer."""

    questionnaire_id: str
    trainer_id: str
    title: str
    description: str
    audience_type: str
    audience_id: str
    opens_at: datetime | None
    due_at: datetime
    is_published: bool
    attempt_count: int
    questions: list[TrainerQuestion]
    created_at: datetime
    updated_at: datetime


class TraineeQuestion(BaseModel):
    """No `correct_index` field exists on this type on purpose."""

    question_id: str
    position: int
    prompt: str
    options: list[str]


class QuestionResult(BaseModel):
    question_id: str
    position: int
    prompt: str
    options: list[str]
    selected_index: int
    correct_index: int
    is_correct: bool


class AttemptResult(BaseModel):
    attempt_id: str
    questionnaire_id: str
    player_id: str
    score: int
    max_score: int
    submitted_at: datetime
    is_late: bool
    questions: list[QuestionResult]


TraineeStatus = Literal["not_started", "submitted", "closed_missed"]


class AvailableQuestionnaire(BaseModel):
    questionnaire_id: str
    title: str
    description: str
    opens_at: datetime | None
    due_at: datetime
    status: TraineeStatus
    is_open: bool
    question_count: int
    score: int | None = None
    max_score: int | None = None


class TraineeQuestionnaireDetail(BaseModel):
    questionnaire_id: str
    title: str
    description: str
    opens_at: datetime | None
    due_at: datetime
    status: TraineeStatus
    is_open: bool
    # Empty once the deadline has passed without an attempt.
    questions: list[TraineeQuestion]
    # Present only after this trainee has submitted.
    attempt: AttemptResult | None = None


ResultStatus = Literal["submitted", "not_submitted", "missed_deadline"]


class ResultRow(BaseModel):
    player_id: str
    username: str
    status: ResultStatus
    score: int | None
    max_score: int | None
    submitted_at: datetime | None


class ResultAggregates(BaseModel):
    audience_size: int
    submitted_count: int
    mean_score: float | None
    max_score: int


class ResultsResponse(BaseModel):
    questionnaire_id: str
    title: str
    due_at: datetime
    deadline_passed: bool
    aggregates: ResultAggregates
    rows: list[ResultRow]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _questions_for(db: Session, questionnaire_id: str) -> list[QuestionnaireQuestion]:
    return (
        db.query(QuestionnaireQuestion)
        .filter(QuestionnaireQuestion.questionnaire_id == questionnaire_id)
        .order_by(QuestionnaireQuestion.position.asc())
        .all()
    )


def _attempt_count(db: Session, questionnaire_id: str) -> int:
    return (
        db.query(QuestionnaireAttempt)
        .filter(QuestionnaireAttempt.questionnaire_id == questionnaire_id)
        .count()
    )


def _serialize_for_trainer(db: Session, row: Questionnaire) -> QuestionnaireResponse:
    return QuestionnaireResponse(
        questionnaire_id=row.questionnaire_id,
        trainer_id=row.trainer_id,
        title=row.title,
        description=row.description,
        audience_type=row.audience_type,
        audience_id=row.audience_id,
        opens_at=_aware(row.opens_at),
        due_at=_aware(row.due_at),
        is_published=row.is_published,
        attempt_count=_attempt_count(db, row.questionnaire_id),
        questions=[
            TrainerQuestion(
                question_id=q.question_id,
                position=q.position,
                prompt=q.prompt,
                options=list(q.options),
                correct_index=q.correct_index,
            )
            for q in _questions_for(db, row.questionnaire_id)
        ],
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def _own_questionnaire_or_404(db: Session, questionnaire_id: str, trainer_id: str) -> Questionnaire:
    row = db.query(Questionnaire).filter(Questionnaire.questionnaire_id == questionnaire_id).one_or_none()
    # A missing row and someone else's row are deliberately indistinguishable.
    if row is None or row.trainer_id != trainer_id:
        raise HTTPException(status_code=404, detail="Questionnaire not found")
    return row


def _require_owned_audience(db: Session, trainer_id: str, audience_type: str, audience_id: str) -> None:
    if audience_type == "cohort":
        owned = (
            db.query(Cohort)
            .filter(Cohort.cohort_id == audience_id, Cohort.trainer_id == trainer_id)
            .one_or_none()
        )
    else:
        owned = (
            db.query(Course)
            .filter(Course.course_id == audience_id, Course.trainer_id == trainer_id)
            .one_or_none()
        )
    if owned is None:
        # Same response for "does not exist" and "belongs to someone else".
        raise HTTPException(status_code=404, detail="Audience not found")


def _audience_player_ids(db: Session, row: Questionnaire) -> list[str]:
    if row.audience_type == "cohort":
        query = db.query(CohortMembership.player_id).filter(CohortMembership.cohort_id == row.audience_id)
    else:
        query = db.query(CourseEnrollment.player_id).filter(
            CourseEnrollment.course_id == f"internal::{row.audience_id}"
        )
    return [player_id for (player_id,) in query.all()]


def _player_in_audience(db: Session, row: Questionnaire, player_id: str) -> bool:
    if row.audience_type == "cohort":
        found = (
            db.query(CohortMembership.membership_id)
            .filter(CohortMembership.cohort_id == row.audience_id, CohortMembership.player_id == player_id)
            .first()
        )
    else:
        found = (
            db.query(CourseEnrollment.enrollment_id)
            .filter(
                CourseEnrollment.course_id == f"internal::{row.audience_id}",
                CourseEnrollment.player_id == player_id,
            )
            .first()
        )
    return found is not None


def _visible_questionnaire_or_404(db: Session, questionnaire_id: str, player_id: str) -> Questionnaire:
    """Published and aimed at this player; anything else is a 404."""
    row = (
        db.query(Questionnaire)
        .filter(Questionnaire.questionnaire_id == questionnaire_id, Questionnaire.is_published.is_(True))
        .one_or_none()
    )
    if row is None or not _player_in_audience(db, row, player_id):
        raise HTTPException(status_code=404, detail="Questionnaire not found")
    return row


def _find_attempt(db: Session, questionnaire_id: str, player_id: str) -> QuestionnaireAttempt | None:
    return (
        db.query(QuestionnaireAttempt)
        .filter(
            QuestionnaireAttempt.questionnaire_id == questionnaire_id,
            QuestionnaireAttempt.player_id == player_id,
        )
        .one_or_none()
    )


def _is_open(row: Questionnaire, now: datetime) -> bool:
    opens_at = _aware(row.opens_at)
    return (opens_at is None or now >= opens_at) and now <= _aware(row.due_at)


def _trainee_status(row: Questionnaire, attempt: QuestionnaireAttempt | None, now: datetime) -> TraineeStatus:
    if attempt is not None:
        return "submitted"
    if now > _aware(row.due_at):
        return "closed_missed"
    return "not_started"


def _attempt_result(
    attempt: QuestionnaireAttempt, questions: list[QuestionnaireQuestion]
) -> AttemptResult:
    answers = attempt.answers or {}
    results = []
    for q in questions:
        selected = answers.get(q.question_id)
        results.append(
            QuestionResult(
                question_id=q.question_id,
                position=q.position,
                prompt=q.prompt,
                options=list(q.options),
                selected_index=selected if isinstance(selected, int) else -1,
                correct_index=q.correct_index,
                is_correct=selected == q.correct_index,
            )
        )
    return AttemptResult(
        attempt_id=attempt.attempt_id,
        questionnaire_id=attempt.questionnaire_id,
        player_id=attempt.player_id,
        score=attempt.score,
        max_score=attempt.max_score,
        submitted_at=_aware(attempt.submitted_at),
        is_late=attempt.is_late,
        questions=results,
    )


def _replace_questions(db: Session, questionnaire_id: str, questions: list[QuestionInput]) -> None:
    db.query(QuestionnaireQuestion).filter(
        QuestionnaireQuestion.questionnaire_id == questionnaire_id
    ).delete(synchronize_session=False)
    db.flush()
    for position, question in enumerate(questions):
        db.add(
            QuestionnaireQuestion(
                questionnaire_id=questionnaire_id,
                position=position,
                prompt=question.prompt,
                options=question.options,
                correct_index=question.correct_index,
            )
        )


def _require_editable(db: Session, row: Questionnaire) -> None:
    if row.is_published:
        raise HTTPException(
            status_code=409,
            detail="Questionnaire is published; unpublish it before editing (only the deadline can be extended).",
        )
    if _attempt_count(db, row.questionnaire_id) > 0:
        raise HTTPException(
            status_code=409,
            detail="Questionnaire already has attempts and can no longer be edited.",
        )


# ---------------------------------------------------------------------------
# Trainer routes
# ---------------------------------------------------------------------------


@router.post("", response_model=QuestionnaireResponse)
def create_questionnaire(
    body: QuestionnaireWriteRequest,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.QUESTIONNAIRE_MANAGE)),
    db: Session = Depends(get_db),
) -> QuestionnaireResponse:
    require_own_player(principal, body.trainer_id)
    player_or_404(db, body.trainer_id)
    _require_owned_audience(db, body.trainer_id, body.audience_type, body.audience_id)

    row = Questionnaire(
        trainer_id=body.trainer_id,
        title=body.title,
        description=body.description.strip(),
        audience_type=body.audience_type,
        audience_id=body.audience_id,
        opens_at=body.opens_at.astimezone(timezone.utc) if body.opens_at else None,
        due_at=body.due_at.astimezone(timezone.utc),
        is_published=False,
    )
    db.add(row)
    db.flush()
    _replace_questions(db, row.questionnaire_id, body.questions)
    db.commit()
    db.refresh(row)
    return _serialize_for_trainer(db, row)


@router.get("/mine", response_model=list[QuestionnaireResponse])
def list_my_questionnaires(
    trainer_id: str,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.QUESTIONNAIRE_MANAGE)),
    db: Session = Depends(get_db),
) -> list[QuestionnaireResponse]:
    require_own_player(principal, trainer_id)
    rows = (
        db.query(Questionnaire)
        .filter(Questionnaire.trainer_id == trainer_id)
        .order_by(Questionnaire.created_at.desc())
        .all()
    )
    return [_serialize_for_trainer(db, row) for row in rows]


@router.get("/available", response_model=list[AvailableQuestionnaire])
def list_available_questionnaires(
    player_id: str,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.QUESTIONNAIRE_ATTEMPT)),
    db: Session = Depends(get_db),
) -> list[AvailableQuestionnaire]:
    require_own_player(principal, player_id)
    player_or_404(db, player_id)

    cohort_ids = [
        cohort_id
        for (cohort_id,) in db.query(CohortMembership.cohort_id)
        .filter(CohortMembership.player_id == player_id)
        .all()
    ]
    prefix = "internal::"
    course_ids = [
        enrolled[len(prefix):]
        for (enrolled,) in db.query(CourseEnrollment.course_id)
        .filter(CourseEnrollment.player_id == player_id, CourseEnrollment.course_id.like(f"{prefix}%"))
        .all()
    ]

    rows: list[Questionnaire] = []
    if cohort_ids:
        rows += (
            db.query(Questionnaire)
            .filter(
                Questionnaire.is_published.is_(True),
                Questionnaire.audience_type == "cohort",
                Questionnaire.audience_id.in_(cohort_ids),
            )
            .all()
        )
    if course_ids:
        rows += (
            db.query(Questionnaire)
            .filter(
                Questionnaire.is_published.is_(True),
                Questionnaire.audience_type == "course",
                Questionnaire.audience_id.in_(course_ids),
            )
            .all()
        )
    rows.sort(key=lambda r: _aware(r.due_at))

    now = utcnow()
    out: list[AvailableQuestionnaire] = []
    for row in rows:
        attempt = _find_attempt(db, row.questionnaire_id, player_id)
        question_count = (
            db.query(QuestionnaireQuestion)
            .filter(QuestionnaireQuestion.questionnaire_id == row.questionnaire_id)
            .count()
        )
        out.append(
            AvailableQuestionnaire(
                questionnaire_id=row.questionnaire_id,
                title=row.title,
                description=row.description,
                opens_at=_aware(row.opens_at),
                due_at=_aware(row.due_at),
                status=_trainee_status(row, attempt, now),
                is_open=_is_open(row, now),
                question_count=question_count,
                # The trainee's own result only; never anyone else's.
                score=attempt.score if attempt else None,
                max_score=attempt.max_score if attempt else None,
            )
        )
    return out


@router.put("/{questionnaire_id}", response_model=QuestionnaireResponse)
def update_questionnaire(
    questionnaire_id: str,
    body: QuestionnaireWriteRequest,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.QUESTIONNAIRE_MANAGE)),
    db: Session = Depends(get_db),
) -> QuestionnaireResponse:
    require_own_player(principal, body.trainer_id)
    row = _own_questionnaire_or_404(db, questionnaire_id, body.trainer_id)
    _require_editable(db, row)
    _require_owned_audience(db, body.trainer_id, body.audience_type, body.audience_id)

    row.title = body.title
    row.description = body.description.strip()
    row.audience_type = body.audience_type
    row.audience_id = body.audience_id
    row.opens_at = body.opens_at.astimezone(timezone.utc) if body.opens_at else None
    row.due_at = body.due_at.astimezone(timezone.utc)
    _replace_questions(db, row.questionnaire_id, body.questions)
    db.commit()
    db.refresh(row)
    return _serialize_for_trainer(db, row)


@router.post("/{questionnaire_id}/publish", response_model=QuestionnaireResponse)
def publish_questionnaire(
    questionnaire_id: str,
    body: TrainerScopedRequest,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.QUESTIONNAIRE_MANAGE)),
    db: Session = Depends(get_db),
) -> QuestionnaireResponse:
    require_own_player(principal, body.trainer_id)
    row = _own_questionnaire_or_404(db, questionnaire_id, body.trainer_id)
    if not row.is_published:
        if _aware(row.due_at) <= utcnow():
            raise HTTPException(
                status_code=409,
                detail="Cannot publish: the deadline is not in the future. Edit the deadline first.",
            )
        # The audience may have changed hands since the draft was written.
        _require_owned_audience(db, row.trainer_id, row.audience_type, row.audience_id)
        row.is_published = True
        db.commit()
        db.refresh(row)
    return _serialize_for_trainer(db, row)


@router.post("/{questionnaire_id}/unpublish", response_model=QuestionnaireResponse)
def unpublish_questionnaire(
    questionnaire_id: str,
    body: TrainerScopedRequest,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.QUESTIONNAIRE_MANAGE)),
    db: Session = Depends(get_db),
) -> QuestionnaireResponse:
    require_own_player(principal, body.trainer_id)
    row = _own_questionnaire_or_404(db, questionnaire_id, body.trainer_id)
    if row.is_published:
        # Withdrawing hides it from trainees; existing attempts are kept and
        # the questions stay frozen (edits also require zero attempts).
        row.is_published = False
        db.commit()
        db.refresh(row)
    return _serialize_for_trainer(db, row)


@router.post("/{questionnaire_id}/extend-deadline", response_model=QuestionnaireResponse)
def extend_deadline(
    questionnaire_id: str,
    body: ExtendDeadlineRequest,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.QUESTIONNAIRE_MANAGE)),
    db: Session = Depends(get_db),
) -> QuestionnaireResponse:
    """The only mutation allowed on a published questionnaire: move `due_at`
    strictly later. The conditional UPDATE keeps it forward-only even if two
    extensions race."""
    require_own_player(principal, body.trainer_id)
    row = _own_questionnaire_or_404(db, questionnaire_id, body.trainer_id)
    new_due = body.due_at.astimezone(timezone.utc)
    if new_due <= _aware(row.due_at):
        raise HTTPException(status_code=422, detail="New deadline must be later than the current deadline.")
    if new_due <= utcnow():
        raise HTTPException(status_code=422, detail="New deadline must be in the future.")

    updated = (
        db.query(Questionnaire)
        .filter(
            Questionnaire.questionnaire_id == questionnaire_id,
            Questionnaire.trainer_id == body.trainer_id,
            Questionnaire.due_at < new_due,
        )
        .update({Questionnaire.due_at: new_due, Questionnaire.updated_at: utcnow()}, synchronize_session=False)
    )
    db.commit()
    if updated != 1:
        raise HTTPException(status_code=409, detail="The deadline was changed concurrently; reload and retry.")
    db.expire_all()
    row = _own_questionnaire_or_404(db, questionnaire_id, body.trainer_id)
    return _serialize_for_trainer(db, row)


@router.get("/{questionnaire_id}/results", response_model=ResultsResponse)
def questionnaire_results(
    questionnaire_id: str,
    trainer_id: str,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.QUESTIONNAIRE_MANAGE)),
    db: Session = Depends(get_db),
) -> ResultsResponse:
    """Participation and scores for this trainer's OWN audience only."""
    require_own_player(principal, trainer_id)
    row = _own_questionnaire_or_404(db, questionnaire_id, trainer_id)
    now = utcnow()
    due_at = _aware(row.due_at)
    deadline_passed = now > due_at

    audience_ids = _audience_player_ids(db, row)
    players = (
        {p.player_id: p for p in db.query(Player).filter(Player.player_id.in_(audience_ids)).all()}
        if audience_ids
        else {}
    )
    attempts = (
        {
            a.player_id: a
            for a in db.query(QuestionnaireAttempt)
            .filter(
                QuestionnaireAttempt.questionnaire_id == questionnaire_id,
                QuestionnaireAttempt.player_id.in_(audience_ids),
            )
            .all()
        }
        if audience_ids
        else {}
    )
    max_score = (
        db.query(QuestionnaireQuestion)
        .filter(QuestionnaireQuestion.questionnaire_id == questionnaire_id)
        .count()
    )

    rows: list[ResultRow] = []
    for player_id in sorted(players, key=lambda pid: players[pid].username.lower()):
        attempt = attempts.get(player_id)
        if attempt is not None:
            rows.append(
                ResultRow(
                    player_id=player_id,
                    username=players[player_id].username,
                    status="submitted",
                    score=attempt.score,
                    max_score=attempt.max_score,
                    submitted_at=_aware(attempt.submitted_at),
                )
            )
        else:
            rows.append(
                ResultRow(
                    player_id=player_id,
                    username=players[player_id].username,
                    status="missed_deadline" if deadline_passed else "not_submitted",
                    score=None,
                    max_score=None,
                    submitted_at=None,
                )
            )

    submitted = [r for r in rows if r.status == "submitted"]
    mean_score = round(sum(r.score for r in submitted) / len(submitted), 2) if submitted else None
    return ResultsResponse(
        questionnaire_id=row.questionnaire_id,
        title=row.title,
        due_at=due_at,
        deadline_passed=deadline_passed,
        aggregates=ResultAggregates(
            audience_size=len(rows),
            submitted_count=len(submitted),
            mean_score=mean_score,
            max_score=max_score,
        ),
        rows=rows,
    )


# ---------------------------------------------------------------------------
# Trainee routes
# ---------------------------------------------------------------------------


@router.get("/{questionnaire_id}", response_model=TraineeQuestionnaireDetail)
def get_questionnaire_for_trainee(
    questionnaire_id: str,
    player_id: str,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.QUESTIONNAIRE_ATTEMPT)),
    db: Session = Depends(get_db),
) -> TraineeQuestionnaireDetail:
    require_own_player(principal, player_id)
    row = _visible_questionnaire_or_404(db, questionnaire_id, player_id)
    now = utcnow()
    opens_at = _aware(row.opens_at)
    attempt = _find_attempt(db, questionnaire_id, player_id)
    questions = _questions_for(db, questionnaire_id)

    if attempt is None and opens_at is not None and now < opens_at:
        raise HTTPException(status_code=409, detail="This questionnaire has not opened yet.")

    status = _trainee_status(row, attempt, now)
    # Questions are only handed out while the trainee can still answer them.
    # After submission the full result (answer key included) is returned
    # through `attempt`; after a missed deadline there is nothing to answer.
    visible = [] if status != "not_started" else questions
    return TraineeQuestionnaireDetail(
        questionnaire_id=row.questionnaire_id,
        title=row.title,
        description=row.description,
        opens_at=opens_at,
        due_at=_aware(row.due_at),
        status=status,
        is_open=_is_open(row, now),
        questions=[
            TraineeQuestion(
                question_id=q.question_id, position=q.position, prompt=q.prompt, options=list(q.options)
            )
            for q in visible
        ],
        attempt=_attempt_result(attempt, questions) if attempt else None,
    )


@router.post("/{questionnaire_id}/submit", response_model=AttemptResult)
def submit_questionnaire(
    questionnaire_id: str,
    body: SubmitRequest,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.QUESTIONNAIRE_ATTEMPT)),
    db: Session = Depends(get_db),
) -> AttemptResult:
    require_own_player(principal, body.player_id)
    player_or_404(db, body.player_id)
    row = _visible_questionnaire_or_404(db, questionnaire_id, body.player_id)
    questions = _questions_for(db, questionnaire_id)

    # Idempotent: a repeat submit returns the original attempt unchanged,
    # even after the deadline (it is the trainee's already-recorded result).
    existing = _find_attempt(db, questionnaire_id, body.player_id)
    if existing is not None:
        return _attempt_result(existing, questions)

    now = utcnow()
    opens_at = _aware(row.opens_at)
    if opens_at is not None and now < opens_at:
        raise HTTPException(status_code=409, detail="This questionnaire has not opened yet.")
    if now > _aware(row.due_at):
        # Nothing is written: a late submission leaves no attempt row.
        raise HTTPException(status_code=409, detail="The deadline has passed; this questionnaire is closed.")

    expected_ids = {q.question_id for q in questions}
    provided_ids = set(body.answers)
    if provided_ids != expected_ids:
        raise HTTPException(status_code=422, detail="Answer every question exactly once.")
    score = 0
    for q in questions:
        selected = body.answers[q.question_id]
        if selected < 0 or selected >= len(q.options):
            raise HTTPException(status_code=422, detail="Selected option is out of range.")
        if selected == q.correct_index:
            score += 1

    attempt = QuestionnaireAttempt(
        questionnaire_id=questionnaire_id,
        player_id=body.player_id,
        answers={q.question_id: body.answers[q.question_id] for q in questions},
        score=score,
        max_score=len(questions),
        submitted_at=now,
        is_late=False,
    )
    db.add(attempt)
    try:
        db.commit()
    except IntegrityError:
        # A concurrent duplicate submit won the UNIQUE (questionnaire,
        # player) race; return the winner rather than a 500.
        db.rollback()
        winner = _find_attempt(db, questionnaire_id, body.player_id)
        if winner is None:
            raise
        return _attempt_result(winner, questions)
    db.refresh(attempt)
    return _attempt_result(attempt, questions)
