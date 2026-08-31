"""
Tests for the Lane 2 versioned governance records (models/governance.py,
schemas/governance.py, security/audit.py) -- SIH26101_TEAM_ORCHESTRATION.md
section 5, Lane 2 immediate package.

Follows the same in-memory-SQLite pattern as
test_learning_platform.py::test_room_unlock_falls_back_to_curricula_for_non_dsa_topics.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base
from models.player import Player
from models.governance import RoleTarget, EvidenceRecord, SourceVersion, AuditEvent
from models.learning import LearningMaterial
from schemas.governance import (
    RoleTargetCreate,
    EvidenceRecordCreate,
    RoleTargetResponse,
    EvidenceRecordResponse,
    SourceVersionResponse,
    AuditEventResponse,
)
from security.audit import record_audit_event


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def player(db):
    p = Player(player_id="p1", username="tester")
    db.add(p)
    db.commit()
    return p


# --- RoleTarget ---


def test_role_target_schema_rejects_out_of_range_level():
    with pytest.raises(ValidationError):
        RoleTargetCreate(role="statistical-officer", competency_id="os_sampling_design", target_level=6)


def test_role_target_round_trips_through_db(db):
    payload = RoleTargetCreate(
        role="statistical-officer",
        competency_id="os_sampling_design",
        target_level=4,
        source="internal-prototype",
    )
    row = RoleTarget(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)

    fetched = db.query(RoleTarget).filter_by(target_id=row.target_id).one()
    response = RoleTargetResponse.model_validate(fetched)
    assert response.target_level == 4
    assert response.approved_by is None
    assert response.valid_to is None  # still in effect


def test_role_target_defaults_to_unapproved_internal_prototype_source():
    payload = RoleTargetCreate(role="*", competency_id="os_data_quality", target_level=3)
    assert payload.source == "internal-prototype"
    assert payload.approved_by is None


# --- EvidenceRecord ---


def test_evidence_record_rejects_unknown_evidence_type():
    with pytest.raises(ValidationError):
        EvidenceRecordCreate(
            player_id="p1", competency_id="os_data_quality", evidence_type="vibes", value=3
        )


@pytest.mark.parametrize(
    "evidence_type", ["self_report", "diagnostic", "observed_practice", "reviewer", "provider_imported"]
)
def test_evidence_record_accepts_every_documented_evidence_type(evidence_type):
    record = EvidenceRecordCreate(
        player_id="p1", competency_id="os_data_quality", evidence_type=evidence_type, value=2
    )
    assert record.evidence_type == evidence_type


def test_evidence_record_value_is_optional_for_qualitative_reviewer_notes():
    record = EvidenceRecordCreate(
        player_id="p1",
        competency_id="os_data_quality",
        evidence_type="reviewer",
        detail="Reviewed manually, needs more practice on GIS.",
    )
    assert record.value is None


def test_evidence_record_round_trips_through_db(db, player):
    payload = EvidenceRecordCreate(
        player_id=player.player_id, competency_id="os_data_quality", evidence_type="diagnostic", value=3
    )
    row = EvidenceRecord(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)

    fetched = db.query(EvidenceRecord).filter_by(evidence_id=row.evidence_id).one()
    response = EvidenceRecordResponse.model_validate(fetched)
    assert response.value == 3
    assert response.evidence_type == "diagnostic"


# --- SourceVersion ---


def test_source_version_defaults_to_version_one_and_no_locator(db, player):
    material = LearningMaterial(
        player_id=player.player_id, filename="notes.txt", sha256="a" * 64, character_count=200
    )
    db.add(material)
    db.commit()
    db.refresh(material)

    row = SourceVersion(material_id=material.material_id, sha256=material.sha256)
    db.add(row)
    db.commit()
    db.refresh(row)

    response = SourceVersionResponse.model_validate(row)
    assert response.version_number == 1
    assert response.locator == ""
    assert response.material_id == material.material_id


def test_source_version_material_id_is_optional_for_non_upload_sources(db):
    row = SourceVersion(material_id=None, sha256="b" * 64)
    db.add(row)
    db.commit()
    db.refresh(row)

    response = SourceVersionResponse.model_validate(row)
    assert response.material_id is None


# --- AuditEvent / record_audit_event ---


def test_record_audit_event_writes_one_immutable_row(db, player):
    event = record_audit_event(
        db,
        actor=player.player_id,
        action="profile.update",
        entity_type="learner_profile",
        entity_id=player.player_id,
        details={"field": "career_goal"},
    )

    assert event.audit_id is not None
    fetched = db.query(AuditEvent).filter_by(audit_id=event.audit_id).one()
    response = AuditEventResponse.model_validate(fetched)
    assert response.action == "profile.update"
    assert response.details == {"field": "career_goal"}


def test_record_audit_event_defaults_details_to_empty_dict_not_none(db):
    event = record_audit_event(db, actor="system", action="seed.run", entity_type="dungeon")
    assert event.details == {}


def test_audit_events_accumulate_rather_than_overwrite(db):
    record_audit_event(db, actor="system", action="seed.run", entity_type="dungeon")
    record_audit_event(db, actor="system", action="seed.run", entity_type="dungeon")

    assert db.query(AuditEvent).count() == 2
