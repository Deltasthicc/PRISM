"""
Pydantic request/response shapes for the versioned governance records in
models/governance.py -- mirrors that file the same way schemas/learning.py
mirrors models/learning.py.

Nothing in routes/ imports these yet; exposing them over HTTP (and deciding
who may write a RoleTarget or read another player's EvidenceRecord) is
tracked as follow-up work, not assumed done here -- see
docs/contracts/data-authorization.md.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from models.governance import EVIDENCE_TYPES


class RoleTargetCreate(BaseModel):
    """Input shape for defining one versioned role/competency target."""

    framework_version: str = Field("prototype-v1", min_length=1, max_length=40)
    role: str = Field(..., min_length=1, max_length=120)
    competency_id: str = Field(..., min_length=1, max_length=120)
    target_level: int = Field(..., ge=1, le=5)
    source: str = Field("internal-prototype", min_length=1, max_length=80)
    approved_by: str | None = None


class RoleTargetResponse(RoleTargetCreate):
    target_id: str
    valid_from: datetime
    valid_to: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EvidenceRecordCreate(BaseModel):
    """Input shape for recording one immutable piece of evidence."""

    player_id: str = Field(..., min_length=1)
    competency_id: str = Field(..., min_length=1, max_length=120)
    evidence_type: str
    value: int | None = Field(None, ge=0, le=5)
    detail: str = Field("", max_length=500)

    @field_validator("evidence_type")
    @classmethod
    def _known_evidence_type(cls, value: str) -> str:
        if value not in EVIDENCE_TYPES:
            raise ValueError(f"evidence_type must be one of {EVIDENCE_TYPES}, got {value!r}")
        return value


class EvidenceRecordResponse(EvidenceRecordCreate):
    evidence_id: str
    recorded_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SourceVersionResponse(BaseModel):
    """Read-only -- SourceVersion rows are created by ingestion code (Lane 4),
    not by a direct API request, so there is no *Create schema here."""

    source_version_id: str
    material_id: str | None
    version_number: int
    sha256: str
    locator: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditEventResponse(BaseModel):
    """Read-only -- AuditEvent rows are only ever created through
    security.audit.record_audit_event(), never through a direct API request."""

    audit_id: str
    actor: str
    action: str
    entity_type: str
    entity_id: str | None
    details: dict
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
