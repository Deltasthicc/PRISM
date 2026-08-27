"""
Player Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class PlayerCreate(BaseModel):
    username: str


class PlayerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: str
    username: str
    level: int
    total_xp: int
    streak_days: int
    last_active: Optional[datetime] = None
    guild_id: Optional[str] = None
    hint_tokens: int


class PlayerStatsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: str
    username: str
    level: int
    total_xp: int
    streak_days: int
    hint_tokens: int
