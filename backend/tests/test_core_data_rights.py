"""Lane 2 tests for internal subject export/deletion/retention primitives."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from db.database import Base
from models.accuracy_history import AccuracyHistory
from models.dungeon import Dungeon
from models.governance import AuditEvent, EvidenceRecord, RoleTarget, SourceVersion
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
from security.audit import record_audit_event
from security.data_rights import (
    DeletionConfirmationError,
    RETENTION_CLASSIFICATION,
    SubjectDataIntegrityError,
    SubjectDataRightsError,
    SubjectNotFoundError,
    delete_subject_data,
    export_subject_data,
)


TARGET_PLAYER_ID = "player-target"
OTHER_PLAYER_ID = "player-other"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def subject_graph(db):
    guild = Guild(
        guild_id="guild-1",
        name="Synthetic Guild",
        raid_topic_assignments={
            TARGET_PLAYER_ID: "sampling",
            OTHER_PLAYER_ID: "metadata",
        },
    )
    dungeon = Dungeon(
        dungeon_id="dungeon-1",
        name="Synthetic Dungeon",
        domain="Synthetic",
    )
    question = Question(
        question_id="question-1",
        topic="sampling",
        difficulty="easy",
        question_text="Synthetic question?",
        expected_answer="Synthetic answer",
    )
    target = Player(
        player_id=TARGET_PLAYER_ID,
        username="target-user",
        guild_id=guild.guild_id,
    )
    other = Player(
        player_id=OTHER_PLAYER_ID,
        username="other-user",
        guild_id=guild.guild_id,
    )
    material = LearningMaterial(
        material_id="material-target",
        player_id=TARGET_PLAYER_ID,
        filename="synthetic.txt",
        sha256="a" * 64,
        text_excerpt="Synthetic excerpt",
    )
    # Commit each dependency layer explicitly. These fixtures intentionally use
    # scalar foreign-key values (rather than ORM relationship attributes), so
    # SQLAlchemy cannot infer an insertion dependency from one add_all() call.
    db.add_all([guild, dungeon, question])
    db.commit()
    db.add_all([target, other])
    db.commit()
    db.add(material)
    db.commit()
    db.add_all(
        [
            LearnerProfile(
                profile_id="profile-target",
                player_id=TARGET_PLAYER_ID,
                designation="Synthetic Officer",
            ),
            CompetencyAssessment(
                assessment_id="assessment-target",
                player_id=TARGET_PLAYER_ID,
                curriculum_slug="official-statistics",
                self_ratings={"sampling": 2},
            ),
            EvidenceRecord(
                evidence_id="evidence-target",
                player_id=TARGET_PLAYER_ID,
                competency_id="sampling",
                evidence_type="diagnostic",
                value=2,
            ),
            IdentityBinding(
                binding_id="identity-target",
                issuer="https://identity.example.test/realms/sih",
                subject_id="external-target-subject",
                player_id=TARGET_PLAYER_ID,
            ),
            AccuracyHistory(
                player_id=TARGET_PLAYER_ID,
                topic="sampling",
                attempts=1,
                correct=1,
            ),
            AccuracyHistory(
                player_id=OTHER_PLAYER_ID,
                topic="metadata",
                attempts=1,
                correct=1,
            ),
            GameSession(
                session_id="session-target",
                player_id=TARGET_PLAYER_ID,
                dungeon_id=dungeon.dungeon_id,
            ),
            AnswerSubmission(
                submission_id="submission-target",
                player_id=TARGET_PLAYER_ID,
                question_id=question.question_id,
                player_answer="Synthetic answer",
                verdict="correct",
            ),
            GeneratedQuiz(
                quiz_id="quiz-target",
                material_id=material.material_id,
                player_id=TARGET_PLAYER_ID,
                title="Synthetic Quiz",
            ),
            SourceVersion(
                source_version_id="source-target",
                material_id=material.material_id,
                version_number=1,
                sha256=material.sha256,
            ),
            RoleTarget(
                target_id="role-target-global",
                role="synthetic-role",
                competency_id="sampling",
                target_level=3,
            ),
            AuditEvent(
                audit_id="audit-existing",
                actor=TARGET_PLAYER_ID,
                action="profile.update",
                entity_type="player",
                entity_id=TARGET_PLAYER_ID,
                details={"synthetic": True},
            ),
        ]
    )
    db.commit()
    return {"guild": guild, "dungeon": dungeon, "question": question}


def test_export_is_complete_deterministic_json_and_audited(db, subject_graph):
    exported = export_subject_data(
        db,
        TARGET_PLAYER_ID,
        actor="privacy-officer",
        reason="verified synthetic request",
    )

    assert exported.player_id == TARGET_PLAYER_ID
    assert exported.schema_version == "subject-data-export-v2"
    assert exported.tenant_scope == "deployment-database"
    assert exported.record_counts == {
        name: len(records) for name, records in exported.records.items()
    }
    assert exported.record_counts["players"] == 1
    assert exported.record_counts["learner_profiles"] == 1
    assert exported.record_counts["competency_assessments"] == 1
    assert exported.record_counts["evidence_records"] == 1
    assert exported.record_counts["accuracy_history"] == 1
    assert exported.record_counts["game_sessions"] == 1
    assert exported.record_counts["submissions"] == 1
    assert exported.record_counts["learning_materials"] == 1
    assert exported.record_counts["generated_quizzes"] == 1
    assert exported.record_counts["source_versions"] == 1
    assert exported.record_counts["identity_bindings"] == 1
    assert exported.record_counts["guild_topic_assignments"] == 1
    assert exported.record_counts["audit_events"] == 2
    assert exported.records["players"][0]["player_id"] == TARGET_PLAYER_ID
    assert OTHER_PLAYER_ID not in json.dumps(exported.model_dump(mode="json"))

    event_row = db.query(AuditEvent).filter_by(audit_id=exported.audit_event_id).one()
    assert event_row.action == "subject_data.export"
    assert event_row.details["record_counts"] == exported.record_counts
    json.dumps(exported.model_dump(mode="json"))


def test_export_rejects_unknown_subject_without_writing_audit(db, subject_graph):
    before = db.query(AuditEvent).count()
    # export_subject_data() requires a session with no transaction already
    # open (Package 5 -- it sets a snapshot isolation level before its first
    # statement), so the read above must not leave one in progress; matches
    # test_core_identity_bootstrap.py::test_bootstrap_requires_a_fresh_session's
    # own use of rollback() for the identical reason.
    db.rollback()

    with pytest.raises(SubjectNotFoundError):
        export_subject_data(
            db,
            "missing-player",
            actor="privacy-officer",
            reason="verified request",
        )

    assert db.query(AuditEvent).count() == before


@pytest.mark.parametrize(
    ("actor", "reason"),
    [("", "valid reason"), ("privacy-officer", "   ")],
)
def test_export_requires_bounded_actor_and_reason(db, subject_graph, actor, reason):
    with pytest.raises(SubjectDataRightsError):
        export_subject_data(
            db,
            TARGET_PLAYER_ID,
            actor=actor,
            reason=reason,
        )


def test_delete_requires_exact_confirmation_without_mutation(db, subject_graph):
    before = db.query(AuditEvent).count()

    with pytest.raises(DeletionConfirmationError):
        delete_subject_data(
            db,
            TARGET_PLAYER_ID,
            actor="privacy-officer",
            reason="verified request",
            confirmation="wrong-player",
        )

    assert db.query(Player).filter_by(player_id=TARGET_PLAYER_ID).count() == 1
    assert db.query(AuditEvent).count() == before


def test_delete_removes_owned_rows_scrubs_guild_and_retains_audit(db, subject_graph):
    result = delete_subject_data(
        db,
        TARGET_PLAYER_ID,
        actor="privacy-officer",
        reason="verified synthetic deletion",
        confirmation=TARGET_PLAYER_ID,
    )

    assert result.deleted_counts == {
        "players": 1,
        "learner_profiles": 1,
        "competency_assessments": 1,
        "evidence_records": 1,
        "accuracy_history": 1,
        "game_sessions": 1,
        "submissions": 1,
        "learning_materials": 1,
        "generated_quizzes": 1,
        "source_versions": 1,
        "identity_bindings": 1,
    }
    assert result.guild_assignments_scrubbed == 1
    assert result.retained_audit_event_count == 2
    assert db.query(Player).filter_by(player_id=TARGET_PLAYER_ID).count() == 0
    assert db.query(IdentityBinding).filter_by(player_id=TARGET_PLAYER_ID).count() == 0
    assert db.query(Player).filter_by(player_id=OTHER_PLAYER_ID).count() == 1
    assert db.query(AccuracyHistory).filter_by(player_id=OTHER_PLAYER_ID).count() == 1
    assert db.query(Dungeon).count() == 1
    assert db.query(Question).count() == 1
    assert db.query(RoleTarget).count() == 1

    guild = db.query(Guild).filter_by(guild_id="guild-1").one()
    assert guild.raid_topic_assignments == {OTHER_PLAYER_ID: "metadata"}
    deletion_event = db.query(AuditEvent).filter_by(audit_id=result.audit_event_id).one()
    assert deletion_event.action == "subject_data.delete"
    assert deletion_event.details["audit_events_retained"] is True


def test_delete_reports_actual_delete_rowcounts_not_a_stale_snapshot(db, subject_graph):
    # A row for this player appearing after the operation starts (e.g. the
    # subject's own in-flight game activity landing concurrently) must
    # still be correctly counted in deleted_counts -- it must reflect what
    # each DELETE statement actually removed, not a snapshot taken before
    # any DELETE ran.
    from sqlalchemy.sql.dml import Delete

    real_execute = db.execute
    injected = {"done": False}

    def _execute_with_injected_concurrent_row(statement, *args, **kwargs):
        if not injected["done"] and isinstance(statement, Delete):
            injected["done"] = True
            real_execute(
                AccuracyHistory.__table__.insert().values(
                    player_id=TARGET_PLAYER_ID, topic="concurrently-inserted"
                )
            )
        return real_execute(statement, *args, **kwargs)

    db.execute = _execute_with_injected_concurrent_row
    try:
        result = delete_subject_data(
            db,
            TARGET_PLAYER_ID,
            actor="privacy-officer",
            reason="verify race-safe counting",
            confirmation=TARGET_PLAYER_ID,
        )
    finally:
        db.execute = real_execute

    assert injected["done"], "the injection hook never fired -- test setup is broken"
    # The subject_graph fixture already gives this player one accuracy_history
    # row; the injected one makes two, and the broad WHERE player_id
    # predicate deletes both regardless of when either was created.
    assert result.deleted_counts["accuracy_history"] == 2
    assert db.query(AccuracyHistory).filter_by(player_id=TARGET_PLAYER_ID).count() == 0


def test_delete_rejects_cross_owner_material_reference_atomically(db, subject_graph):
    db.add(
        GeneratedQuiz(
            quiz_id="foreign-quiz",
            material_id="material-target",
            player_id=OTHER_PLAYER_ID,
            title="Invalid cross-owner quiz",
        )
    )
    db.commit()
    before_audits = db.query(AuditEvent).count()

    with pytest.raises(SubjectDataIntegrityError):
        delete_subject_data(
            db,
            TARGET_PLAYER_ID,
            actor="privacy-officer",
            reason="verified request",
            confirmation=TARGET_PLAYER_ID,
        )

    assert db.query(Player).filter_by(player_id=TARGET_PLAYER_ID).count() == 1
    assert db.query(LearningMaterial).filter_by(player_id=TARGET_PLAYER_ID).count() == 1
    assert db.query(AuditEvent).count() == before_audits


def test_delete_rolls_back_all_mutations_when_commit_fails(
    db, subject_graph, monkeypatch
):
    before_audits = db.query(AuditEvent).count()
    real_commit = db.commit

    def _fail_commit():
        raise RuntimeError("synthetic commit failure")

    monkeypatch.setattr(db, "commit", _fail_commit)
    with pytest.raises(RuntimeError, match="synthetic commit failure"):
        delete_subject_data(
            db,
            TARGET_PLAYER_ID,
            actor="privacy-officer",
            reason="verified request",
            confirmation=TARGET_PLAYER_ID,
        )

    monkeypatch.setattr(db, "commit", real_commit)
    db.expire_all()
    assert db.query(Player).filter_by(player_id=TARGET_PLAYER_ID).count() == 1
    assert db.query(LearningMaterial).filter_by(player_id=TARGET_PLAYER_ID).count() == 1
    assert db.query(AuditEvent).count() == before_audits
    guild = db.query(Guild).filter_by(guild_id="guild-1").one()
    assert guild.raid_topic_assignments[TARGET_PLAYER_ID] == "sampling"


def test_uncommitted_audit_event_rolls_back_with_parent_operation(db):
    event_row = record_audit_event(
        db,
        actor="privacy-officer",
        action="subject_data.test",
        entity_type="player",
        entity_id=TARGET_PLAYER_ID,
        commit=False,
    )
    assert db.query(AuditEvent).filter_by(audit_id=event_row.audit_id).count() == 1

    db.rollback()

    assert db.query(AuditEvent).filter_by(audit_id=event_row.audit_id).count() == 0


def test_retention_classification_keeps_audit_as_explicit_exception():
    assert set(RETENTION_CLASSIFICATION) == {
        "players",
        "learner_profiles",
        "competency_assessments",
        "evidence_records",
        "accuracy_history",
        "game_sessions",
        "submissions",
        "learning_materials",
        "generated_quizzes",
        "source_versions",
        "identity_bindings",
        "guild_topic_assignments",
        "audit_events",
    }
    assert RETENTION_CLASSIFICATION["audit_events"].startswith("retain_append_only")
