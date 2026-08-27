"""
Player SQLAlchemy model.
"""
import os
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Float, String, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.sqlite import TEXT
from sqlalchemy.orm import relationship
from db.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class Player(Base):
    __tablename__ = "players"

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

    # Relationships
    guild = relationship("Guild", back_populates="members")
    accuracy_histories = relationship("AccuracyHistory", back_populates="player")
    submissions = relationship("AnswerSubmission", back_populates="player")
    sessions = relationship("GameSession", back_populates="player")
