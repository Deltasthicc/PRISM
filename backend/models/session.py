"""
GameSession SQLAlchemy model — tracks active dungeon sessions.
"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from db.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class GameSession(Base):
    __tablename__ = "game_sessions"

    session_id = Column(String, primary_key=True, default=generate_uuid)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False)
    dungeon_id = Column(String, ForeignKey("dungeons.dungeon_id"), nullable=False)
    current_room_id = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status = Column(String, default="active")  # active | completed | abandoned

    # Relationships
    player = relationship("Player", back_populates="sessions")
    dungeon = relationship("Dungeon")
