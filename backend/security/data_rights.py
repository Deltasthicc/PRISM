"""Internal subject-data inventory, export and verified deletion primitives.

These functions are deliberately not HTTP endpoints. The repository has no
authenticated subject or RBAC enforcement yet, so a route must not expose
them until Lane 5 consumes the authorization contract and Lane 2 supplies a
server-derived actor. Callers are responsible for verifying authority before
invocation; every completed export/deletion writes an append-only audit event.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from models.accuracy_history import AccuracyHistory
from models.dungeon import Dungeon
from models.governance import AuditEvent, EvidenceRecord, SourceVersion
from models.guild import Guild
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
EXPORT_SCHEMA_VERSION = "subject-data-export-v1"

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
        "guild_topic_assignments": guild_assignments,
    }


def export_subject_data(
    db: Session,
    player_id: str,
    *,
    actor: str,
    reason: str,
) -> SubjectDataExport:
    """Return one deterministic export and audit it in the same DB session."""
    actor = _required_text(actor, "actor", 200)
    reason = _required_text(reason, "reason", 500)
    player = db.query(Player).filter(Player.player_id == player_id).first()
    if player is None:
        raise SubjectNotFoundError(f"Player not found: {player_id}")

    try:
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

        records = _subject_records(db, player)
        deleted_counts = {
            name: len(rows)
            for name, rows in records.items()
            if name != "guild_topic_assignments"
        }
        guild_assignments_scrubbed = 0
        for guild in db.query(Guild).all():
            assignments = dict(guild.raid_topic_assignments or {})
            if player_id in assignments:
                assignments.pop(player_id)
                guild.raid_topic_assignments = assignments
                guild_assignments_scrubbed += 1

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

        db.query(GeneratedQuiz).filter(
            GeneratedQuiz.player_id == player_id
        ).delete(synchronize_session=False)
        if material_ids:
            db.query(SourceVersion).filter(
                SourceVersion.material_id.in_(material_ids)
            ).delete(synchronize_session=False)
        db.query(LearningMaterial).filter(
            LearningMaterial.player_id == player_id
        ).delete(synchronize_session=False)
        db.query(AnswerSubmission).filter(
            AnswerSubmission.player_id == player_id
        ).delete(synchronize_session=False)
        db.query(AccuracyHistory).filter(
            AccuracyHistory.player_id == player_id
        ).delete(synchronize_session=False)
        db.query(CompetencyAssessment).filter(
            CompetencyAssessment.player_id == player_id
        ).delete(synchronize_session=False)
        db.query(EvidenceRecord).filter(
            EvidenceRecord.player_id == player_id
        ).delete(synchronize_session=False)
        db.query(GameSession).filter(GameSession.player_id == player_id).delete(
            synchronize_session=False
        )
        db.query(LearnerProfile).filter(
            LearnerProfile.player_id == player_id
        ).delete(synchronize_session=False)
        db.query(Player).filter(Player.player_id == player_id).delete(
            synchronize_session=False
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
