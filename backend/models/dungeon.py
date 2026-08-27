"""
Dungeon and Room SQLAlchemy models.
"""
import uuid
from sqlalchemy import Column, String, Integer, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from db.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class Dungeon(Base):
    __tablename__ = "dungeons"

    dungeon_id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    domain = Column(String, nullable=False)
    # Slug of the services/curricula.py entry this dungeon materializes
    # (e.g. "official-statistics"). Nullable for backward compatibility with
    # any dungeon seeded before this field existed.
    curriculum_slug = Column(String, nullable=True, index=True)

    # Relationships
    rooms = relationship("Room", back_populates="dungeon", order_by="Room.order_index")


class Room(Base):
    __tablename__ = "rooms"

    room_id = Column(String, primary_key=True, default=generate_uuid)
    dungeon_id = Column(String, ForeignKey("dungeons.dungeon_id"), nullable=False)
    topic = Column(String, nullable=False)
    enemy_count = Column(Integer, default=3)
    is_boss = Column(Boolean, default=False)
    is_unlocked = Column(Boolean, default=False)
    order_index = Column(Integer, default=0)

    # Relationships
    dungeon = relationship("Dungeon", back_populates="rooms")
