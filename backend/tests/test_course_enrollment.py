"""HTTP contract for the real enroll/complete lifecycle
(routes/course_enrollment.py) built on top of
services/learning_catalog.py::recommend_courses()' output, which was
computed correctly but had no route and no frontend page before this.

Follows test_dsa_sandbox.py's isolated-app + in-memory-SQLite +
require_principal-override pattern, since this route is owner-scoped
(require_own_player) and needs a real bound principal.
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
from models.governance import EvidenceRecord, RoleTarget, SourceVersion, AuditEvent
from models.identity import IdentityBinding  # noqa: F401
from models.question_bank import QuestionBankItem, QuestionBankAttempt  # noqa: F401
from models.dsa_submission import DsaSubmission  # noqa: F401
from models.course_enrollment import CourseEnrollment
from routes.authorization import require_principal
from routes.course_enrollment import router as course_enrollment_router
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
    app.include_router(course_enrollment_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    if principal is not None:
        app.dependency_overrides[require_principal] = lambda: principal
    return app


def _make_player(db) -> str:
    player_id = str(uuid.uuid4())
    db.add(Player(player_id=player_id, username=f"enroll-{player_id[:8]}"))
    db.commit()
    return player_id


def test_enroll_in_an_igot_course_is_accepted_and_persisted():
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))

    response = client.post(
        "/learning/catalogue/enroll",
        json={"player_id": player_id, "course_id": "igot::os_sampling_design", "title": "Sampling Design 101"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "enrolled"
    assert body["provider"] == "igot"
    assert body["competency_id"] == "os_sampling_design"
    assert db.query(CourseEnrollment).filter_by(player_id=player_id).count() == 1


def test_enrolling_twice_in_the_same_course_is_idempotent():
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))
    payload = {"player_id": player_id, "course_id": "nssta::os_price_statistics", "title": "Price Stats TPAC"}

    first = client.post("/learning/catalogue/enroll", json=payload)
    second = client.post("/learning/catalogue/enroll", json=payload)

    assert first.status_code == 200 and second.status_code == 200
    assert first.json()["enrollment_id"] == second.json()["enrollment_id"]
    assert db.query(CourseEnrollment).filter_by(player_id=player_id).count() == 1


def test_internal_practice_course_id_is_rejected_not_enrolled():
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))

    response = client.post(
        "/learning/catalogue/enroll",
        json={"player_id": player_id, "course_id": "practice::arrays", "title": "Practice: Arrays"},
    )

    assert response.status_code == 422


def test_completing_an_enrollment_writes_unscored_provider_evidence():
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))

    enrolled = client.post(
        "/learning/catalogue/enroll",
        json={"player_id": player_id, "course_id": "igot::os_gis", "title": "GIS for Officials"},
    ).json()

    response = client.post(
        f"/learning/catalogue/enrollments/{enrolled['enrollment_id']}/complete",
        json={"player_id": player_id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["completed_at"] is not None

    records = db.query(EvidenceRecord).filter_by(player_id=player_id).all()
    assert len(records) == 1
    assert records[0].evidence_type == "provider_imported"
    assert records[0].competency_id == "os_gis"
    assert records[0].detail == "igot:igot::os_gis"


def test_completing_twice_does_not_double_write_evidence():
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))

    enrolled = client.post(
        "/learning/catalogue/enroll",
        json={"player_id": player_id, "course_id": "igot::os_gis", "title": "GIS for Officials"},
    ).json()
    complete_url = f"/learning/catalogue/enrollments/{enrolled['enrollment_id']}/complete"
    client.post(complete_url, json={"player_id": player_id})
    client.post(complete_url, json={"player_id": player_id})

    assert db.query(EvidenceRecord).filter_by(player_id=player_id).count() == 1


def test_cannot_complete_someone_elses_enrollment():
    db = _db()
    player_id = _make_player(db)
    other_player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))

    enrolled = client.post(
        "/learning/catalogue/enroll",
        json={"player_id": player_id, "course_id": "igot::os_gis", "title": "GIS for Officials"},
    ).json()

    other_client = TestClient(_app(db, _principal(other_player_id)))
    response = other_client.post(
        f"/learning/catalogue/enrollments/{enrolled['enrollment_id']}/complete",
        json={"player_id": other_player_id},
    )
    assert response.status_code == 404


def test_list_enrollments_returns_only_that_players_rows():
    db = _db()
    player_id = _make_player(db)
    other_player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id)))
    other_client = TestClient(_app(db, _principal(other_player_id)))

    client.post(
        "/learning/catalogue/enroll",
        json={"player_id": player_id, "course_id": "igot::os_gis", "title": "GIS for Officials"},
    )
    other_client.post(
        "/learning/catalogue/enroll",
        json={"player_id": other_player_id, "course_id": "nssta::os_ml", "title": "ML for Officials"},
    )

    response = client.get("/learning/catalogue/enrollments", params={"player_id": player_id})
    assert response.status_code == 200
    rows = response.json()["enrollments"]
    assert len(rows) == 1
    assert rows[0]["course_id"] == "igot::os_gis"
