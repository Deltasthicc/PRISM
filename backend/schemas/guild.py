"""
Guild Pydantic schemas.
"""
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class GuildCreate(BaseModel):
    name: str
    creator_player_id: str


class GuildResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    guild_id: str
    name: str
    members: List[dict] = Field(default_factory=list)
    raid_active: bool
    raid_boss_id: Optional[str] = None


class RaidJoinRequest(BaseModel):
    guild_id: str
    player_id: str


class GuildJoinRequest(BaseModel):
    guild_id: str
    player_id: str
