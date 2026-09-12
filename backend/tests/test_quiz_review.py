"""HTTP contract for the real trainer review/approval workflow
(routes/quiz_review.py) and its effect on the existing generated-quiz
routes (routes/learning_content.py) -- a private quiz's owner-only
behavior must stay exactly as before, while a published quiz becomes
takeable by anyone, with a separate GeneratedQuizAttempt per taker.

Follows test_course_enrollment.py's isolated-app + in-memory-SQLite +
require_principal-override pattern.
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
from models.learning import (
    LearnerProfile,
    CompetencyAssessment,
    LearningMaterial,
    GeneratedQuiz,
    GeneratedQuizAttempt,
)
from models.governance import EvidenceRecord, RoleTarget, SourceVersion, AuditEvent  # noqa: F401
from models.identity import IdentityBinding  # noqa: F401
from models.question_bank import QuestionBankItem, QuestionBankAttempt  # noqa: F401
from models.dsa_submission import DsaSubmission  # noqa: F401
from models.course_enrollment import CourseEnrollment  # noqa: F401
from models.proctoring import ProctoringEvent  # noqa: F401
from routes.authorization import require_principal
from routes.learning_content import router as content_router
from routes.quiz_review import router as review_router
from security.rbac import BoundPrincipal


class _Subject:
    issuer = "https://issuer.example/realm"
    subject_id = "subject-1"

    def __init__(self, roles):
        self.roles = frozenset(roles)


def _principal(player_id: str | None, roles=("learner",)) -> BoundPrincipal:
    subject = _Subject(roles)
    return BoundPrincipal(subject=subject, binding_id="binding-1", player_id=player_id, roles=subject.roles)


def _db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _app(db, principal: BoundPrincipal | None) -> FastAPI:
    app = FastAPI()
    app.include_router(content_router)
    app.include_router(review_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    if principal is not None:
        app.dependency_overrides[require_principal] = lambda: principal
    return app


def _make_player(db, username_prefix="learner") -> str:
    player_id = str(uuid.uuid4())
    db.add(Player(player_id=player_id, username=f"{username_prefix}-{player_id[:8]}"))
    db.commit()
    return player_id


def _make_quiz(db, player_id: str, review_status: str = "private") -> str:
    material = LearningMaterial(
        player_id=player_id,
        filename="notes.txt",
        content_type="text/plain",
        sha256="a" * 64,
        character_count=500,
        text_excerpt="excerpt",
    )
    db.add(material)
    db.flush()
    quiz = GeneratedQuiz(
        material_id=material.material_id,
        player_id=player_id,
        title="Sample Quiz",
        difficulty="mixed",
        language="English",
        generation_mode="extractive-fallback",
        review_status=review_status,
        questions=[
            {
                "question": "2 + 2 = ?",
                "options": ["3", "4", "5", "6"],
                "answer_index": 1,
                "difficulty": "easy",
                "explanation": "Basic arithmetic.",
                "source_excerpt": "n/a",
                "competency": "Arithmetic",
                "bloom_level": "remember",
            }
        ],
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return quiz.quiz_id


# ---------------------------------------------------------------------------
# submit-for-review
# ---------------------------------------------------------------------------


def test_owner_can_submit_a_private_quiz_for_review():
    db = _db()
    player_id = _make_player(db)
    quiz_id = _make_quiz(db, player_id, review_status="private")
    client = TestClient(_app(db, _principal(player_id)))

    response = client.post(f"/learning/quiz/{quiz_id}/submit-for-review", json={"player_id": player_id})

    assert response.status_code == 200
    assert response.json()["review_status"] == "pending_review"
    db.refresh(db.get(GeneratedQuiz, quiz_id))
    assert db.get(GeneratedQuiz, quiz_id).submitted_for_review_at is not None


def test_cannot_submit_someone_elses_quiz_for_review():
    db = _db()
    owner_id = _make_player(db)
    other_id = _make_player(db)
    quiz_id = _make_quiz(db, owner_id, review_status="private")
    client = TestClient(_app(db, _principal(other_id)))

    response = client.post(f"/learning/quiz/{quiz_id}/submit-for-review", json={"player_id": other_id})
    assert response.status_code == 403


def test_cannot_resubmit_an_already_pending_quiz():
    db = _db()
    player_id = _make_player(db)
    quiz_id = _make_quiz(db, player_id, review_status="pending_review")
    client = TestClient(_app(db, _principal(player_id)))

    response = client.post(f"/learning/quiz/{quiz_id}/submit-for-review", json={"player_id": player_id})
    assert response.status_code == 422


def test_a_rejected_quiz_can_be_resubmitted():
    db = _db()
    player_id = _make_player(db)
    quiz_id = _make_quiz(db, player_id, review_status="rejected")
    client = TestClient(_app(db, _principal(player_id)))

    response = client.post(f"/learning/quiz/{quiz_id}/submit-for-review", json={"player_id": player_id})
    assert response.status_code == 200
    assert response.json()["review_status"] == "pending_review"


# ---------------------------------------------------------------------------
# review queue + decision -- RBAC boundary
# ---------------------------------------------------------------------------


def test_a_plain_learner_cannot_reach_the_review_queue_or_decide():
    db = _db()
    player_id = _make_player(db)
    quiz_id = _make_quiz(db, player_id, review_status="pending_review")
    client = TestClient(_app(db, _principal(player_id, roles=("learner",))))

    queue = client.get("/learning/quiz/review/queue")
    decision = client.post(f"/learning/quiz/{quiz_id}/review", json={"decision": "approve"})

    assert queue.status_code == 403
    assert decision.status_code == 403


def test_a_content_reviewer_sees_full_question_content_in_the_queue():
    db = _db()
    player_id = _make_player(db)
    _make_quiz(db, player_id, review_status="pending_review")
    _make_quiz(db, player_id, review_status="private")  # must not appear
    client = TestClient(_app(db, _principal(None, roles=("content_reviewer",))))

    response = client.get("/learning/quiz/review/queue")
    assert response.status_code == 200
    body = response.json()["quizzes"]
    assert len(body) == 1
    assert body[0]["questions"][0]["question"] == "2 + 2 = ?"
    assert body[0]["questions"][0]["answer_index"] == 1


def test_approving_a_quiz_publishes_it_with_reviewer_metadata():
    db = _db()
    player_id = _make_player(db)
    quiz_id = _make_quiz(db, player_id, review_status="pending_review")
    client = TestClient(_app(db, _principal(None, roles=("content_reviewer",))))

    response = client.post(
        f"/learning/quiz/{quiz_id}/review",
        json={"decision": "approve", "notes": "Solid, ship it."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["review_status"] == "published"
    assert body["reviewed_by"] is not None
    assert body["reviewer_notes"] == "Solid, ship it."


def test_rejecting_a_quiz_returns_it_to_the_creator():
    db = _db()
    player_id = _make_player(db)
    quiz_id = _make_quiz(db, player_id, review_status="pending_review")
    client = TestClient(_app(db, _principal(None, roles=("content_reviewer",))))

    response = client.post(f"/learning/quiz/{quiz_id}/review", json={"decision": "reject"})
    assert response.status_code == 200
    assert response.json()["review_status"] == "rejected"


def test_cannot_review_a_quiz_that_isnt_pending():
    db = _db()
    player_id = _make_player(db)
    quiz_id = _make_quiz(db, player_id, review_status="private")
    client = TestClient(_app(db, _principal(None, roles=("content_reviewer",))))

    response = client.post(f"/learning/quiz/{quiz_id}/review", json={"decision": "approve"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# library + non-owner take flow
# ---------------------------------------------------------------------------


def test_library_lists_only_published_quizzes():
    db = _db()
    player_id = _make_player(db)
    _make_quiz(db, player_id, review_status="published")
    _make_quiz(db, player_id, review_status="pending_review")
    _make_quiz(db, player_id, review_status="private")
    client = TestClient(_app(db, _principal(player_id)))

    response = client.get("/learning/quiz/review/library")
    assert response.status_code == 200
    assert len(response.json()["quizzes"]) == 1


def test_a_private_quiz_is_still_invisible_to_a_non_owner():
    db = _db()
    owner_id = _make_player(db)
    other_id = _make_player(db)
    quiz_id = _make_quiz(db, owner_id, review_status="private")
    client = TestClient(_app(db, _principal(other_id)))

    response = client.get(f"/learning/quiz/detail/{quiz_id}", params={"player_id": other_id})
    assert response.status_code == 403


def test_a_published_quiz_is_visible_to_and_takeable_by_a_non_owner():
    db = _db()
    owner_id = _make_player(db)
    taker_id = _make_player(db)
    quiz_id = _make_quiz(db, owner_id, review_status="published")
    client = TestClient(_app(db, _principal(taker_id)))

    detail = client.get(f"/learning/quiz/detail/{quiz_id}", params={"player_id": taker_id})
    assert detail.status_code == 200

    submit = client.post(
        f"/learning/quiz/{quiz_id}/submit",
        json={"player_id": taker_id, "answers": [{"question_index": 0, "selected_index": 1}]},
    )
    assert submit.status_code == 200
    assert submit.json()["correct_count"] == 1

    # The taker's attempt is real and persisted...
    attempts = db.query(GeneratedQuizAttempt).filter_by(player_id=taker_id, quiz_id=quiz_id).all()
    assert len(attempts) == 1
    # ...but never overwrites the ORIGINAL creator's own best_score slot.
    quiz = db.get(GeneratedQuiz, quiz_id)
    assert quiz.best_score is None
    assert quiz.last_attempted_at is None


def test_the_owners_own_attempt_still_updates_best_score_as_before():
    db = _db()
    owner_id = _make_player(db)
    quiz_id = _make_quiz(db, owner_id, review_status="published")
    client = TestClient(_app(db, _principal(owner_id)))

    response = client.post(
        f"/learning/quiz/{quiz_id}/submit",
        json={"player_id": owner_id, "answers": [{"question_index": 0, "selected_index": 1}]},
    )
    assert response.status_code == 200

    quiz = db.get(GeneratedQuiz, quiz_id)
    assert quiz.best_score is not None
    assert quiz.last_attempted_at is not None


def test_attempts_endpoint_is_own_player_scoped():
    db = _db()
    owner_id = _make_player(db)
    taker_id = _make_player(db)
    quiz_id = _make_quiz(db, owner_id, review_status="published")
    taker_client = TestClient(_app(db, _principal(taker_id)))
    taker_client.post(
        f"/learning/quiz/{quiz_id}/submit",
        json={"player_id": taker_id, "answers": [{"question_index": 0, "selected_index": 1}]},
    )

    own_view = taker_client.get(f"/learning/quiz/{quiz_id}/attempts", params={"player_id": taker_id})
    assert own_view.status_code == 200
    assert len(own_view.json()["attempts"]) == 1

    cross_view = taker_client.get(f"/learning/quiz/{quiz_id}/attempts", params={"player_id": owner_id})
    assert cross_view.status_code == 403
