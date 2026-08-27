"""
Guild SQLAlchemy model.
"""
import uuid
from sqlalchemy import Column, String, Boolean, Integer, JSON
from sqlalchemy.orm import relationship
from db.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class Guild(Base):
    __tablename__ = "guilds"

    guild_id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, unique=True, nullable=False)
    raid_boss_id = Column(String, nullable=True)
    raid_active = Column(Boolean, default=False)
    raid_boss_hp = Column(Integer, default=0)          # total HP for raid boss
    raid_boss_damage = Column(Integer, default=0)      # cumulative damage dealt
    raid_topic_assignments = Column(JSON, default=dict)   # {player_id: topic}

    # Relationships
    members = relationship("Player", back_populates="guild")
