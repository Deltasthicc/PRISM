"""
AccuracyHistory SQLAlchemy model — tracks per-player, per-topic performance.
"""
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, String, Integer, Float, DateTime, UniqueConstraint, JSON, ForeignKey
from sqlalchemy.orm import relationship
from db.database import Base


class AccuracyHistory(Base):
    __tablename__ = "accuracy_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)
    topic = Column(String, nullable=False)
    attempts = Column(Integer, default=0)
    correct = Column(Integer, default=0)
    recent_accuracy = Column(Float, default=0.0)
    last_5_results = Column(JSON, default=list)
    # One-way ratchet: True forever once recent_accuracy has ever crossed the
    # unlock threshold. Room-unlock checks must never regress a topic a
    # player has already proven, or a bad run on an unrelated later question
    # (last_5_results is a rolling window) would re-lock rooms they already
    # legitimately opened -- see _is_room_unlocked_for_player in routes/game.py.
    mastered = Column(Boolean, default=False)
    # Cumulative damage dealt to this topic's boss across every submission
    # ever made for it -- the single running total both the in-fight HP bar
    # (hits_required/hits_landed) and the room-clear/unlock-proof checks read
    # from, so they can never disagree about whether the boss is dead.
    damage_dealt = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("player_id", "topic", name="uq_player_topic"),
    )

    # Relationship
    player = relationship("Player", back_populates="accuracy_histories")
