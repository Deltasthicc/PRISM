"""Real, persisted live quiz-session lifecycle -- the "QR-code live
classroom quiz" feature (routes/live_sessions.py). A trainer hosts a shared,
paced session from an existing GeneratedQuiz (their own private quiz, or any
already-published one -- see models/learning.py's GeneratedQuiz.review_status
lifecycle and routes/quiz_review.py), generates a short human-typeable
join_code, and participants join on their own device (phone or laptop) to
answer in lockstep with the host -- every participant sees the same question
at the same time, not a self-paced quiz.

Deliberately reuses GeneratedQuiz's `questions` JSON rather than duplicating
that schema: a live session is just a shared, paced "take" of an existing
quiz, not a separate content type. Each participant's final score is
computed with services/quiz_scoring.py's same weighted-scoring algorithm the
single-player quiz flow already uses (see routes/live_sessions.py's end()
for why the time factor is always neutral here -- a live session has no
per-question timing signal to honestly report).

Follows models/course_enrollment.py's docstring/style conventions.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint
from db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class LiveQuizSession(Base):
    """One trainer-hosted live session of a single GeneratedQuiz. The host
    controls pacing via `current_question_index` -- there is no per-learner
    self-pacing here, unlike the ordinary single-player quiz flow."""

    __tablename__ = "live_quiz_sessions"

    session_id = Column(String, primary_key=True, default=generate_uuid)
    quiz_id = Column(String, ForeignKey("generated_quizzes.quiz_id"), nullable=False, index=True)
    host_player_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)

    # Short, human-typeable code a participant enters on their own device --
    # deliberately NOT the full session_id. See routes/live_sessions.py's
    # _JOIN_CODE_ALPHABET/_generate_unique_join_code for the exact alphabet,
    # length, and collision-retry rationale.
    join_code = Column(String, nullable=False, unique=True, index=True)

    status = Column(String, nullable=False, default="waiting")  # waiting | active | ended
    current_question_index = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    ended_at = Column(DateTime(timezone=True), nullable=True)


class LiveSessionParticipant(Base):
    """One learner's real-time participation in one LiveQuizSession.
    `answers` accumulates as {str(question_index): selected_index} while the
    session is live (see routes/live_sessions.py's answer endpoint for why
    only an answer to the session's CURRENT question is ever accepted);
    `score` stays None until the host ends the session, at which point it is
    computed once, honestly, from the real questions/answers -- never
    fabricated or estimated early."""

    __tablename__ = "live_session_participants"
    __table_args__ = (
        UniqueConstraint("session_id", "player_id", name="uq_live_session_participant"),
    )

    participant_id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("live_quiz_sessions.session_id"), nullable=False, index=True)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)

    joined_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    answers = Column(JSON, nullable=False, default=dict)
    score = Column(Float, nullable=True)
