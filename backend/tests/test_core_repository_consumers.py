"""Cross-lane contracts for Lane 2's read-only repository facade.

These tests intentionally exercise storage semantics only. Route-level identity,
permission and own-player checks remain mandatory before a caller reaches these
functions; see docs/contracts/data-authorization.md.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from db.database import Base
from db.repositories import (
    get_current_role_target,
    get_latest_evidence,
    get_latest_source_version,
)
from models.accuracy_history import AccuracyHistory  # noqa: F401 -- metadata dependency
from models.dungeon import Dungeon, Room  # noqa: F401 -- metadata dependency
from models.governance import EvidenceRecord, RoleTarget, SourceVersion
from models.guild import Guild  # noqa: F401 -- metadata dependency
from models.identity import IdentityBinding  # noqa: F401 -- metadata dependency
from models.learning import LearningMaterial
from models.player import Player
from models.question import Question  # noqa: F401 -- metadata dependency
from models.session import GameSession  # noqa: F401 -- metadata dependency
from models.submission import AnswerSubmission  # noqa: F401 -- metadata dependency


PLAYER_A = "consumer-player-a"
PLAYER_B = "consumer-player-b"
COMPETENCY = "os_sampling_design"
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all(
        [
            Player(player_id=PLAYER_A, username="consumer_a"),
            Player(player_id=PLAYER_B, username="consumer_b"),
        ]
    )
    session.commit()
    yield session
    session.close()
    engine.dispose()


def _target(
    target_id: str,
    *,
    role: str = "statistical officer",
    competency_id: str = COMPETENCY,
    valid_from: datetime | None = T0,
    valid_to: datetime | None = None,
    created_at: datetime | None = T0,
    level: int = 3,
) -> RoleTarget:
    return RoleTarget(
        target_id=target_id,
        role=role,
        competency_id=competency_id,
        target_level=level,
        source="internal-prototype",
        valid_from=valid_from,
        valid_to=valid_to,
        created_at=created_at,
    )


def _evidence(
    evidence_id: str,
    *,
    player_id: str = PLAYER_A,
    competency_id: str = COMPETENCY,
    evidence_type: str = "diagnostic",
    recorded_at: datetime | None = T0,
    value: int = 2,
) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        player_id=player_id,
        competency_id=competency_id,
        evidence_type=evidence_type,
        recorded_at=recorded_at,
        value=value,
    )


def test_current_role_target_returns_none_for_an_empty_stream(db):
    assert get_current_role_target(db, "statistical officer", COMPETENCY, as_of=T0) is None


def test_current_role_target_applies_half_open_validity_window(db):
    db.add_all(
        [
            _target("expired", valid_from=T0 - timedelta(days=2), valid_to=T0),
            _target("starts-now", valid_from=T0, valid_to=T0 + timedelta(days=1)),
            _target("future", valid_from=T0 + timedelta(seconds=1)),
        ]
    )
    db.commit()

    result = get_current_role_target(db, "statistical officer", COMPETENCY, as_of=T0)
    assert result.target_id == "starts-now"


def test_current_role_target_rejects_null_start_and_resolves_overlap_deterministically(db):
    db.add_all(
        [
            _target("unknown-start", valid_from=None, created_at=T0 + timedelta(days=10)),
            _target("older-window", valid_from=T0 - timedelta(days=2), level=2),
            _target("newer-window-a", valid_from=T0 - timedelta(days=1), created_at=T0, level=4),
            _target("newer-window-z", valid_from=T0 - timedelta(days=1), created_at=T0, level=5),
        ]
    )
    db.commit()
    # ORM defaults replace explicit None during INSERT; force the legacy/null
    # case through SQL so the test exercises the documented rejection.
    db.execute(text("UPDATE role_targets SET valid_from = NULL WHERE target_id = 'unknown-start'"))
    db.commit()

    result = get_current_role_target(
        db, "statistical officer", COMPETENCY, as_of=T0 + timedelta(hours=1)
    )
    assert result.target_id == "newer-window-z"
    assert result.target_level == 5


def test_current_role_target_is_exact_and_does_not_invent_lane3_policy(db):
    db.add_all(
        [
            _target("wildcard", role="*"),
            _target("different-case", role="Statistical Officer"),
        ]
    )
    db.commit()

    assert (
        get_current_role_target(db, "statistical officer", COMPETENCY, as_of=T0)
        is None
    )


def test_current_role_target_isolated_by_competency_for_same_role(db):
    db.add_all(
        [
            _target("requested", level=3),
            _target(
                "other-competency-newer",
                competency_id="os_data_quality",
                valid_from=T0 + timedelta(hours=1),
                created_at=T0 + timedelta(days=1),
                level=5,
            ),
        ]
    )
    db.commit()

    result = get_current_role_target(
        db,
        "statistical officer",
        COMPETENCY,
        as_of=T0 + timedelta(hours=2),
    )
    assert result.target_id == "requested"
    assert result.competency_id == COMPETENCY


def test_current_role_target_validates_keys_and_timezone(db):
    with pytest.raises(ValueError, match="role"):
        get_current_role_target(db, " ", COMPETENCY, as_of=T0)
    with pytest.raises(ValueError, match="competency_id"):
        get_current_role_target(db, "statistical officer", "", as_of=T0)
    with pytest.raises(ValueError, match="timezone-aware"):
        get_current_role_target(
            db, "statistical officer", COMPETENCY, as_of=datetime(2026, 1, 1)
        )


def test_latest_evidence_is_isolated_by_player_competency_and_type(db):
    db.add_all(
        [
            _evidence("mine-old", recorded_at=T0),
            _evidence("mine-new", recorded_at=T0 + timedelta(days=1), value=4),
            _evidence("other-player", player_id=PLAYER_B, recorded_at=T0 + timedelta(days=2)),
            _evidence("other-type", evidence_type="self_report", recorded_at=T0 + timedelta(days=3)),
            _evidence("other-competency", competency_id="os_data_quality", recorded_at=T0 + timedelta(days=4)),
        ]
    )
    db.commit()

    result = get_latest_evidence(db, PLAYER_A, COMPETENCY, "diagnostic")
    assert result.evidence_id == "mine-new"
    assert result.value == 4


def test_latest_evidence_prefers_timestamp_then_id_and_sorts_null_last(db):
    db.add_all(
        [
            _evidence("aaa", recorded_at=T0),
            _evidence("zzz", recorded_at=T0, value=4),
            _evidence("null-time", recorded_at=T0 + timedelta(days=3), value=5),
        ]
    )
    db.commit()
    db.execute(
        text("UPDATE evidence_records SET recorded_at = NULL WHERE evidence_id = 'null-time'")
    )
    db.commit()

    result = get_latest_evidence(db, PLAYER_A, COMPETENCY, "diagnostic")
    assert result.evidence_id == "zzz"


def test_latest_evidence_returns_none_and_rejects_unknown_type(db):
    assert get_latest_evidence(db, PLAYER_A, COMPETENCY, "reviewer") is None
    with pytest.raises(ValueError, match="evidence_type"):
        get_latest_evidence(db, PLAYER_A, COMPETENCY, "quiz")
    with pytest.raises(ValueError, match="player_id"):
        get_latest_evidence(db, "", COMPETENCY, "diagnostic")


def test_latest_source_version_uses_version_number_before_timestamp(db):
    material = LearningMaterial(
        material_id="material-a",
        player_id=PLAYER_A,
        filename="sampling.md",
        sha256="material-hash",
    )
    db.add(material)
    db.add_all(
        [
            SourceVersion(
                source_version_id="version-1-newer-time",
                material_id=material.material_id,
                version_number=1,
                sha256="hash-v1",
                created_at=T0 + timedelta(days=5),
            ),
            SourceVersion(
                source_version_id="version-2-a",
                material_id=material.material_id,
                version_number=2,
                sha256="hash-v2a",
                created_at=T0,
            ),
            SourceVersion(
                source_version_id="version-2-z",
                material_id=material.material_id,
                version_number=2,
                sha256="hash-v2z",
                created_at=T0,
            ),
        ]
    )
    db.commit()

    result = get_latest_source_version(db, material.material_id)
    assert result.source_version_id == "version-2-z"
    assert result.sha256 == "hash-v2z"


def test_latest_source_version_does_not_cross_material_boundary(db):
    materials = [
        LearningMaterial(
            material_id="material-a",
            player_id=PLAYER_A,
            filename="a.md",
            sha256="material-a-hash",
        ),
        LearningMaterial(
            material_id="material-b",
            player_id=PLAYER_B,
            filename="b.md",
            sha256="material-b-hash",
        ),
    ]
    db.add_all(materials)
    db.add_all(
        [
            SourceVersion(
                source_version_id="a-v1",
                material_id="material-a",
                version_number=1,
                sha256="a-hash",
            ),
            SourceVersion(
                source_version_id="b-v99",
                material_id="material-b",
                version_number=99,
                sha256="b-hash",
            ),
        ]
    )
    db.commit()

    assert get_latest_source_version(db, "material-a").source_version_id == "a-v1"
    assert get_latest_source_version(db, "missing") is None
    with pytest.raises(ValueError, match="material_id"):
        get_latest_source_version(db, " ")


def test_all_repository_reads_leave_the_session_unmodified(db):
    db.add(_target("target"))
    db.add(_evidence("evidence"))
    material = LearningMaterial(
        material_id="material-a",
        player_id=PLAYER_A,
        filename="a.md",
        sha256="material-a-hash",
    )
    db.add(material)
    db.add(
        SourceVersion(
            source_version_id="source-version",
            material_id="material-a",
            version_number=1,
            sha256="source-hash",
        )
    )
    db.commit()

    get_current_role_target(db, "statistical officer", COMPETENCY, as_of=T0)
    get_latest_evidence(db, PLAYER_A, COMPETENCY, "diagnostic")
    get_latest_source_version(db, "material-a")

    assert not db.new
    assert not db.dirty
    assert not db.deleted
