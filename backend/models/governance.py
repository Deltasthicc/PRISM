"""
Versioned role-target, evidence, source-version and audit records -- Lane 2's
"minimal versioned records" deliverable (SIH26101_TEAM_ORCHESTRATION.md
section 5, Lane 2 immediate package; docs/contracts/data-authorization.md).

These are additive, brand-new tables. On the SQLite demo profile, plain
Base.metadata.create_all() in main.py's lifespan is still enough -- no
ensure_columns() patching needed, same as models/learning.py. On PostgreSQL,
main.py no longer calls create_all() at all: db/database.py's
require_database_at_migration_head() refuses startup unless the database is
already at the Alembic head revision, and these four tables are schema-owned
by migrations/versions/2baf7d4bd8a2_add_governance_tables.py (which safely
adopts a pre-existing, schema-compatible copy of them rather than colliding
with one create_all() already made -- see that file's
_adopt_compatible_preexisting_tables()).

Why these exist as separate tables instead of extending LearnerProfile /
CompetencyAssessment in place:

- RoleTarget lets a target level for a competency be versioned and dated
  (valid_from/valid_to) independently of any one learner's assessment, so
  Lane 3 can stop hardcoding EXPERIENCE_TARGET_CAP and instead look up a
  named, sourced target -- see CODEX.md "Architecture invariants": targets
  must become versioned/auditable rather than silently mutable.
- EvidenceRecord keeps each individual piece of evidence (a self-rating, one
  diagnostic result, one reviewer note) as its own immutable row, instead of
  collapsing everything into CompetencyAssessment.self_ratings /
  measured_scores. SIH26101_MASTER_CHECKLIST.md section 4.1 explicitly calls
  for separating self-report, diagnostic, observed-practice, reviewer and
  provider evidence -- this table is what makes that separation queryable
  rather than just a comment.
- SourceVersion is the versioned-source primitive the data-authorization
  contract promises Lane 4's content pipeline; it references LearningMaterial
  by id but stays a distinct table because a future non-file source (e.g. a
  live provider catalogue entry) may need a source-version row without ever
  having a LearningMaterial row.
- AuditEvent is deliberately append-only in the sense that matters: there is
  no UPDATE path anywhere in this module or any route, and PostgreSQL
  additionally rejects UPDATE at the database level (Package V). DELETE is
  intentionally still possible -- `scripts/retention_job.py` is the one
  sanctioned caller, and only once a real, cited maximum retention exists
  for a category (none do yet). Do not describe this table as unconditionally
  immune to deletion; "append-only" here means "never mutated," not "never
  pruned under a lawful, auditable retention policy."
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String
from db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


# Evidence types Lane 3's gap engine may eventually blend or keep separate --
# kept here (not in learning_engine.py) because this is the storage-level
# vocabulary; SIH26101_MASTER_CHECKLIST.md 4.1 owns the *policy* for how
# these get weighted, this module only owns what gets recorded.
EVIDENCE_TYPES = ("self_report", "diagnostic", "observed_practice", "reviewer", "provider_imported")


class RoleTarget(Base):
    """A versioned target_level for one competency under one named role.

    `role` is a free-text key today (a designation or job_role string, or
    "*" for a role-agnostic default) -- there is no Role table yet because no
    approved role catalogue exists (docs/SIH26101_PROBLEM_STATEMENT.md,
    "Known unknowns"). Do not treat `source="internal-prototype"` as
    equivalent to `source="mospi-cbc-approved"`; nothing in this model
    enforces that distinction, the caller must set it honestly.
    """

    __tablename__ = "role_targets"

    target_id = Column(String, primary_key=True, default=generate_uuid)
    framework_version = Column(String, nullable=False, default="prototype-v1")
    role = Column(String, nullable=False, index=True)
    competency_id = Column(String, nullable=False, index=True)
    target_level = Column(Integer, nullable=False)  # 1-5, enforced by schemas.governance.RoleTargetCreate
    source = Column(String, nullable=False, default="internal-prototype")
    approved_by = Column(String, nullable=True)  # null until an authorized reviewer signs off

    valid_from = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    valid_to = Column(DateTime(timezone=True), nullable=True)  # null = currently in effect

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class EvidenceRecord(Base):
    """One immutable observation of a learner's level on one competency.

    Never updated after insert -- a correction is a new row, not an edit, so
    the evidence history stays auditable. `value` is nullable because
    evidence_type="reviewer" may carry only a qualitative note in `detail`
    with no numeric rating.
    """

    __tablename__ = "evidence_records"

    evidence_id = Column(String, primary_key=True, default=generate_uuid)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)
    competency_id = Column(String, nullable=False, index=True)
    evidence_type = Column(String, nullable=False)  # one of EVIDENCE_TYPES
    value = Column(Integer, nullable=True)  # 0-5, enforced by schemas.governance.EvidenceRecordCreate
    detail = Column(String, default="")  # e.g. a quiz_id, session_id, or reviewer note
    recorded_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class SourceVersion(Base):
    """An immutable, versioned pointer to one revision of a content source.

    material_id is nullable so a future non-upload source (e.g. a catalogued
    provider course description) can still get a source-version row without
    a LearningMaterial row existing for it.
    """

    __tablename__ = "source_versions"

    source_version_id = Column(String, primary_key=True, default=generate_uuid)
    material_id = Column(String, ForeignKey("learning_materials.material_id"), nullable=True, index=True)
    version_number = Column(Integer, nullable=False, default=1)
    sha256 = Column(String, nullable=False, index=True)
    locator = Column(String, default="")  # e.g. "page 3" / "section 2.1" -- empty until Lane 4 chunks it
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AuditEvent(Base):
    """Append-only log of privileged reads/writes, role changes, content
    approval and exports (SIH26101_TEAM_ORCHESTRATION.md section 5, Lane 2
    acceptance evidence). Write with security.audit.record_audit_event() --
    do not construct/add this model directly from route code, so every write
    path stays consistent."""

    __tablename__ = "audit_events"

    audit_id = Column(String, primary_key=True, default=generate_uuid)
    actor = Column(String, nullable=False)  # a player_id, or "system" for non-human actions
    action = Column(String, nullable=False)  # e.g. "role_target.approve", "profile.update"
    entity_type = Column(String, nullable=False)  # e.g. "role_target", "learner_profile"
    entity_id = Column(String, nullable=True)
    details = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
