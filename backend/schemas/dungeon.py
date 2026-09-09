"""
Dungeon and session Pydantic schemas.
"""
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    room_id: str
    topic: str
    enemy_count: int
    is_boss: bool
    is_unlocked: bool
    order_index: int
    # Populated only when GET /game/dungeon/{id} is called with a `player_id`
    # -- real per-player status (see game.py::_annotate_rooms_for_player),
    # generalized from the old DSA-only client-side heuristic in
    # frontend/lib/api/client.js to every seeded curriculum.
    unlocked_for_player: Optional[bool] = None
    recent_accuracy: Optional[float] = None
    completion: Optional[float] = None
    status: Optional[str] = None  # "locked" | "unlocked" | "weak" | "mastered"


class DungeonResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    dungeon_id: str
    name: str
    domain: str
    curriculum_slug: Optional[str] = None
    rooms: List[RoomResponse] = Field(default_factory=list)
    boss_unlocked: Optional[bool] = None
    next_topic: Optional[str] = None


class SessionStartRequest(BaseModel):
    player_id: str
    dungeon_id: str


class SessionStartResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    session_id: str
    dungeon: DungeonResponse
    current_room_id: Optional[str] = None


class RoomEnterRequest(BaseModel):
    session_id: str
    room_id: str


class RoomEnterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    room: RoomResponse
    question: dict  # question_id, question, hint, topic, difficulty
    enemy_hp: int
    # Hits-based combat truth: the villain's HP bar is driven by these, not by
    # enemy_hp, so it always empties in exact sync with the real room-clear
    # condition (correct_count >= hits_required) instead of an arbitrary flat
    # HP pool that can disagree with when the room actually clears.
    hits_required: int
    hits_landed: int
