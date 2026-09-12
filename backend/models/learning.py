"""
Learner profile, competency assessment, learning material, and generated quiz
SQLAlchemy models -- the persistence layer for the cross-domain skill
intelligence features (see services/curricula.py, learning_engine.py,
quiz_generator.py, and routes/learning.py).

These were brand-new tables when this module was first written, so plain
Base.metadata.create_all() in main.py's lifespan was enough on its own.
That stopped being true the moment `full_name` was added to the
already-existing `learner_profiles` table: create_all() never alters an
existing table's columns, so any local SQLite app.db created before that
change is permanently missing the column until main.py's lifespan also
calls db/database.py's ensure_columns("learner_profiles", ...) for it --
confirmed as a real, reproduced bug (every learner_profiles read 500ing
with "no such column: learner_profiles.full_name" against a pre-existing
demo database). Adding a column to any model here now requires the
matching ensure_columns() call in main.py, the same discipline the
Phase 2/3 `players` columns already follow -- this docstring's original
"nothing here alters an existing table" claim does not hold in general.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, JSON, String
from db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class LearnerProfile(Base):
    """One row per player -- the role/context inputs the gap engine reads.

    Field set mirrors schemas.learning.LearnerProfileUpsert exactly; routes/
    learning.py's upsert_profile() setattr-loops over every field in that
    schema onto this model, so the two must stay in lockstep.
    """

    __tablename__ = "learner_profiles"

    profile_id = Column(String, primary_key=True, default=generate_uuid)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False, unique=True, index=True)

    full_name = Column(String, default="")
    designation = Column(String, default="")
    department = Column(String, default="")
    job_role = Column(String, default="")
    current_assignment = Column(String, default="")
    educational_qualifications = Column(String, default="")
    years_experience = Column(Integer, default=0)
    previous_trainings = Column(JSON, default=list)
    career_goal = Column(String, default="")
    preferred_language = Column(String, default="English")
    experience_level = Column(String, default="beginner")  # beginner | intermediate | advanced | expert
    target_domains = Column(JSON, default=list)  # curriculum slugs (services/curricula.py) this learner is pursuing

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class CompetencyAssessment(Base):
    """One row per assessment run -- an immutable snapshot, not an editable record.

    get_pathway() re-derives a live result from the *latest* row's
    self_ratings plus fresh measured_scores, so a stale assessment never
    silently drifts from current quest performance.
    """

    __tablename__ = "competency_assessments"
    __table_args__ = (
        # Matches get_latest_assessment()'s exact WHERE/ORDER BY shape
        # (db/repositories.py) -- benchmarked against a representative
        # 120k-row PostgreSQL table: PostgreSQL planner cost 109.52 -> 16.02
        # for the query this repository function issues (Package 4).
        Index(
            "ix_competency_assessments_lookup_newest",
            "player_id",
            "curriculum_slug",
            "created_at",
            "assessment_id",
        ),
    )

    assessment_id = Column(String, primary_key=True, default=generate_uuid)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)
    curriculum_slug = Column(String, nullable=False, index=True)

    self_ratings = Column(JSON, default=dict)       # {competency_id: 0-5}
    measured_scores = Column(JSON, default=dict)    # {competency_id: 0-5}, derived from AccuracyHistory
    skill_gaps = Column(JSON, default=list)
    recommended_course_ids = Column(JSON, default=list)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LearningMaterial(Base):
    """Metadata for an uploaded document -- never the original file or full
    extracted body. Only a hash (dedupe / integrity check), a character
    count, and a short excerpt are persisted; see services/content_ingestion.py
    for the bounds enforced before text ever reaches this table."""

    __tablename__ = "learning_materials"

    material_id = Column(String, primary_key=True, default=generate_uuid)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)

    filename = Column(String, nullable=False)
    content_type = Column(String, default="application/octet-stream")
    sha256 = Column(String, nullable=False, index=True)
    character_count = Column(Integer, default=0)
    text_excerpt = Column(String, default="")

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class GeneratedQuiz(Base):
    """A generated quiz's questions, verbatim, plus which generation path
    produced them ("gemini-grounded" or "extractive-fallback" -- see
    services/quiz_generator.py). `questions` itself is never rewritten after
    creation; `review_status` and the reviewer fields below are, via the
    real trainer review/approval workflow in routes/quiz_review.py."""

    __tablename__ = "generated_quizzes"

    quiz_id = Column(String, primary_key=True, default=generate_uuid)
    material_id = Column(String, ForeignKey("learning_materials.material_id"), nullable=False, index=True)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)

    title = Column(String, nullable=False)
    difficulty = Column(String, default="mixed")
    language = Column(String, default="English")
    questions = Column(JSON, default=list)
    generation_mode = Column(String, default="extractive-fallback")

    # Denormalized best-attempt summary -- see routes/learning_content.py's
    # POST /learning/quiz/{quiz_id}/submit. Reflects only the OWNER's own
    # attempts (routes/quiz_review.py's published-quiz-library lets other
    # learners take a copy too; their attempts land in GeneratedQuizAttempt
    # instead, so a non-owner's score never overwrites the creator's own
    # best_score). Deliberately NOT written into AccuracyHistory/the real
    # competency vector, since a generated quiz's `competency` field is free
    # text from the model or the extractive fallback, not a real curriculum
    # competency_id (see services/curricula.py). This is a real, honest score
    # for this one quiz, not curriculum evidence.
    best_score = Column(Float, nullable=True)
    last_attempted_at = Column(DateTime(timezone=True), nullable=True)

    # Real trainer review/approval lifecycle (routes/quiz_review.py):
    # private (default, only the creator can see/take it, current behavior
    # unchanged) -> pending_review (creator submitted it for publication) ->
    # published (a content_reviewer/trainer approved it -- now listed in the
    # shared quiz library for any learner) or rejected (resubmittable).
    review_status = Column(String, nullable=False, default="private", server_default="private")
    submitted_for_review_at = Column(DateTime(timezone=True), nullable=True)
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    reviewer_notes = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class GeneratedQuizAttempt(Base):
    """One real, persisted attempt at a GeneratedQuiz, by whoever took it --
    not just the quiz's creator. Exists because a published quiz (see
    review_status above) can be taken by any learner, and GeneratedQuiz's
    own best_score/last_attempted_at columns are a single slot that must
    keep reflecting the CREATOR's own attempts (routes/learning_content.py's
    existing submit flow), not get overwritten by someone else's score."""

    __tablename__ = "generated_quiz_attempts"

    attempt_id = Column(String, primary_key=True, default=generate_uuid)
    quiz_id = Column(String, ForeignKey("generated_quizzes.quiz_id"), nullable=False, index=True)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)

    correct_count = Column(Integer, nullable=False)
    total_questions = Column(Integer, nullable=False)
    weighted_score = Column(Float, nullable=False)

    attempted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
