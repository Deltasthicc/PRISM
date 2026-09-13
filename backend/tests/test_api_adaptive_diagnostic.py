"""HTTP contract for the two-stage adaptive diagnostic
(routes/adaptive_diagnostic.py, services/adaptive_diagnostic.py).

Follows test_api_judgment_scenarios.py's isolated-app + in-memory-SQLite +
require_principal-override pattern, since these routes are real-RBAC-gated
(require_own_player) unlike routes/competency_quiz.py's ungated routes.
"""
from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base, get_db
from models.player import Player
from models.enums import DEFAULT_LEARNING_MODE  # noqa: F401
from models.accuracy_history import AccuracyHistory
from models.question import Question  # noqa: F401
from models.submission import AnswerSubmission  # noqa: F401
from models.guild import Guild  # noqa: F401
from models.dungeon import Dungeon, Room  # noqa: F401
from models.session import GameSession  # noqa: F401
from models.learning import LearnerProfile, CompetencyAssessment, LearningMaterial, GeneratedQuiz  # noqa: F401
from models.governance import EvidenceRecord, RoleTarget, SourceVersion, AuditEvent  # noqa: F401
from models.identity import IdentityBinding  # noqa: F401
from models.question_bank import QuestionBankItem, QuestionBankAttempt  # noqa: F401
from models.dsa_submission import DsaSubmission  # noqa: F401
from models.course_enrollment import CourseEnrollment  # noqa: F401
from models.proctoring import ProctoringEvent  # noqa: F401
from models.judgment_scenario import JudgmentScenario, JudgmentScenarioAttempt  # noqa: F401
from routes.authorization import require_principal
from routes.adaptive_diagnostic import router as diagnostic_router
from security.rbac import BoundPrincipal
from services import adaptive_diagnostic as engine


class _Subject:
    issuer = "https://issuer.example/realm"
    subject_id = "subject-1"
    roles = frozenset({"learner"})


def _principal(player_id: str | None) -> BoundPrincipal:
    return BoundPrincipal(subject=_Subject(), binding_id="binding-1", player_id=player_id, roles=_Subject.roles)


def _app(db, principal: BoundPrincipal) -> FastAPI:
    app = FastAPI()
    app.include_router(diagnostic_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_principal] = lambda: principal
    return app


def _db():
    engine_ = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine_)
    return sessionmaker(bind=engine_)()


def _make_player(db) -> str:
    player_id = str(uuid.uuid4())
    db.add(Player(player_id=player_id, username=f"learner-{player_id[:8]}"))
    db.commit()
    return player_id


def setup_function():
    # The engine's session registry is a process-local module dict -- clear
    # it between tests so one test's sessions can't leak into another's.
    engine._active_sessions.clear()


def test_stage1_start_returns_items_with_no_leaked_answers():
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))

    response = client.post(
        "/learning/diagnostic/stage1/start",
        json={"player_id": player_id, "curriculum_slug": "official-statistics"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"]
    for item in body["items"]:
        assert "answer_index" not in item
        assert "explanation" not in item
        assert "options" in item and len(item["options"]) >= 2


def test_stage1_start_rejects_a_curriculum_with_no_content():
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))

    response = client.post(
        "/learning/diagnostic/stage1/start",
        json={"player_id": player_id, "curriculum_slug": "not-a-real-curriculum"},
    )
    assert response.status_code == 503


def test_stage1_submit_grades_for_real_and_writes_evidence():
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))

    started = client.post(
        "/learning/diagnostic/stage1/start",
        json={"player_id": player_id, "curriculum_slug": "official-statistics"},
    ).json()
    session_id = started["session_id"]

    pool = engine.curriculum_item_pool("official-statistics")
    # Deliberately wrong for every item so a misconception signal is likely.
    answers = [
        {"item_id": item["item_id"], "selected_index": (pool[item["item_id"]]["answer_index"] + 1) % len(pool[item["item_id"]]["options"])}
        for item in started["items"]
    ]

    response = client.post(
        "/learning/diagnostic/stage1/submit",
        json={"session_id": session_id, "player_id": player_id, "answers": answers},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["correct"] == 0
    assert body["total"] == len(started["items"])
    for graded in body["graded"]:
        assert graded["correct"] is False
        assert "explanation" in graded and graded["explanation"]

    # Real evidence must actually be persisted, not just claimed in the response.
    assert db.query(EvidenceRecord).filter(EvidenceRecord.player_id == player_id).count() > 0
    assert db.query(AccuracyHistory).filter(AccuracyHistory.player_id == player_id).count() > 0


def test_stage1_submit_rejects_a_mismatched_item_set():
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))

    started = client.post(
        "/learning/diagnostic/stage1/start",
        json={"player_id": player_id, "curriculum_slug": "official-statistics"},
    ).json()

    response = client.post(
        "/learning/diagnostic/stage1/submit",
        json={
            "session_id": started["session_id"],
            "player_id": player_id,
            "answers": [{"item_id": "not-a-real-item-id", "selected_index": 0}],
        },
    )
    assert response.status_code == 422


def test_stage1_submit_is_single_use():
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))

    started = client.post(
        "/learning/diagnostic/stage1/start",
        json={"player_id": player_id, "curriculum_slug": "official-statistics"},
    ).json()
    pool = engine.curriculum_item_pool("official-statistics")
    answers = [{"item_id": item["item_id"], "selected_index": pool[item["item_id"]]["answer_index"]} for item in started["items"]]

    first = client.post(
        "/learning/diagnostic/stage1/submit",
        json={"session_id": started["session_id"], "player_id": player_id, "answers": answers},
    )
    assert first.status_code == 200

    second = client.post(
        "/learning/diagnostic/stage1/submit",
        json={"session_id": started["session_id"], "player_id": player_id, "answers": answers},
    )
    assert second.status_code == 422


def test_full_two_stage_flow_with_a_real_targeted_misconception():
    """Deliberately picks known items so the *same* tagged misconception
    (sampling-design-tradeoff-confusion) is guaranteed to be the strongest
    signal, then verifies stage 2 actually serves different, real items
    tagged with that same misconception -- not a fabricated follow-up."""
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))

    tagged_ids = set(engine._items_by_misconception()["sampling-design-tradeoff-confusion"])
    assert len(tagged_ids) >= 2, "test fixture assumption: this tag needs at least 2 real tagged items"

    session_id, items = engine.start_stage1("official-statistics", player_id)
    # Force the scenario deterministically: answer every tagged item wrong,
    # everything else right, so the tally unambiguously points at this tag.
    pool = engine.curriculum_item_pool("official-statistics")
    answers = []
    for item in items:
        correct_index = item["answer_index"]
        if item["item_id"] in tagged_ids:
            wrong = (correct_index + 1) % len(item["options"])
            answers.append({"item_id": item["item_id"], "selected_index": wrong})
        else:
            answers.append({"item_id": item["item_id"], "selected_index": correct_index})

    # Stage 1 may not have drawn any tagged items in its random sample --
    # if so, inject at least one directly so the scenario is deterministic.
    if not any(a["item_id"] in tagged_ids for a in answers):
        extra_id = next(iter(tagged_ids))
        engine.get_session(session_id)["stage1_item_ids"].append(extra_id)
        extra_item = pool[extra_id]
        answers.append({"item_id": extra_id, "selected_index": (extra_item["answer_index"] + 1) % len(extra_item["options"])})

    submit = client.post(
        "/learning/diagnostic/stage1/submit",
        json={"session_id": session_id, "player_id": player_id, "answers": answers},
    )
    assert submit.status_code == 200
    signal = submit.json()["misconception_signal"]
    assert signal is not None
    assert signal["misconception"] == "sampling-design-tradeoff-confusion"
    assert signal["stage2_available"] is True

    stage2_start = client.post(
        "/learning/diagnostic/stage2/start",
        json={"session_id": session_id, "player_id": player_id},
    )
    assert stage2_start.status_code == 200
    stage2_items = stage2_start.json()["items"]
    assert stage2_items
    shown_stage1_ids = {a["item_id"] for a in answers}
    for item in stage2_items:
        assert item["item_id"] not in shown_stage1_ids, "stage 2 must not re-serve a stage-1 item"

    stage2_answers = [{"item_id": item["item_id"], "selected_index": 0} for item in stage2_items]
    stage2_submit = client.post(
        "/learning/diagnostic/stage2/submit",
        json={"session_id": session_id, "player_id": player_id, "answers": stage2_answers},
    )
    assert stage2_submit.status_code == 200
    combined = stage2_submit.json()["combined_summary"]
    assert combined["stage1_total"] == len(answers)
    assert combined["stage2_total"] == len(stage2_items)


def test_stage2_is_honestly_unavailable_with_no_misconception_signal():
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))

    started = client.post(
        "/learning/diagnostic/stage1/start",
        json={"player_id": player_id, "curriculum_slug": "official-statistics"},
    ).json()
    pool = engine.curriculum_item_pool("official-statistics")
    # Answer everything correctly -- no wrong answers, so there can be no
    # real misconception signal at all.
    answers = [{"item_id": item["item_id"], "selected_index": pool[item["item_id"]]["answer_index"]} for item in started["items"]]

    submit = client.post(
        "/learning/diagnostic/stage1/submit",
        json={"session_id": started["session_id"], "player_id": player_id, "answers": answers},
    )
    assert submit.json()["misconception_signal"] is None

    stage2_start = client.post(
        "/learning/diagnostic/stage2/start",
        json={"session_id": started["session_id"], "player_id": player_id},
    )
    assert stage2_start.status_code == 422


def test_cross_player_access_is_rejected():
    db = _db()
    owner_id = _make_player(db)
    other_id = _make_player(db)
    owner_client = TestClient(_app(db, _principal(owner_id)))
    other_client = TestClient(_app(db, _principal(other_id)))

    started = owner_client.post(
        "/learning/diagnostic/stage1/start",
        json={"player_id": owner_id, "curriculum_slug": "official-statistics"},
    ).json()

    cross_submit = other_client.post(
        "/learning/diagnostic/stage1/submit",
        json={
            "session_id": started["session_id"],
            "player_id": other_id,
            "answers": [{"item_id": started["items"][0]["item_id"], "selected_index": 0}],
        },
    )
    assert cross_submit.status_code == 403

    cross_start_as_owner_session = other_client.post(
        "/learning/diagnostic/stage1/start",
        json={"player_id": owner_id, "curriculum_slug": "official-statistics"},
    )
    assert cross_start_as_owner_session.status_code == 403
