"""
Answer submission Pydantic schemas.
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict


class AnswerSubmitRequest(BaseModel):
    player_id: str
    question_id: str
    player_answer: str
    response_time_ms: int = 0


class AnswerSubmitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    submission_id: str
    score: float
    damage_multiplier: float
    verdict: str  # correct | partial | incorrect
    feedback: Optional[str] = None
    xp_gained: int
    damage_dealt: int
    room_cleared: bool = False
    new_level: Optional[int] = None
    dungeon_completed: bool = False
    hits_required: Optional[int] = None
    hits_landed: Optional[int] = None
