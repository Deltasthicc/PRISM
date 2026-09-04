"""Internal subject-data inventory, export and verified deletion primitives.

These functions are deliberately not HTTP endpoints and do not authenticate
their string ``actor`` argument. Lane 2 supplies OIDC verification, binding
and RBAC primitives, but a route must not expose these operations until Lane 5
composes those checks and passes a server-derived actor. Every completed
export/deletion writes an append-only audit event.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

from models.accuracy_history import AccuracyHistory
from models.dungeon import Dungeon
from models.governance import AuditEvent, EvidenceRecord, SourceVersion
from models.guild import Guild
from models.identity import IdentityBinding
from models.learning import (
    CompetencyAssessment,
    GeneratedQuiz,
    LearnerProfile,
    LearningMaterial,
)
from models.player import Player
from models.question import Question
from models.session import GameSession
from models.submission import AnswerSubmission
from schemas.data_rights import SubjectDataExport, SubjectDeletionResult
from security.audit import record_audit_event


_REGISTERED_RELATIONSHIP_MODELS = (Dungeon, Question)
EXPORT_SCHEMA_VERSION = "subject-data-export-v2"

RETENTION_CLASSIFICATION = {
    "players": "delete_with_verified_subject_request",
    "learner_profiles": "delete_with_verified_subject_request",
    "competency_assessments": "delete_with_verified_subject_request",
    "evidence_records": "delete_with_verified_subject_request",
    "accuracy_history": "delete_with_verified_subject_request",
    "game_sessions": "delete_with_verified_subject_request",
    "submissions": "delete_with_verified_subject_request",
    "learning_materials": "delete_with_verified_subject_request",
    "generated_quizzes": "delete_with_verified_subject_request",
    "source_versions": "delete_with_verified_subject_request",
    "identity_bindings": "delete_with_verified_subject_request",
    "guild_topic_assignments": "scrub_with_verified_subject_request",
    "audit_events": "retain_append_only_security_log_duration_policy_pending",
}


class SubjectDataRightsError(ValueError):
    """Base error for rejected subject-data operations."""


class SubjectNotFoundError(SubjectDataRightsError):
    """Raised when the requested player record does not exist."""


class DeletionConfirmationError(SubjectDataRightsError):
    """Raised when explicit destructive confirmation does not match."""


class SubjectDataIntegrityError(SubjectDataRightsError):
    """Raised rather than deleting records that appear foreign-owned."""


class SubjectExportSessionError(SubjectDataRightsError):
    """Raised when export_subject_data() cannot establish a point-in-time
    snapshot because the caller's session already has a transaction open."""


def _required_text(value: str, field: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise SubjectDataRightsError(f"{field} is required")
    if len(normalized) > maximum:
        raise SubjectDataRightsError(f"{field} exceeds {maximum} characters")
    return normalized


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _serialize_row(row: Any) -> dict[str, Any]:
    return {
        column.name: _json_value(getattr(row, column.name))
        for column in row.__table__.columns
    }


def _ordered_rows(db: Session, model: Any, criterion: Any) -> list[Any]:
    primary_key = tuple(model.__table__.primary_key.columns)
    return db.query(model).filter(criterion).order_by(*primary_key).all()


def _subject_records(db: Session, player: Player) -> dict[str, list[dict[str, Any]]]:
    player_id = player.player_id
    materials = _ordered_rows(
        db, LearningMaterial, LearningMaterial.player_id == player_id
    )
    material_ids = [material.material_id for material in materials]

    source_versions = (
        db.query(SourceVersion)
        .filter(SourceVersion.material_id.in_(material_ids))
        .order_by(SourceVersion.source_version_id)
        .all()
        if material_ids
        else []
    )
    guild_assignments = [
        {"guild_id": guild.guild_id, "topic": guild.raid_topic_assignments[player_id]}
        for guild in db.query(Guild).order_by(Guild.guild_id).all()
        if player_id in (guild.raid_topic_assignments or {})
    ]

    return {
        "players": [_serialize_row(player)],
        "learner_profiles": [
            _serialize_row(row)
            for row in _ordered_rows(
                db, LearnerProfile, LearnerProfile.player_id == player_id
            )
        ],
        "competency_assessments": [
            _serialize_row(row)
            for row in _ordered_rows(
                db,
                CompetencyAssessment,
                CompetencyAssessment.player_id == player_id,
            )
        ],
        "evidence_records": [
            _serialize_row(row)
            for row in _ordered_rows(
                db, EvidenceRecord, EvidenceRecord.player_id == player_id
            )
        ],
        "accuracy_history": [
            _serialize_row(row)
            for row in _ordered_rows(
                db, AccuracyHistory, AccuracyHistory.player_id == player_id
            )
        ],
        "game_sessions": [
            _serialize_row(row)
            for row in _ordered_rows(db, GameSession, GameSession.player_id == player_id)
        ],
        "submissions": [
            _serialize_row(row)
            for row in _ordered_rows(
                db, AnswerSubmission, AnswerSubmission.player_id == player_id
            )
        ],
        "learning_materials": [_serialize_row(row) for row in materials],
        "generated_quizzes": [
            _serialize_row(row)
            for row in _ordered_rows(
                db, GeneratedQuiz, GeneratedQuiz.player_id == player_id
            )
        ],
        "source_versions": [_serialize_row(row) for row in source_versions],
        "identity_bindings": [
            _serialize_row(row)
            for row in _ordered_rows(
                db, IdentityBinding, IdentityBinding.player_id == player_id
            )
        ],
        "guild_topic_assignments": guild_assignments,
    }


def export_subject_data(
    db: Session,
    player_id: str,
    *,
    actor: str,
    reason: str,
) -> SubjectDataExport:
    """Return one point-in-time export, then durably audit that it happened.

    This is two transactions, not one snapshot-then-write in a single
    transaction -- deliberately. Extending a snapshot transaction into a
    write is exactly what SQLite's WAL mode (and PostgreSQL's REPEATABLE
    READ) correctly refuse once any unrelated commit has landed since the
    snapshot began ("database is locked" / `could not serialize access`, a
    real conflict-detection mechanism, confirmed directly by first writing
    the single-transaction version and watching a concurrent-write test
    fail on it before splitting this in two). The audit write doesn't need
    the export's snapshot -- it only needs to durably record that the
    export happened, at the current moment, not the snapshot moment -- so
    it runs in its own fresh transaction after the snapshot's read-only
    phase commits (releasing the snapshot; there is nothing to lose, since
    nothing was written yet).

    Every read in the first phase shares one consistent snapshot of the
    database, not a per-statement one. `db.query(...)` here issues one
    SELECT per table; under PostgreSQL's default READ COMMITTED isolation,
    each of those statements sees the database as of *its own* start, not
    as of when this function began -- a row a concurrent transaction
    commits between two of these SELECTs would appear in some of this
    export's tables but not others, silently producing an internally
    inconsistent "point in time" that never actually existed. Switching
    this session's connection to REPEATABLE READ before the first statement
    fixes that: every read for the rest of that transaction sees the same
    snapshot PostgreSQL took at the first one.

    SQLite has the same underlying problem for a different reason, and
    needs its own fix, not "none" -- confirmed by writing the naive version
    first and watching it fail a concurrent-write test before adding this.
    SQLAlchemy's pysqlite dialect runs on the DBAPI's *legacy* transaction
    control (`isolation_level=None`), under which pysqlite only auto-opens a
    transaction before a write, never before a plain SELECT. Without an
    explicit `BEGIN`, every SELECT below would run outside any real
    transaction and see the latest committed state independently -- the
    same class of bug as PostgreSQL's READ COMMITTED default, just from a
    different mechanism, and `test_core_data_rights.py`'s existing SQLite
    tests never exercised concurrent writers so never caught it. An
    explicit `BEGIN` as the first statement (the same technique, for a
    different purpose, `security/identity_bootstrap.py`'s `BEGIN IMMEDIATE`
    already uses) makes pysqlite actually open a transaction, after which
    this project's WAL journal mode gives that connection a stable read
    snapshot for the rest of it, immune to concurrent commits, until this
    function's own `db.commit()`/`db.rollback()` ends it. Plain `BEGIN`
    (deferred), not `BEGIN IMMEDIATE` -- this is a read-only snapshot, not a
    write lock, and does not need to block a concurrent writer the way
    `identity_bootstrap.py`'s bootstrap serialization does.

    Either way, the isolation level or transaction must be established
    before any statement has run in the current transaction, so the caller
    must supply a session with none already open -- the same requirement,
    for the same reason, `security/identity_bootstrap.py`'s bootstrap flow
    already enforces on its own session argument.

    This does not change `delete_subject_data()`'s isolation level: that
    function's own inline comment already explains why it deliberately
    wants each DELETE to see the latest committed data as it runs (so a
    row inserted mid-deletion still gets caught by the matching DELETE's
    own `WHERE player_id = ...`), which is exactly what READ COMMITTED
    already gives it. Snapshot consistency and deletion-completeness are
    different, sometimes opposite, goals; this package only changes export.
    """
    if db.in_transaction():
        raise SubjectExportSessionError(
            "export_subject_data requires a fresh database session with no "
            "transaction already in progress, so the snapshot isolation level "
            "can be set before the first statement runs"
        )
    dialect = db.get_bind().dialect.name
    if dialect == "postgresql":
        db.connection(execution_options={"isolation_level": "REPEATABLE READ"})
    elif dialect == "sqlite":
        db.execute(text("BEGIN"))

    actor = _required_text(actor, "actor", 200)
    reason = _required_text(reason, "reason", 500)
    player = db.query(Player).filter(Player.player_id == player_id).first()
    if player is None:
        db.rollback()  # release the snapshot transaction; nothing was written
        raise SubjectNotFoundError(f"Player not found: {player_id}")

    records = _subject_records(db, player)
    record_counts = {name: len(rows) for name, rows in records.items()}
    related_audit_events = (
        db.query(AuditEvent)
        .filter(
            or_(
                AuditEvent.actor == player_id,
                and_(
                    AuditEvent.entity_type == "player",
                    AuditEvent.entity_id == player_id,
                ),
            )
        )
        .order_by(AuditEvent.created_at, AuditEvent.audit_id)
        .all()
    )
    record_counts["audit_events"] = len(related_audit_events) + 1

    # The snapshot's job ends here -- everything above this line is a pure
    # read. Committing now (nothing to lose: no write has happened yet)
    # releases the snapshot transaction before the audit-event write below,
    # deliberately *not* extending it into a write. A write appended to the
    # same transaction as a long-held snapshot is exactly what SQLite's WAL
    # mode (and PostgreSQL's REPEATABLE READ) correctly refuse once any
    # unrelated commit has landed since the snapshot began -- "database is
    # locked" / `could not serialize access`, a real conflict-detection
    # mechanism working as intended, not a bug to route around. The audit
    # write doesn't need the export's snapshot; it only needs to durably
    # record that the export happened, at the current, not the snapshot,
    # moment.
    db.commit()

    try:
        event = record_audit_event(
            db,
            actor=actor,
            action="subject_data.export",
            entity_type="player",
            entity_id=player_id,
            details={
                "reason": reason,
                "schema_version": EXPORT_SCHEMA_VERSION,
                "record_counts": dict(record_counts),
            },
            commit=False,
        )
        records["audit_events"] = [
            _serialize_row(audit_event) for audit_event in [*related_audit_events, event]
        ]
        result = SubjectDataExport(
            generated_at=datetime.now(timezone.utc),
            player_id=player_id,
            records=records,
            record_counts=record_counts,
            retention_classification=dict(RETENTION_CLASSIFICATION),
            audit_event_id=event.audit_id,
        )
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def delete_subject_data(
    db: Session,
    player_id: str,
    *,
    actor: str,
    reason: str,
    confirmation: str,
) -> SubjectDeletionResult:
    """Delete one subject's owned rows transactionally after exact confirmation."""
    actor = _required_text(actor, "actor", 200)
    reason = _required_text(reason, "reason", 500)
    if confirmation != player_id:
        raise DeletionConfirmationError("confirmation must exactly match player_id")

    player = db.query(Player).filter(Player.player_id == player_id).first()
    if player is None:
        raise SubjectNotFoundError(f"Player not found: {player_id}")

    try:
        material_ids = [
            material_id
            for (material_id,) in db.query(LearningMaterial.material_id)
            .filter(LearningMaterial.player_id == player_id)
            .all()
        ]
        if material_ids:
            foreign_quiz = (
                db.query(GeneratedQuiz.quiz_id)
                .filter(
                    GeneratedQuiz.material_id.in_(material_ids),
                    GeneratedQuiz.player_id != player_id,
                )
                .first()
            )
            if foreign_quiz is not None:
                raise SubjectDataIntegrityError(
                    "Refusing deletion: another player's quiz references subject material"
                )

        guild_assignments_scrubbed = 0
        for guild in db.query(Guild).all():
            assignments = dict(guild.raid_topic_assignments or {})
            if player_id in assignments:
                assignments.pop(player_id)
                guild.raid_topic_assignments = assignments
                guild_assignments_scrubbed += 1

        # `deleted_counts` is built from each DELETE statement's own
        # returned rowcount, not a pre-delete snapshot -- a snapshot taken
        # before these statements run can go stale if a concurrent write
        # (e.g. the subject's own in-flight game activity) inserts a new
        # row for this player in between. Every DELETE below still filters
        # by player_id, so the row would be removed correctly either way;
        # only the *reported* count would have been wrong under a snapshot.
        deleted_counts: dict[str, int] = {
            "generated_quizzes": db.query(GeneratedQuiz)
            .filter(GeneratedQuiz.player_id == player_id)
            .delete(synchronize_session=False),
            "source_versions": (
                db.query(SourceVersion)
                .filter(SourceVersion.material_id.in_(material_ids))
                .delete(synchronize_session=False)
                if material_ids
                else 0
            ),
            "learning_materials": db.query(LearningMaterial)
            .filter(LearningMaterial.player_id == player_id)
            .delete(synchronize_session=False),
            "submissions": db.query(AnswerSubmission)
            .filter(AnswerSubmission.player_id == player_id)
            .delete(synchronize_session=False),
            "accuracy_history": db.query(AccuracyHistory)
            .filter(AccuracyHistory.player_id == player_id)
            .delete(synchronize_session=False),
            "competency_assessments": db.query(CompetencyAssessment)
            .filter(CompetencyAssessment.player_id == player_id)
            .delete(synchronize_session=False),
            "evidence_records": db.query(EvidenceRecord)
            .filter(EvidenceRecord.player_id == player_id)
            .delete(synchronize_session=False),
            "game_sessions": db.query(GameSession)
            .filter(GameSession.player_id == player_id)
            .delete(synchronize_session=False),
            "learner_profiles": db.query(LearnerProfile)
            .filter(LearnerProfile.player_id == player_id)
            .delete(synchronize_session=False),
            "identity_bindings": db.query(IdentityBinding)
            .filter(IdentityBinding.player_id == player_id)
            .delete(synchronize_session=False),
            "players": db.query(Player)
            .filter(Player.player_id == player_id)
            .delete(synchronize_session=False),
        }

        event = record_audit_event(
            db,
            actor=actor,
            action="subject_data.delete",
            entity_type="player",
            entity_id=player_id,
            details={
                "reason": reason,
                "deleted_counts": deleted_counts,
                "guild_assignments_scrubbed": guild_assignments_scrubbed,
                "audit_events_retained": True,
            },
            commit=False,
        )
        retained_audit_event_count = (
            db.query(AuditEvent)
            .filter(
                or_(
                    AuditEvent.actor == player_id,
                    and_(
                        AuditEvent.entity_type == "player",
                        AuditEvent.entity_id == player_id,
                    ),
                )
            )
            .count()
        )
        result = SubjectDeletionResult(
            player_id=player_id,
            deleted_counts=deleted_counts,
            guild_assignments_scrubbed=guild_assignments_scrubbed,
            retained_audit_event_count=retained_audit_event_count,
            audit_event_id=event.audit_id,
        )
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
