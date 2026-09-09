"""HTTP contract for the Source Quiz Generator's scored take/retake flow
(routes/learning_content.py's GET /learning/quiz/detail/{quiz_id} and
POST /learning/quiz/{quiz_id}/submit).

Follows test_dsa_sandbox.py's isolated-app + in-memory-SQLite +
require_principal-override pattern -- these routes are owner-scoped
(require_own_player) and need a real bound principal to exercise properly.
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
from models.accuracy_history import AccuracyHistory  # noqa: F401
from models.question import Question  # noqa: F401
from models.submission import AnswerSubmission  # noqa: F401
from models.guild import Guild  # noqa: F401
from models.dungeon import Dungeon, Room  # noqa: F401
from models.session import GameSession  # noqa: F401
from models.learning import LearnerProfile, CompetencyAssessment, LearningMaterial, GeneratedQuiz
from models.governance import RoleTarget, EvidenceRecord, SourceVersion, AuditEvent  # noqa: F401
from models.identity import IdentityBinding  # noqa: F401
from models.question_bank import QuestionBankItem, QuestionBankAttempt  # noqa: F401
from models.dsa_submission import DsaSubmission  # noqa: F401
from routes.authorization import require_principal
from routes.learning_content import router as learning_content_router
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
    app.include_router(learning_content_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    if principal is not None:
        app.dependency_overrides[require_principal] = lambda: principal
    return app


def _make_player(db) -> str:
    player_id = str(uuid.uuid4())
    db.add(Player(player_id=player_id, username=f"quiz-submit-{player_id[:8]}"))
    db.commit()
    return player_id


_QUESTIONS = [
    {
        "question": "Q1?",
        "options": ["a", "b", "c", "d"],
        "answer_index": 1,
        "explanation": "because",
        "source_excerpt": "excerpt one",
        "competency": "Source comprehension",
        "bloom_level": "understand",
        "difficulty": "easy",
    },
    {
        "question": "Q2?",
        "options": ["a", "b", "c", "d"],
        "answer_index": 2,
        "explanation": "because",
        "source_excerpt": "excerpt two",
        "competency": "Source comprehension",
        "bloom_level": "apply",
        "difficulty": "hard",
    },
]


def _make_quiz(db, player_id: str) -> str:
    material = LearningMaterial(
        player_id=player_id,
        filename="doc.txt",
        sha256="deadbeef",
        character_count=100,
        text_excerpt="excerpt",
    )
    db.add(material)
    db.flush()
    quiz = GeneratedQuiz(
        material_id=material.material_id,
        player_id=player_id,
        title="Test Quiz",
        difficulty="mixed",
        language="English",
        questions=_QUESTIONS,
        generation_mode="extractive-fallback",
    )
    db.add(quiz)
    db.commit()
    return quiz.quiz_id


def test_get_quiz_detail_returns_full_questions():
    db = _db()
    player_id = _make_player(db)
    quiz_id = _make_quiz(db, player_id)
    client = TestClient(_app(db, _principal(player_id)))

    response = client.get(f"/learning/quiz/detail/{quiz_id}", params={"player_id": player_id})
    assert response.status_code == 200
    body = response.json()
    assert body["quiz_id"] == quiz_id
    assert len(body["questions"]) == 2
    assert body["questions"][0]["difficulty"] == "easy"


def test_submit_all_correct_scores_full_marks():
    db = _db()
    player_id = _make_player(db)
    quiz_id = _make_quiz(db, player_id)
    client = TestClient(_app(db, _principal(player_id)))

    response = client.post(
        f"/learning/quiz/{quiz_id}/submit",
        json={
            "player_id": player_id,
            "answers": [
                {"question_index": 0, "selected_index": 1, "time_taken_ms": 20000},
                {"question_index": 1, "selected_index": 2, "time_taken_ms": 75000},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["correct_count"] == 2
    assert body["accuracy"] == 1.0
    assert body["weighted_score"] == 100.0
    assert body["by_difficulty"]["easy"]["count"] == 1
    assert body["by_difficulty"]["hard"]["count"] == 1

    quiz = db.query(GeneratedQuiz).filter(GeneratedQuiz.quiz_id == quiz_id).first()
    assert quiz.best_score == 100.0
    assert quiz.last_attempted_at is not None


def test_submit_partial_correct_weighs_hard_questions_more():
    db = _db()
    player_id = _make_player(db)
    quiz_id = _make_quiz(db, player_id)
    client = TestClient(_app(db, _principal(player_id)))

    # Only the easy question (weight 1.0) right; the hard one (weight 2.0)
    # wrong -- weighted_score should be well below 50% since missing the
    # harder question costs more than the easy one earns.
    response = client.post(
        f"/learning/quiz/{quiz_id}/submit",
        json={
            "player_id": player_id,
            "answers": [
                {"question_index": 0, "selected_index": 1},
                {"question_index": 1, "selected_index": 0},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["correct_count"] == 1
    assert body["accuracy"] == 0.5
    assert body["weighted_score"] < 40.0


def test_submit_faster_than_expected_scores_above_full_accuracy_baseline():
    db = _db()
    player_id = _make_player(db)
    quiz_id = _make_quiz(db, player_id)
    client = TestClient(_app(db, _principal(player_id)))

    # Both correct, both answered much faster than the easy/hard reference
    # times -- the bounded time factor should push weighted_score above the
    # plain (untimed) 100%... but it's capped, so still <= 110% of baseline.
    response = client.post(
        f"/learning/quiz/{quiz_id}/submit",
        json={
            "player_id": player_id,
            "answers": [
                {"question_index": 0, "selected_index": 1, "time_taken_ms": 1000},
                {"question_index": 1, "selected_index": 2, "time_taken_ms": 1000},
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["weighted_score"] == 110.0
    for result in body["results"]:
        assert result["pace"] == "faster"


def test_second_submission_keeps_the_higher_best_score():
    db = _db()
    player_id = _make_player(db)
    quiz_id = _make_quiz(db, player_id)
    client = TestClient(_app(db, _principal(player_id)))

    client.post(
        f"/learning/quiz/{quiz_id}/submit",
        json={"player_id": player_id, "answers": [{"question_index": 0, "selected_index": 1}]},
    )
    client.post(
        f"/learning/quiz/{quiz_id}/submit",
        json={"player_id": player_id, "answers": [{"question_index": 0, "selected_index": 0}]},
    )

    quiz = db.query(GeneratedQuiz).filter(GeneratedQuiz.quiz_id == quiz_id).first()
    assert quiz.best_score == 100.0


def test_submit_rejects_another_players_quiz():
    db = _db()
    player_id = _make_player(db)
    other_player_id = _make_player(db)
    quiz_id = _make_quiz(db, player_id)
    client = TestClient(_app(db, _principal(other_player_id)))

    response = client.post(
        f"/learning/quiz/{quiz_id}/submit",
        json={"player_id": other_player_id, "answers": [{"question_index": 0, "selected_index": 1}]},
    )
    assert response.status_code == 403


def test_submit_unknown_quiz_id_404s():
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))

    response = client.post(
        "/learning/quiz/not-a-real-quiz/submit",
        json={"player_id": player_id, "answers": [{"question_index": 0, "selected_index": 1}]},
    )
    assert response.status_code == 404


def test_submit_requires_verified_bearer():
    db = _db()
    player_id = _make_player(db)
    quiz_id = _make_quiz(db, player_id)
    client = TestClient(_app(db, None))

    response = client.post(
        f"/learning/quiz/{quiz_id}/submit",
        json={"player_id": player_id, "answers": [{"question_index": 0, "selected_index": 1}]},
    )
    assert response.status_code == 401
