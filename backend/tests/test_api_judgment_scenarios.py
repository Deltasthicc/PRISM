"""HTTP contract for the branching Judgment Simulation feature
(routes/judgment_scenarios.py) built on models/judgment_scenario.py.

Follows test_course_enrollment.py's isolated-app + in-memory-SQLite +
require_principal-override pattern -- these routes are owner-scoped
(require_own_player) and need a real bound principal.
"""
from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base, get_db
# See test_course_enrollment.py's identical comment: Base.metadata is
# process-global, import the full model set so create_all() is correct
# regardless of what else has already run this session.
from models.player import Player
from models.enums import DEFAULT_LEARNING_MODE  # noqa: F401
from models.accuracy_history import AccuracyHistory
from models.question import Question  # noqa: F401
from models.submission import AnswerSubmission  # noqa: F401
from models.guild import Guild  # noqa: F401
from models.dungeon import Dungeon, Room  # noqa: F401
from models.session import GameSession  # noqa: F401
from models.learning import LearnerProfile, CompetencyAssessment, LearningMaterial, GeneratedQuiz  # noqa: F401
from models.governance import EvidenceRecord, RoleTarget, SourceVersion, AuditEvent
from models.identity import IdentityBinding  # noqa: F401
from models.question_bank import QuestionBankItem, QuestionBankAttempt  # noqa: F401
from models.dsa_submission import DsaSubmission  # noqa: F401
from models.course_enrollment import CourseEnrollment  # noqa: F401
from models.proctoring import ProctoringEvent  # noqa: F401
from models.judgment_scenario import JudgmentScenario, JudgmentScenarioAttempt
from routes.authorization import require_principal
from routes.judgment_scenarios import router as judgment_scenarios_router
from security.rbac import BoundPrincipal


class _Subject:
    issuer = "https://issuer.example/realm"
    subject_id = "subject-1"
    roles = frozenset({"learner"})


def _principal(player_id: str) -> BoundPrincipal:
    return BoundPrincipal(subject=_Subject(), binding_id="binding-1", player_id=player_id, roles=_Subject.roles)


def _db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _app(db, principal: BoundPrincipal | None) -> FastAPI:
    app = FastAPI()
    app.include_router(judgment_scenarios_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    if principal is not None:
        app.dependency_overrides[require_principal] = lambda: principal
    return app


def _make_player(db) -> str:
    player_id = str(uuid.uuid4())
    db.add(Player(player_id=player_id, username=f"scenario-{player_id[:8]}"))
    db.commit()
    return player_id


# A small, self-contained 2-level scenario: one real decision at the start
# (a recommended and a non-recommended path), each leading straight to its
# own distinct terminal ending. Enough to exercise every route without
# depending on the full hand-authored content file.
_SCENARIO_ID = "test-scenario-1"
_NODES = {
    "n1": {
        "prompt": "A vendor offers you a favor. What do you do?",
        "choices": [
            {
                "choice_id": "decline",
                "text": "Decline and report it.",
                "next_node_id": "good_ending",
                "feedback": "Declining and reporting protects the process.",
                "is_recommended": True,
            },
            {
                "choice_id": "accept",
                "text": "Accept quietly.",
                "next_node_id": "bad_ending",
                "feedback": "Accepting quietly creates a real conflict of interest.",
                "is_recommended": False,
            },
        ],
    },
    "good_ending": {"prompt": "The process stays clean.", "choices": []},
    "bad_ending": {"prompt": "The conflict surfaces later.", "choices": []},
}


def _make_scenario(db, scenario_id: str = _SCENARIO_ID) -> JudgmentScenario:
    scenario = JudgmentScenario(
        scenario_id=scenario_id,
        competency_id="pa_ethics",
        title="Test Scenario",
        situation_brief="A short test scenario.",
        nodes=_NODES,
        start_node_id="n1",
    )
    db.add(scenario)
    db.commit()
    return scenario


def test_list_scenarios_never_leaks_node_or_choice_internals():
    db = _db()
    player_id = _make_player(db)
    _make_scenario(db)
    client = TestClient(_app(db, _principal(player_id)))

    response = client.get("/learning/scenarios/")
    assert response.status_code == 200
    scenarios = response.json()["scenarios"]
    assert len(scenarios) == 1
    row = scenarios[0]
    assert set(row.keys()) == {"scenario_id", "competency_id", "title", "situation_brief"}
    assert "nodes" not in row


def test_get_node_start_literal_resolves_to_real_start_node_and_hides_answers():
    db = _db()
    player_id = _make_player(db)
    _make_scenario(db)
    client = TestClient(_app(db, _principal(player_id)))

    response = client.get(f"/learning/scenarios/{_SCENARIO_ID}/node/start")
    assert response.status_code == 200
    body = response.json()
    assert body["node_id"] == "n1"
    assert body["prompt"] == _NODES["n1"]["prompt"]
    assert len(body["choices"]) == 2
    for choice in body["choices"]:
        assert set(choice.keys()) == {"choice_id", "text"}


def test_get_node_404_for_unknown_scenario_or_node():
    db = _db()
    player_id = _make_player(db)
    _make_scenario(db)
    client = TestClient(_app(db, _principal(player_id)))

    assert client.get("/learning/scenarios/does-not-exist/node/start").status_code == 404
    assert client.get(f"/learning/scenarios/{_SCENARIO_ID}/node/does-not-exist").status_code == 404


def test_choose_reveals_feedback_only_after_commit_and_persists_nothing():
    db = _db()
    player_id = _make_player(db)
    _make_scenario(db)
    client = TestClient(_app(db, _principal(player_id)))

    response = client.post(
        f"/learning/scenarios/{_SCENARIO_ID}/choose",
        json={"player_id": player_id, "node_id": "n1", "choice_id": "decline"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["feedback"] == _NODES["n1"]["choices"][0]["feedback"]
    assert body["is_recommended"] is True
    assert body["next_node_id"] == "good_ending"
    assert body["is_ending"] is True
    # Nothing is written to the database by /choose alone.
    assert db.query(JudgmentScenarioAttempt).count() == 0
    assert db.query(EvidenceRecord).count() == 0


def test_complete_rejects_a_path_with_an_invalid_edge():
    db = _db()
    player_id = _make_player(db)
    _make_scenario(db)
    client = TestClient(_app(db, _principal(player_id)))

    response = client.post(
        f"/learning/scenarios/{_SCENARIO_ID}/complete",
        json={
            "player_id": player_id,
            "path_taken": [{"node_id": "n1", "choice_id": "not-a-real-choice"}],
        },
    )
    assert response.status_code == 422
    assert db.query(JudgmentScenarioAttempt).count() == 0


def test_complete_rejects_a_path_that_does_not_end_at_a_real_ending():
    db = _db()
    player_id = _make_player(db)
    _make_scenario(db)
    client = TestClient(_app(db, _principal(player_id)))

    # Points a step's node_id at "good_ending", which has no choices at all
    # -- can never legitimately appear as a non-final step.
    response = client.post(
        f"/learning/scenarios/{_SCENARIO_ID}/complete",
        json={
            "player_id": player_id,
            "path_taken": [
                {"node_id": "n1", "choice_id": "decline"},
                {"node_id": "good_ending", "choice_id": "anything"},
            ],
        },
    )
    assert response.status_code == 422


def test_valid_completion_writes_evidence_and_updates_accuracy_history():
    db = _db()
    player_id = _make_player(db)
    _make_scenario(db)
    client = TestClient(_app(db, _principal(player_id)))

    response = client.post(
        f"/learning/scenarios/{_SCENARIO_ID}/complete",
        json={
            "player_id": player_id,
            "path_taken": [{"node_id": "n1", "choice_id": "decline"}],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["recommended_choice_count"] == 1
    assert body["total_choice_count"] == 1
    assert body["completed_at"] is not None

    attempts = db.query(JudgmentScenarioAttempt).filter_by(player_id=player_id).all()
    assert len(attempts) == 1
    assert attempts[0].path_taken == [{"node_id": "n1", "choice_id": "decline"}]

    evidence = db.query(EvidenceRecord).filter_by(player_id=player_id).all()
    assert len(evidence) == 1
    assert evidence[0].evidence_type == "observed_practice"
    assert evidence[0].competency_id == "pa_ethics"
    assert evidence[0].value == 1.0
    assert "Test Scenario" in evidence[0].detail

    acc = (
        db.query(AccuracyHistory)
        .filter_by(player_id=player_id, topic="pa_ethics")
        .first()
    )
    assert acc is not None
    assert acc.attempts == 1
    assert acc.correct == 1
    assert acc.recent_accuracy == 1.0


def test_recompleting_a_scenario_is_allowed_and_adds_another_attempt_row():
    db = _db()
    player_id = _make_player(db)
    _make_scenario(db)
    client = TestClient(_app(db, _principal(player_id)))
    payload = {
        "player_id": player_id,
        "path_taken": [{"node_id": "n1", "choice_id": "accept"}],
    }

    first = client.post(f"/learning/scenarios/{_SCENARIO_ID}/complete", json=payload)
    second = client.post(f"/learning/scenarios/{_SCENARIO_ID}/complete", json=payload)

    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["attempt_id"] != second.json()["attempt_id"]
    assert db.query(JudgmentScenarioAttempt).filter_by(player_id=player_id).count() == 2
    assert db.query(EvidenceRecord).filter_by(player_id=player_id).count() == 2


def test_cannot_fetch_another_players_attempts():
    db = _db()
    player_id = _make_player(db)
    other_player_id = _make_player(db)
    _make_scenario(db)
    client = TestClient(_app(db, _principal(player_id)))

    client.post(
        f"/learning/scenarios/{_SCENARIO_ID}/complete",
        json={"player_id": player_id, "path_taken": [{"node_id": "n1", "choice_id": "decline"}]},
    )

    other_client = TestClient(_app(db, _principal(other_player_id)))
    response = other_client.get(
        f"/learning/scenarios/{_SCENARIO_ID}/attempts",
        params={"player_id": player_id},
    )
    assert response.status_code == 403


def test_own_attempts_are_listed_correctly():
    db = _db()
    player_id = _make_player(db)
    _make_scenario(db)
    client = TestClient(_app(db, _principal(player_id)))

    client.post(
        f"/learning/scenarios/{_SCENARIO_ID}/complete",
        json={"player_id": player_id, "path_taken": [{"node_id": "n1", "choice_id": "decline"}]},
    )

    response = client.get(
        f"/learning/scenarios/{_SCENARIO_ID}/attempts",
        params={"player_id": player_id},
    )
    assert response.status_code == 200
    attempts = response.json()["attempts"]
    assert len(attempts) == 1
    assert attempts[0]["recommended_choice_count"] == 1
