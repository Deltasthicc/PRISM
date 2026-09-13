"""HTTP contract for the real, persisted "QR-code live quiz session"
feature (routes/live_sessions.py, models/live_session.py) -- a trainer hosts
a shared, paced session of an existing GeneratedQuiz, participants join via
a short join_code, and everyone's real weighted score is computed once the
host ends the session.

Follows test_course_enrollment.py's / test_quiz_review.py's isolated-app +
in-memory-SQLite + require_principal-override pattern.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base, get_db
# Base.metadata is process-global -- import the full model set so
# create_all() is correct regardless of what else has already run this
# session (same comment as test_course_enrollment.py / test_quiz_review.py).
from models.player import Player
from models.enums import DEFAULT_LEARNING_MODE  # noqa: F401
from models.accuracy_history import AccuracyHistory  # noqa: F401
from models.question import Question  # noqa: F401
from models.submission import AnswerSubmission  # noqa: F401
from models.guild import Guild  # noqa: F401
from models.dungeon import Dungeon, Room  # noqa: F401
from models.session import GameSession  # noqa: F401
from models.learning import LearnerProfile, CompetencyAssessment, LearningMaterial, GeneratedQuiz, GeneratedQuizAttempt
from models.governance import EvidenceRecord, RoleTarget, SourceVersion, AuditEvent  # noqa: F401
from models.identity import IdentityBinding  # noqa: F401
from models.question_bank import QuestionBankItem, QuestionBankAttempt  # noqa: F401
from models.dsa_submission import DsaSubmission  # noqa: F401
from models.course_enrollment import CourseEnrollment  # noqa: F401
from models.proctoring import ProctoringEvent  # noqa: F401
from models.judgment_scenario import JudgmentScenario, JudgmentScenarioAttempt  # noqa: F401
from models.live_session import LiveQuizSession, LiveSessionParticipant
from routes.authorization import require_principal
from routes.live_sessions import router as live_sessions_router
import routes.live_sessions as live_sessions_module
from security.rbac import BoundPrincipal


class _Subject:
    issuer = "https://issuer.example/realm"
    subject_id = "subject-1"

    def __init__(self, roles):
        self.roles = frozenset(roles)


def _principal(player_id: str | None, roles=("learner", "trainer")) -> BoundPrincipal:
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
    app.include_router(live_sessions_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    if principal is not None:
        app.dependency_overrides[require_principal] = lambda: principal
    return app


def _client_for(db, player_id: str | None, roles=("learner", "trainer")) -> TestClient:
    return TestClient(_app(db, _principal(player_id, roles=roles)))


def _make_player(db, username_prefix="player") -> str:
    player_id = str(uuid.uuid4())
    db.add(Player(player_id=player_id, username=f"{username_prefix}-{player_id[:8]}"))
    db.commit()
    return player_id


def _make_quiz(db, player_id: str, review_status: str = "private", questions=None) -> str:
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
        title="Live Session Quiz",
        difficulty="mixed",
        language="English",
        generation_mode="extractive-fallback",
        review_status=review_status,
        questions=questions
        if questions is not None
        else [
            {
                "question": "2 + 2 = ?",
                "options": ["3", "4", "5", "6"],
                "answer_index": 1,
                "difficulty": "easy",
                "explanation": "Basic arithmetic.",
                "source_excerpt": "n/a",
                "competency": "Arithmetic",
                "bloom_level": "remember",
            },
            {
                "question": "Capital of France?",
                "options": ["Berlin", "Madrid", "Paris", "Rome"],
                "answer_index": 2,
                "difficulty": "medium",
                "explanation": "Geography.",
                "source_excerpt": "n/a",
                "competency": "Geography",
                "bloom_level": "remember",
            },
            {
                "question": "sqrt(144) = ?",
                "options": ["10", "11", "12", "13"],
                "answer_index": 2,
                "difficulty": "hard",
                "explanation": "Arithmetic.",
                "source_excerpt": "n/a",
                "competency": "Arithmetic",
                "bloom_level": "apply",
            },
        ],
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return quiz.quiz_id


def _create_session(db, host_id, quiz_id) -> dict:
    client = _client_for(db, host_id)
    response = client.post("/learning/live-sessions/", json={"host_player_id": host_id, "quiz_id": quiz_id})
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------------------
# join_code generation
# ---------------------------------------------------------------------------


def test_join_code_uses_the_expected_alphabet_and_length():
    db = _db()
    host_id = _make_player(db, "host")
    quiz_id = _make_quiz(db, host_id)

    session = _create_session(db, host_id, quiz_id)
    code = session["join_code"]
    assert len(code) == 6
    assert set(code) <= set("ABCDEFGHJKLMNPQRSTUVWXYZ23456789")


def test_two_sessions_never_share_a_join_code():
    db = _db()
    host_id = _make_player(db, "host")
    quiz_id = _make_quiz(db, host_id)

    codes = {_create_session(db, host_id, quiz_id)["join_code"] for _ in range(25)}
    assert len(codes) == 25


def test_join_code_generation_retries_past_a_forced_collision(monkeypatch):
    db = _db()
    host_id = _make_player(db, "host")
    quiz_id = _make_quiz(db, host_id)

    first = _create_session(db, host_id, quiz_id)
    taken_code = first["join_code"]

    # Force the very next draw to collide with the already-taken code, then
    # succeed on the second draw -- proves the retry loop actually re-checks
    # the database rather than trusting the first random draw blindly.
    draws = iter([taken_code, "ZZZZZZ" if taken_code != "ZZZZZZ" else "YYYYYY"])
    monkeypatch.setattr(live_sessions_module, "_random_join_code", lambda: next(draws))

    second = _create_session(db, host_id, quiz_id)
    assert second["join_code"] != taken_code
    assert db.query(LiveQuizSession).count() == 2


# ---------------------------------------------------------------------------
# create + visibility
# ---------------------------------------------------------------------------


def test_host_can_create_a_session_from_their_own_private_quiz():
    db = _db()
    host_id = _make_player(db, "host")
    quiz_id = _make_quiz(db, host_id, review_status="private")

    session = _create_session(db, host_id, quiz_id)
    assert session["status"] == "waiting"
    assert session["current_question_index"] == 0
    assert session["question_count"] == 3


def test_cannot_create_a_session_from_someone_elses_private_quiz():
    db = _db()
    owner_id = _make_player(db, "owner")
    other_id = _make_player(db, "other")
    quiz_id = _make_quiz(db, owner_id, review_status="private")

    client = _client_for(db, other_id)
    response = client.post("/learning/live-sessions/", json={"host_player_id": other_id, "quiz_id": quiz_id})
    assert response.status_code == 403


def test_anyone_can_create_a_session_from_a_published_quiz():
    db = _db()
    owner_id = _make_player(db, "owner")
    other_id = _make_player(db, "other")
    quiz_id = _make_quiz(db, owner_id, review_status="published")

    session = _create_session(db, other_id, quiz_id)
    assert session["host_player_id"] == other_id


# ---------------------------------------------------------------------------
# by-code resolution + join
# ---------------------------------------------------------------------------


def test_by_code_resolves_without_requiring_the_host_identity():
    db = _db()
    host_id = _make_player(db, "host")
    participant_id = _make_player(db, "participant")
    quiz_id = _make_quiz(db, host_id)
    session = _create_session(db, host_id, quiz_id)

    # A different principal than the host -- proves this really is reachable
    # by a participant who has no idea who the host is.
    client = _client_for(db, participant_id)
    response = client.get(f"/learning/live-sessions/by-code/{session['join_code']}")
    assert response.status_code == 200
    assert response.json()["session_id"] == session["session_id"]


def test_by_code_is_case_insensitive():
    db = _db()
    host_id = _make_player(db, "host")
    quiz_id = _make_quiz(db, host_id)
    session = _create_session(db, host_id, quiz_id)

    client = _client_for(db, host_id)
    response = client.get(f"/learning/live-sessions/by-code/{session['join_code'].lower()}")
    assert response.status_code == 200


def test_joining_twice_does_not_duplicate_a_participant_row():
    db = _db()
    host_id = _make_player(db, "host")
    participant_id = _make_player(db, "participant")
    quiz_id = _make_quiz(db, host_id)
    session = _create_session(db, host_id, quiz_id)
    session_id = session["session_id"]

    client = _client_for(db, participant_id)
    first = client.post(f"/learning/live-sessions/{session_id}/join", json={"player_id": participant_id})
    second = client.post(f"/learning/live-sessions/{session_id}/join", json={"player_id": participant_id})

    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["participant_id"] == second.json()["participant_id"]
    assert (
        db.query(LiveSessionParticipant)
        .filter_by(session_id=session_id, player_id=participant_id)
        .count()
        == 1
    )


def test_cannot_join_an_ended_session():
    db = _db()
    host_id = _make_player(db, "host")
    participant_id = _make_player(db, "participant")
    quiz_id = _make_quiz(db, host_id)
    session = _create_session(db, host_id, quiz_id)
    session_id = session["session_id"]

    host_client = _client_for(db, host_id)
    host_client.post(f"/learning/live-sessions/{session_id}/start")
    host_client.post(f"/learning/live-sessions/{session_id}/end")

    participant_client = _client_for(db, participant_id)
    response = participant_client.post(
        f"/learning/live-sessions/{session_id}/join", json={"player_id": participant_id}
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# host-only RBAC boundary
# ---------------------------------------------------------------------------


def test_non_host_cannot_start_advance_or_end_the_session():
    db = _db()
    host_id = _make_player(db, "host")
    intruder_id = _make_player(db, "intruder")
    quiz_id = _make_quiz(db, host_id)
    session = _create_session(db, host_id, quiz_id)
    session_id = session["session_id"]

    intruder_client = _client_for(db, intruder_id)
    start = intruder_client.post(f"/learning/live-sessions/{session_id}/start")
    advance = intruder_client.post(f"/learning/live-sessions/{session_id}/advance")
    end = intruder_client.post(f"/learning/live-sessions/{session_id}/end")

    assert start.status_code == 403
    assert advance.status_code == 403
    assert end.status_code == 403
    db.refresh(db.get(LiveQuizSession, session_id))
    assert db.get(LiveQuizSession, session_id).status == "waiting"


def test_cannot_start_a_session_that_is_not_waiting():
    db = _db()
    host_id = _make_player(db, "host")
    quiz_id = _make_quiz(db, host_id)
    session = _create_session(db, host_id, quiz_id)
    session_id = session["session_id"]
    host_client = _client_for(db, host_id)
    host_client.post(f"/learning/live-sessions/{session_id}/start")

    response = host_client.post(f"/learning/live-sessions/{session_id}/start")
    assert response.status_code == 422


def test_cannot_advance_past_the_last_question():
    db = _db()
    host_id = _make_player(db, "host")
    quiz_id = _make_quiz(db, host_id)  # 3 questions -> indices 0, 1, 2
    session = _create_session(db, host_id, quiz_id)
    session_id = session["session_id"]
    host_client = _client_for(db, host_id)
    host_client.post(f"/learning/live-sessions/{session_id}/start")

    first_advance = host_client.post(f"/learning/live-sessions/{session_id}/advance")
    second_advance = host_client.post(f"/learning/live-sessions/{session_id}/advance")
    third_advance = host_client.post(f"/learning/live-sessions/{session_id}/advance")

    assert first_advance.status_code == 200 and first_advance.json()["current_question_index"] == 1
    assert second_advance.status_code == 200 and second_advance.json()["current_question_index"] == 2
    assert third_advance.status_code == 422  # already on the last question (index 2 of 3)


# ---------------------------------------------------------------------------
# stale-answer rejection
# ---------------------------------------------------------------------------


def test_participant_cannot_answer_a_question_the_host_has_moved_past():
    db = _db()
    host_id = _make_player(db, "host")
    participant_id = _make_player(db, "participant")
    quiz_id = _make_quiz(db, host_id)
    session = _create_session(db, host_id, quiz_id)
    session_id = session["session_id"]

    host_client = _client_for(db, host_id)
    participant_client = _client_for(db, participant_id)
    participant_client.post(f"/learning/live-sessions/{session_id}/join", json={"player_id": participant_id})
    host_client.post(f"/learning/live-sessions/{session_id}/start")
    host_client.post(f"/learning/live-sessions/{session_id}/advance")  # now on question index 1

    stale_answer = participant_client.post(
        f"/learning/live-sessions/{session_id}/answer",
        json={"player_id": participant_id, "question_index": 0, "selected_index": 1},
    )
    assert stale_answer.status_code == 422

    current_answer = participant_client.post(
        f"/learning/live-sessions/{session_id}/answer",
        json={"player_id": participant_id, "question_index": 1, "selected_index": 2},
    )
    assert current_answer.status_code == 200


def test_cannot_answer_before_the_session_is_active():
    db = _db()
    host_id = _make_player(db, "host")
    participant_id = _make_player(db, "participant")
    quiz_id = _make_quiz(db, host_id)
    session = _create_session(db, host_id, quiz_id)
    session_id = session["session_id"]

    participant_client = _client_for(db, participant_id)
    participant_client.post(f"/learning/live-sessions/{session_id}/join", json={"player_id": participant_id})
    response = participant_client.post(
        f"/learning/live-sessions/{session_id}/answer",
        json={"player_id": participant_id, "question_index": 0, "selected_index": 1},
    )
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# end -> real weighted scoring + GeneratedQuizAttempt
# ---------------------------------------------------------------------------


def test_ending_a_session_computes_the_exact_expected_weighted_score():
    # Weights: easy=1.0, medium=1.5, hard=2.0 (services/quiz_scoring.py).
    # Alice answers all three correctly -> weighted_possible == weighted_earned
    # (time_factor is neutral 1.0 for every live-session answer) -> 100.0.
    # Bob answers only the easy question (index 0) correctly ->
    # weighted_earned = 1.0, weighted_possible = 1.0 + 1.5 + 2.0 = 4.5 ->
    # round(1.0 / 4.5 * 100, 1) == 22.2.
    db = _db()
    host_id = _make_player(db, "host")
    alice_id = _make_player(db, "alice")
    bob_id = _make_player(db, "bob")
    quiz_id = _make_quiz(db, host_id)
    session = _create_session(db, host_id, quiz_id)
    session_id = session["session_id"]

    host_client = _client_for(db, host_id)
    alice_client = _client_for(db, alice_id)
    bob_client = _client_for(db, bob_id)
    alice_client.post(f"/learning/live-sessions/{session_id}/join", json={"player_id": alice_id})
    bob_client.post(f"/learning/live-sessions/{session_id}/join", json={"player_id": bob_id})
    host_client.post(f"/learning/live-sessions/{session_id}/start")

    # Question 0 (easy, answer_index=1)
    alice_client.post(
        f"/learning/live-sessions/{session_id}/answer",
        json={"player_id": alice_id, "question_index": 0, "selected_index": 1},
    )
    bob_client.post(
        f"/learning/live-sessions/{session_id}/answer",
        json={"player_id": bob_id, "question_index": 0, "selected_index": 1},
    )
    host_client.post(f"/learning/live-sessions/{session_id}/advance")

    # Question 1 (medium, answer_index=2) -- Bob answers wrong
    alice_client.post(
        f"/learning/live-sessions/{session_id}/answer",
        json={"player_id": alice_id, "question_index": 1, "selected_index": 2},
    )
    bob_client.post(
        f"/learning/live-sessions/{session_id}/answer",
        json={"player_id": bob_id, "question_index": 1, "selected_index": 0},
    )
    host_client.post(f"/learning/live-sessions/{session_id}/advance")

    # Question 2 (hard, answer_index=2) -- Bob doesn't answer at all
    alice_client.post(
        f"/learning/live-sessions/{session_id}/answer",
        json={"player_id": alice_id, "question_index": 2, "selected_index": 2},
    )

    end_response = host_client.post(f"/learning/live-sessions/{session_id}/end")
    assert end_response.status_code == 200
    assert end_response.json()["status"] == "ended"

    alice = db.query(LiveSessionParticipant).filter_by(session_id=session_id, player_id=alice_id).first()
    bob = db.query(LiveSessionParticipant).filter_by(session_id=session_id, player_id=bob_id).first()
    assert alice.score == 100.0
    assert bob.score == pytest.approx(22.2)

    # A real GeneratedQuizAttempt row per participant, integrating with the
    # existing attempt history rather than duplicating it.
    attempts = db.query(GeneratedQuizAttempt).filter_by(quiz_id=quiz_id).all()
    assert len(attempts) == 2
    attempts_by_player = {row.player_id: row for row in attempts}
    assert attempts_by_player[alice_id].weighted_score == 100.0
    assert attempts_by_player[alice_id].correct_count == 3
    assert attempts_by_player[alice_id].total_questions == 3
    assert attempts_by_player[bob_id].weighted_score == pytest.approx(22.2)
    assert attempts_by_player[bob_id].correct_count == 1


def test_ending_an_already_ended_session_is_rejected():
    db = _db()
    host_id = _make_player(db, "host")
    quiz_id = _make_quiz(db, host_id)
    session = _create_session(db, host_id, quiz_id)
    session_id = session["session_id"]
    host_client = _client_for(db, host_id)
    host_client.post(f"/learning/live-sessions/{session_id}/start")
    host_client.post(f"/learning/live-sessions/{session_id}/end")

    response = host_client.post(f"/learning/live-sessions/{session_id}/end")
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# state polling + results
# ---------------------------------------------------------------------------


def test_host_view_includes_every_participants_live_progress():
    db = _db()
    host_id = _make_player(db, "host")
    participant_id = _make_player(db, "participant")
    quiz_id = _make_quiz(db, host_id)
    session = _create_session(db, host_id, quiz_id)
    session_id = session["session_id"]

    participant_client = _client_for(db, participant_id)
    participant_client.post(f"/learning/live-sessions/{session_id}/join", json={"player_id": participant_id})
    host_client = _client_for(db, host_id)
    host_client.post(f"/learning/live-sessions/{session_id}/start")
    participant_client.post(
        f"/learning/live-sessions/{session_id}/answer",
        json={"player_id": participant_id, "question_index": 0, "selected_index": 1},
    )

    state = host_client.get(f"/learning/live-sessions/{session_id}", params={"player_id": host_id})
    assert state.status_code == 200
    body = state.json()
    assert len(body["participants"]) == 1
    assert body["participants"][0]["answered_count"] == 1


def test_a_stranger_cannot_read_session_state():
    db = _db()
    host_id = _make_player(db, "host")
    stranger_id = _make_player(db, "stranger")
    quiz_id = _make_quiz(db, host_id)
    session = _create_session(db, host_id, quiz_id)
    session_id = session["session_id"]

    stranger_client = _client_for(db, stranger_id)
    response = stranger_client.get(f"/learning/live-sessions/{session_id}", params={"player_id": stranger_id})
    assert response.status_code == 403


def test_results_are_unavailable_until_the_session_has_ended():
    db = _db()
    host_id = _make_player(db, "host")
    quiz_id = _make_quiz(db, host_id)
    session = _create_session(db, host_id, quiz_id)
    session_id = session["session_id"]
    host_client = _client_for(db, host_id)

    response = host_client.get(f"/learning/live-sessions/{session_id}/results", params={"player_id": host_id})
    assert response.status_code == 422


def test_results_leaderboard_is_sorted_descending_by_score():
    db = _db()
    host_id = _make_player(db, "host")
    alice_id = _make_player(db, "alice")
    bob_id = _make_player(db, "bob")
    quiz_id = _make_quiz(db, host_id)
    session = _create_session(db, host_id, quiz_id)
    session_id = session["session_id"]

    alice_client = _client_for(db, alice_id)
    bob_client = _client_for(db, bob_id)
    alice_client.post(f"/learning/live-sessions/{session_id}/join", json={"player_id": alice_id})
    bob_client.post(f"/learning/live-sessions/{session_id}/join", json={"player_id": bob_id})
    host_client = _client_for(db, host_id)
    host_client.post(f"/learning/live-sessions/{session_id}/start")

    # Alice gets question 0 right, Bob gets it wrong.
    alice_client.post(
        f"/learning/live-sessions/{session_id}/answer",
        json={"player_id": alice_id, "question_index": 0, "selected_index": 1},
    )
    bob_client.post(
        f"/learning/live-sessions/{session_id}/answer",
        json={"player_id": bob_id, "question_index": 0, "selected_index": 0},
    )
    host_client.post(f"/learning/live-sessions/{session_id}/end")

    results = host_client.get(f"/learning/live-sessions/{session_id}/results", params={"player_id": host_id})
    assert results.status_code == 200
    leaderboard = results.json()["leaderboard"]
    assert leaderboard[0]["player_id"] == alice_id
    assert leaderboard[0]["score"] > leaderboard[1]["score"]


# ---------------------------------------------------------------------------
# current_question answer-reveal boundary
# ---------------------------------------------------------------------------


def test_participant_does_not_see_the_answer_before_answering():
    db = _db()
    host_id = _make_player(db, "host")
    participant_id = _make_player(db, "participant")
    quiz_id = _make_quiz(db, host_id)
    session = _create_session(db, host_id, quiz_id)
    session_id = session["session_id"]

    participant_client = _client_for(db, participant_id)
    participant_client.post(f"/learning/live-sessions/{session_id}/join", json={"player_id": participant_id})
    host_client = _client_for(db, host_id)
    host_client.post(f"/learning/live-sessions/{session_id}/start")

    state = participant_client.get(
        f"/learning/live-sessions/{session_id}", params={"player_id": participant_id}
    )
    assert state.status_code == 200
    current_question = state.json()["current_question"]
    assert current_question["question"] == "2 + 2 = ?"
    assert "answer_index" not in current_question
    assert "explanation" not in current_question


def test_participant_sees_the_answer_only_after_answering():
    db = _db()
    host_id = _make_player(db, "host")
    participant_id = _make_player(db, "participant")
    quiz_id = _make_quiz(db, host_id)
    session = _create_session(db, host_id, quiz_id)
    session_id = session["session_id"]

    participant_client = _client_for(db, participant_id)
    participant_client.post(f"/learning/live-sessions/{session_id}/join", json={"player_id": participant_id})
    host_client = _client_for(db, host_id)
    host_client.post(f"/learning/live-sessions/{session_id}/start")
    participant_client.post(
        f"/learning/live-sessions/{session_id}/answer",
        json={"player_id": participant_id, "question_index": 0, "selected_index": 1},
    )

    state = participant_client.get(
        f"/learning/live-sessions/{session_id}", params={"player_id": participant_id}
    )
    assert state.json()["current_question"]["answer_index"] == 1


def test_host_always_sees_the_answer():
    db = _db()
    host_id = _make_player(db, "host")
    quiz_id = _make_quiz(db, host_id)
    session = _create_session(db, host_id, quiz_id)
    session_id = session["session_id"]
    host_client = _client_for(db, host_id)
    host_client.post(f"/learning/live-sessions/{session_id}/start")

    state = host_client.get(f"/learning/live-sessions/{session_id}", params={"player_id": host_id})
    assert state.json()["current_question"]["answer_index"] == 1
