"""
Player SQLAlchemy model.
"""
import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Boolean, CheckConstraint, Column, Float, String, Integer, DateTime, ForeignKey,
)
from sqlalchemy.dialects.sqlite import TEXT
from sqlalchemy.orm import relationship
from db.database import Base
from models.enums import DEFAULT_LEARNING_MODE, LEARNING_MODE_VALUES


def generate_uuid():
    return str(uuid.uuid4())


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (
        # Same name as migrations/versions/640603a37f2f_*.py's constraint --
        # keeping the two in lockstep (name and allowed values) is what
        # keeps `alembic check` clean and what makes a fresh SQLite database
        # (Base.metadata.create_all(), the real zero-setup-demo runtime
        # path, which never runs Alembic at all) enforce the same rule a
        # migration-managed PostgreSQL database does. A pre-existing SQLite
        # demo file upgraded only through db/database.py's ensure_columns()
        # (a plain ALTER TABLE ADD COLUMN) does NOT get this constraint --
        # SQLite cannot ALTER a constraint onto an existing table outside
        # Alembic's batch/copy-and-move mode -- matching this project's
        # existing precedent that ensure_columns() is best-effort
        # compatibility, not enforcement, for every other column it adds.
        CheckConstraint(
            f"preferred_mode IN ({', '.join(repr(v) for v in LEARNING_MODE_VALUES)})",
            name="ck_players_preferred_mode_known_value",
        ),
    )

    player_id = Column(String, primary_key=True, default=generate_uuid)
    username = Column(String, unique=True, nullable=False, index=True)
    level = Column(Integer, default=1)
    total_xp = Column(Integer, default=0)
    streak_days = Column(Integer, default=0)
    last_active = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    guild_id = Column(String, ForeignKey("guilds.guild_id"), nullable=True)
    hint_tokens = Column(Integer, default=lambda: int(os.getenv("MAX_HINT_TOKENS", "3")))

    # Phase 2/3: character + powerup state
    hero_id = Column(String, nullable=True)
    pending_xp_multiplier = Column(Float, default=1.0)
    pending_verdict_boost = Column(Boolean, default=False)
    pending_force_correct = Column(Boolean, default=False)
    powerup_window_start = Column(DateTime(timezone=True), nullable=True)
    powerup_uses_this_window = Column(Integer, default=0)

    # Which experience surface this learner is currently associated with --
    # see models/enums.py's LearningMode docstring for the full boundary.
    # Never an authorization check; RBAC/tenant remain the only access axes.
    preferred_mode = Column(
        String, nullable=False, default=DEFAULT_LEARNING_MODE, server_default=DEFAULT_LEARNING_MODE
    )

    # Relationships
    guild = relationship("Guild", back_populates="members")
    accuracy_histories = relationship("AccuracyHistory", back_populates="player")
    submissions = relationship("AnswerSubmission", back_populates="player")
    sessions = relationship("GameSession", back_populates="player")
