"""Internal result shapes for subject-data inventory, export and deletion."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class SubjectDataExport(BaseModel):
    schema_version: Literal["subject-data-export-v1"] = "subject-data-export-v1"
    generated_at: datetime
    tenant_scope: Literal["deployment-database"] = "deployment-database"
    player_id: str
    records: dict[str, list[dict[str, Any]]]
    record_counts: dict[str, int]
    retention_classification: dict[str, str]
    audit_event_id: str


class SubjectDeletionResult(BaseModel):
    player_id: str
    deleted_counts: dict[str, int]
    guild_assignments_scrubbed: int = Field(ge=0)
    retained_audit_event_count: int = Field(ge=1)
    audit_event_id: str

