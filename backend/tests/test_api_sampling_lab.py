"""HTTP contract for the sampling-design virtual lab route.

The lab logic itself (backend/labs/sampling_lab.py) already has full unit
coverage in test_competency_sampling_lab.py -- this file only proves the
route wires it up correctly: task listing never leaks answers, a correct
submission writes both EvidenceRecord and AccuracyHistory (the table
routes/game.py's Prerequisite Pathways room-unlock logic actually reads --
see PR #45's fix for the exact bug this dual-write exists to avoid
repeating), and a wrong submission writes neither.
"""
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base, get_db
from labs.sampling_lab import TASKS
from main import app
from models.accuracy_history import AccuracyHistory
from models.governance import EvidenceRecord
from models.player import Player

client = TestClient(app)


@pytest.fixture()
def db_session(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'sampling_lab.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    db = TestSession()

    def override_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    try:
        yield db
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()


def _make_player(db) -> Player:
    player = Player(username=f"lab-{uuid.uuid4()}")
    db.add(player)
    db.commit()
    db.refresh(player)
    return player


def test_task_list_never_leaks_expected_answers():
    response = client.get("/learning/sampling-lab/tasks")
    assert response.status_code == 200
    tasks = response.json()["tasks"]
    assert len(tasks) == len(TASKS)
    for task in tasks:
        assert "expected" not in task
        assert "parameters" not in task


def test_correct_submission_writes_evidence_and_accuracy_history(db_session):
    player = _make_player(db_session)
    response = client.post(
        "/learning/sampling-lab/submit",
        json={"player_id": player.player_id, "task_id": "srs-basic", "value": 385},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["correct"] is True

    records = db_session.query(EvidenceRecord).filter_by(player_id=player.player_id).all()
    assert len(records) == 1
    assert records[0].evidence_type == "observed_practice"
    assert records[0].competency_id == "os_sampling_design"

    accuracy_rows = db_session.query(AccuracyHistory).filter_by(player_id=player.player_id).all()
    assert len(accuracy_rows) == 1
    assert accuracy_rows[0].topic == "os_sampling_design"
    assert accuracy_rows[0].attempts == 1
    assert accuracy_rows[0].correct == 1


def test_wrong_submission_writes_neither(db_session):
    player = _make_player(db_session)
    response = client.post(
        "/learning/sampling-lab/submit",
        json={"player_id": player.player_id, "task_id": "srs-basic", "value": 100},
    )
    assert response.status_code == 200
    assert response.json()["correct"] is False
    assert db_session.query(EvidenceRecord).filter_by(player_id=player.player_id).count() == 0
    assert db_session.query(AccuracyHistory).filter_by(player_id=player.player_id).count() == 0


def test_unknown_task_is_a_422_not_a_500(db_session):
    player = _make_player(db_session)
    response = client.post(
        "/learning/sampling-lab/submit",
        json={"player_id": player.player_id, "task_id": "not-a-real-task", "value": 1},
    )
    assert response.status_code == 422


def test_unknown_player_is_a_404(db_session):
    response = client.post(
        "/learning/sampling-lab/submit",
        json={"player_id": "not-a-real-player", "task_id": "srs-basic", "value": 385},
    )
    assert response.status_code == 404
