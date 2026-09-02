"""
Player Pydantic schemas for request/response validation.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict

from models.enums import LearningMode


class PlayerCreate(BaseModel):
    username: str
    # preferred_mode is deliberately NOT accepted here yet: routes/game.py's
    # create_player() (Lane 5-owned) does not read it, so a client-supplied
    # value would be silently ignored -- every new player gets the model's
    # own professional/base default (models/enums.py) regardless. Accepting
    # a field the route can't yet honor would be exactly the kind of
    # looks-implemented-but-isn't gap this project explicitly guards
    # against; add it here once Lane 5 wires it through.


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
    preferred_mode: LearningMode


class PlayerStatsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    player_id: str
    username: str
    level: int
    total_xp: int
    streak_days: int
    hint_tokens: int
