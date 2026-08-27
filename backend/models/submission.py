"""
AnswerSubmission SQLAlchemy model — records every answer a player submits.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from db.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class AnswerSubmission(Base):
    __tablename__ = "submissions"

    submission_id = Column(String, primary_key=True, default=generate_uuid)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False)
    question_id = Column(String, ForeignKey("questions.question_id"), nullable=False)
    player_answer = Column(String, nullable=False)
    score = Column(Float, default=0.0)
    damage_multiplier = Column(Float, default=0.0)
    # Actual damage this submission dealt (question.max_damage * score,
    # zeroed for an "incorrect" verdict) -- persisted so it can be summed
    # per-topic later; the old model only stored verdict/score and computed
    # damage fresh each response, which meant nothing durable recorded how
    # much of a boss's HP pool a past submission had actually taken off.
    damage_dealt = Column(Integer, default=0)
    verdict = Column(String, nullable=False)  # correct | partial | incorrect
    response_time_ms = Column(Integer, default=0)
    submitted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    player = relationship("Player", back_populates="submissions")
    question = relationship("Question")
