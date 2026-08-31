"""Validated internal shapes for OIDC-to-application identity bindings."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IdentityBindingCreate(BaseModel):
    issuer: str = Field(min_length=1, max_length=500)
    subject_id: str = Field(min_length=1, max_length=500)
    player_id: str | None = Field(default=None, min_length=1, max_length=200)


class IdentityBindingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    binding_id: str
    issuer: str
    subject_id: str
    player_id: str | None
    active: bool
    created_at: datetime
    updated_at: datetime
