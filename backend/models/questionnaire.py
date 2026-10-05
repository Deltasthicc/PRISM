"""Trainer-authored, deadline-bound MCQ questionnaires (SIH26075 PS75-08).

Distinct from `models.learning.GeneratedQuiz` (AI-generated drafts reviewed
through routes/quiz_review.py): every row here is authored by a trainer,
targeted at an audience that trainer already owns (one of their cohorts or
one of their courses), and attempted by trainees before a server-enforced
deadline.

Design notes:
- `(questionnaire_id, player_id)` is UNIQUE on attempts: one attempt per
  trainee, enforced by the database rather than a check-then-insert.
- `(questionnaire_id, position)` is UNIQUE on questions so ordering can
  never silently collide.
- Scores here are plain correct/total counts. They are deliberately NOT
  written as competency `EvidenceRecord` rows: how a trainer-authored
  questionnaire should weigh into competency scoring is a versioned
  scoring-policy decision (CLAUDE.md), not a side effect of this table.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Questionnaire(Base):
    __tablename__ = "questionnaires"
    __table_args__ = (
        CheckConstraint(
            "audience_type IN ('cohort', 'course')",
            name="ck_questionnaire_audience_type",
        ),
        CheckConstraint(
            "opens_at IS NULL OR due_at > opens_at",
            name="ck_questionnaire_due_after_opens",
        ),
    )

    questionnaire_id = Column(String, primary_key=True, default=generate_uuid)
    trainer_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(String(2000), nullable=False, default="")
    # "cohort" -> audience_id is a cohorts.cohort_id; "course" -> a bare
    # courses.course_id (enrollment rows carry it as "internal::<course_id>").
    # Not a foreign key because it targets one of two tables; ownership is
    # validated server-side at write time instead.
    audience_type = Column(String, nullable=False)
    audience_id = Column(String, nullable=False, index=True)
    opens_at = Column(DateTime(timezone=True), nullable=True)
    due_at = Column(DateTime(timezone=True), nullable=False)
    is_published = Column(Boolean, nullable=False, default=False, index=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=_now, onupdate=_now)


class QuestionnaireQuestion(Base):
    __tablename__ = "questionnaire_questions"
    __table_args__ = (
        UniqueConstraint("questionnaire_id", "position", name="uq_questionnaire_question_position"),
        CheckConstraint("position >= 0", name="ck_questionnaire_question_position"),
        CheckConstraint("correct_index >= 0", name="ck_questionnaire_question_correct_index"),
    )

    question_id = Column(String, primary_key=True, default=generate_uuid)
    questionnaire_id = Column(
        String, ForeignKey("questionnaires.questionnaire_id"), nullable=False, index=True
    )
    position = Column(Integer, nullable=False)
    prompt = Column(String(1000), nullable=False)
    options = Column(JSON, nullable=False)  # list of 2-6 non-empty strings
    correct_index = Column(Integer, nullable=False)


class QuestionnaireAttempt(Base):
    __tablename__ = "questionnaire_attempts"
    __table_args__ = (
        UniqueConstraint(
            "questionnaire_id", "player_id", name="uq_questionnaire_attempt_questionnaire_player"
        ),
        CheckConstraint("score >= 0 AND score <= max_score", name="ck_questionnaire_attempt_score"),
    )

    attempt_id = Column(String, primary_key=True, default=generate_uuid)
    questionnaire_id = Column(
        String, ForeignKey("questionnaires.questionnaire_id"), nullable=False, index=True
    )
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)
    answers = Column(JSON, nullable=False)  # {question_id: selected_index}
    score = Column(Integer, nullable=False)
    max_score = Column(Integer, nullable=False)
    submitted_at = Column(DateTime(timezone=True), nullable=False, default=_now)
    # Submissions after the deadline are rejected outright (no row), so this
    # is always False today; kept so a future "accept late, flagged" policy
    # does not need a migration.
    is_late = Column(Boolean, nullable=False, default=False)
