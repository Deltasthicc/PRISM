"""Tests for services/evidence_resolver.py against real EvidenceRecord rows.

The resolver is the seam between Lane 2's storage (`db/repositories.py`) and
Lane 3's pure gap engine: it reads rows here so `analyse_competencies()` never
has to, keeping that function pure and its golden fixtures exact.

DB setup mirrors tests/test_core_repositories.py so both lanes exercise the
same ordering contract the same way.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base
from models.accuracy_history import AccuracyHistory  # noqa: F401 -- relationship target
from models.dungeon import Dungeon, Room  # noqa: F401 -- relationship target
from models.governance import EvidenceRecord
from models.guild import Guild  # noqa: F401 -- relationship target
from models.player import Player
from models.question import Question  # noqa: F401 -- relationship target
from models.session import GameSession  # noqa: F401 -- relationship target
from models.submission import AnswerSubmission  # noqa: F401 -- relationship target
from services.evidence_resolver import resolve_evidence
from services.learning_engine import analyse_competencies

PLAYER_ID = "evidence-test-player"
OTHER_PLAYER_ID = "evidence-test-other"
COMPETENCY = "os_data_quality"
T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([
        Player(player_id=PLAYER_ID, username="evidence_test"),
        Player(player_id=OTHER_PLAYER_ID, username="evidence_test_other"),
    ])
    session.commit()
    yield session
    session.close()


def test_returns_nothing_when_no_rows_exist(db):
    assert resolve_evidence(db, PLAYER_ID, [COMPETENCY]) == {}


def test_separates_each_evidence_type(db):
    db.add_all([
        EvidenceRecord(player_id=PLAYER_ID, competency_id=COMPETENCY,
                       evidence_type="self_report", value=2, recorded_at=T0),
        EvidenceRecord(player_id=PLAYER_ID, competency_id=COMPETENCY,
                       evidence_type="reviewer", value=None, detail="Panel note", recorded_at=T0),
    ])
    db.commit()

    resolved = resolve_evidence(db, PLAYER_ID, [COMPETENCY])
    assert set(resolved[COMPETENCY]) == {"self_report", "reviewer"}
    assert resolved[COMPETENCY]["self_report"]["value"] == 2
    # A qualitative reviewer row keeps a null value rather than becoming a zero.
    assert resolved[COMPETENCY]["reviewer"]["value"] is None
    assert resolved[COMPETENCY]["reviewer"]["detail"] == "Panel note"


def test_takes_the_latest_row_per_type(db):
    db.add_all([
        EvidenceRecord(player_id=PLAYER_ID, competency_id=COMPETENCY,
                       evidence_type="self_report", value=1, recorded_at=T0),
        EvidenceRecord(player_id=PLAYER_ID, competency_id=COMPETENCY,
                       evidence_type="self_report", value=4, recorded_at=T0 + timedelta(days=1)),
    ])
    db.commit()
    # A correction is a new row, never an edit -- the newest must win.
    assert resolve_evidence(db, PLAYER_ID, [COMPETENCY])[COMPETENCY]["self_report"]["value"] == 4


def test_isolates_by_player(db):
    db.add(EvidenceRecord(player_id=OTHER_PLAYER_ID, competency_id=COMPETENCY,
                          evidence_type="self_report", value=5, recorded_at=T0))
    db.commit()
    assert resolve_evidence(db, PLAYER_ID, [COMPETENCY]) == {}


def test_isolates_by_competency(db):
    db.add(EvidenceRecord(player_id=PLAYER_ID, competency_id="os_gis",
                          evidence_type="self_report", value=5, recorded_at=T0))
    db.commit()
    resolved = resolve_evidence(db, PLAYER_ID, [COMPETENCY, "os_gis"])
    assert COMPETENCY not in resolved
    assert resolved["os_gis"]["self_report"]["value"] == 5


def test_resolved_evidence_flows_into_the_engine(db):
    # The full seam: rows -> resolver -> pure engine, with no DB inside the engine.
    db.add_all([
        EvidenceRecord(player_id=PLAYER_ID, competency_id=COMPETENCY,
                       evidence_type="self_report", value=2, recorded_at=T0),
        EvidenceRecord(player_id=PLAYER_ID, competency_id=COMPETENCY,
                       evidence_type="observed_practice", value=4, recorded_at=T0),
        EvidenceRecord(player_id=PLAYER_ID, competency_id=COMPETENCY,
                       evidence_type="reviewer", value=None, detail="note", recorded_at=T0),
    ])
    db.commit()

    result = analyse_competencies(
        "official-statistics", {}, {}, "expert",
        evidence=resolve_evidence(db, PLAYER_ID, [COMPETENCY]),
    )
    row = next(c for c in result["competencies"] if c["competency_id"] == COMPETENCY)
    # 65% observed_practice + 35% self_report, from stored rows.
    assert row["observed_level"] == pytest.approx(4 * 0.65 + 2 * 0.35, abs=0.01)
    assert row["has_scored_evidence"] is True
    assert {r["evidence_type"] for r in row["evidence_records"]} == {
        "self_report", "observed_practice", "reviewer",
    }
