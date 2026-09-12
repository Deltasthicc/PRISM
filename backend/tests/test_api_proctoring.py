"""HTTP contract for real, persisted exam-integrity signal logging
(routes/proctoring.py). Follows test_dsa_sandbox.py's isolated-app +
in-memory-SQLite + require_principal-override pattern, since this route is
owner-scoped (require_own_player) and needs a real bound principal.
"""
from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base, get_db
# See test_dsa_sandbox.py's identical comment: Base.metadata is
# process-global, import the full model set so create_all() is correct
# regardless of what else has already run this session.
from models.player import Player
from models.enums import DEFAULT_LEARNING_MODE  # noqa: F401
from models.accuracy_history import AccuracyHistory  # noqa: F401
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
from models.proctoring import ProctoringEvent
from routes.authorization import require_principal
from routes.proctoring import router as proctoring_router
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
    app.include_router(proctoring_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    if principal is not None:
        app.dependency_overrides[require_principal] = lambda: principal
    return app


def _make_player(db) -> str:
    player_id = str(uuid.uuid4())
    db.add(Player(player_id=player_id, username=f"proctor-{player_id[:8]}"))
    db.commit()
    return player_id


def test_reporting_a_violation_persists_it_and_returns_a_running_count():
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))
    attempt_id = str(uuid.uuid4())

    first = client.post(
        "/learning/proctoring/violations",
        json={"player_id": player_id, "attempt_id": attempt_id, "violation_type": "no_face_detected"},
    )
    second = client.post(
        "/learning/proctoring/violations",
        json={"player_id": player_id, "attempt_id": attempt_id, "violation_type": "phone_detected", "detail": "confidence=0.91"},
    )

    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["attempt_violation_count"] == 1
    assert second.json()["attempt_violation_count"] == 2
    assert second.json()["detail"] == "confidence=0.91"
    assert db.query(ProctoringEvent).filter_by(player_id=player_id).count() == 2


def test_unknown_violation_type_is_rejected():
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))

    response = client.post(
        "/learning/proctoring/violations",
        json={"player_id": player_id, "attempt_id": "attempt-1", "violation_type": "not-a-real-type"},
    )

    assert response.status_code == 422
    assert db.query(ProctoringEvent).count() == 0


def test_violations_are_scoped_per_attempt():
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))

    client.post(
        "/learning/proctoring/violations",
        json={"player_id": player_id, "attempt_id": "attempt-a", "violation_type": "tab_switch"},
    )
    client.post(
        "/learning/proctoring/violations",
        json={"player_id": player_id, "attempt_id": "attempt-b", "violation_type": "tab_switch"},
    )
    client.post(
        "/learning/proctoring/violations",
        json={"player_id": player_id, "attempt_id": "attempt-b", "violation_type": "fullscreen_exit"},
    )

    response = client.get(
        "/learning/proctoring/violations",
        params={"player_id": player_id, "attempt_id": "attempt-b"},
    )
    assert response.status_code == 200
    rows = response.json()["violations"]
    assert len(rows) == 2
    assert {row["violation_type"] for row in rows} == {"tab_switch", "fullscreen_exit"}


def test_cannot_report_or_list_violations_for_another_player():
    db = _db()
    player_id = _make_player(db)
    other_player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))

    report = client.post(
        "/learning/proctoring/violations",
        json={"player_id": other_player_id, "attempt_id": "attempt-1", "violation_type": "tab_switch"},
    )
    listing = client.get(
        "/learning/proctoring/violations",
        params={"player_id": other_player_id, "attempt_id": "attempt-1"},
    )

    assert report.status_code == 403
    assert listing.status_code == 403


def test_unknown_player_is_rejected():
    db = _db()
    client = TestClient(_app(db, _principal("does-not-exist")))

    response = client.post(
        "/learning/proctoring/violations",
        json={"player_id": "does-not-exist", "attempt_id": "attempt-1", "violation_type": "tab_switch"},
    )

    assert response.status_code == 404
