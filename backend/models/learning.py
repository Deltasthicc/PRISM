"""
Learner profile, competency assessment, learning material, and generated quiz
SQLAlchemy models -- the persistence layer for the cross-domain skill
intelligence features (see services/curricula.py, learning_engine.py,
quiz_generator.py, and routes/learning.py).

These are brand-new tables, so plain Base.metadata.create_all() in main.py's
lifespan is enough; unlike the Phase 2/3 columns added to `players` in
db/database.py's ensure_columns() calls, nothing here alters an existing
table.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, JSON, String
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
    services/quiz_generator.py). Never rewritten after creation."""

    __tablename__ = "generated_quizzes"

    quiz_id = Column(String, primary_key=True, default=generate_uuid)
    material_id = Column(String, ForeignKey("learning_materials.material_id"), nullable=False, index=True)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)

    title = Column(String, nullable=False)
    difficulty = Column(String, default="mixed")
    language = Column(String, default="English")
    questions = Column(JSON, default=list)
    generation_mode = Column(String, default="extractive-fallback")

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
