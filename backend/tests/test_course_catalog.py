"""HTTP contract for the trainer-authored course catalog
(routes/course_catalog.py) and its integration with the pre-existing
enroll/complete lifecycle (routes/course_enrollment.py) via the new
"internal::" provider prefix.

Follows test_course_enrollment.py's isolated-app + in-memory-SQLite +
require_principal-override pattern exactly.
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
from models.learning import LearnerProfile, CompetencyAssessment, LearningMaterial, GeneratedQuiz  # noqa: F401
from models.governance import EvidenceRecord, RoleTarget, SourceVersion, AuditEvent
from models.identity import IdentityBinding  # noqa: F401
from models.question_bank import QuestionBankItem, QuestionBankAttempt  # noqa: F401
from models.dsa_submission import DsaSubmission  # noqa: F401
from models.course import Course
from models.course_enrollment import CourseEnrollment
from routes.authorization import require_principal
from routes.course_catalog import router as course_catalog_router
from routes.course_enrollment import router as course_enrollment_router
from security.rbac import BoundPrincipal


class _Subject:
    def __init__(self, subject_id: str, roles: frozenset[str]):
        self.issuer = "https://issuer.example/realm"
        self.subject_id = subject_id
        self.roles = roles


def _principal(player_id: str | None, roles: frozenset[str]) -> BoundPrincipal:
    return BoundPrincipal(
        subject=_Subject(player_id or "no-player", roles),
        binding_id="binding-1",
        player_id=player_id,
        roles=roles,
    )


def _db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _app(db, principal: BoundPrincipal | None) -> FastAPI:
    app = FastAPI()
    app.include_router(course_catalog_router)
    app.include_router(course_enrollment_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    if principal is not None:
        app.dependency_overrides[require_principal] = lambda: principal
    return app


def _make_player(db, *, username_prefix: str = "player") -> str:
    player_id = str(uuid.uuid4())
    db.add(Player(player_id=player_id, username=f"{username_prefix}-{player_id[:8]}"))
    db.commit()
    return player_id


def test_trainer_creates_a_draft_course_not_visible_to_public_browse():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    client = TestClient(_app(db, _principal(trainer_id, frozenset({"trainer"}))))

    created = client.post(
        "/learning/courses",
        json={
            "trainer_id": trainer_id,
            "title": "Coastal Hazard Basics",
            "description": "Intro",
            "competency_id": "hazard_basics",
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["is_published"] is False
    assert body["trainer_id"] == trainer_id

    published_list = client.get("/learning/courses")
    assert published_list.status_code == 200
    assert published_list.json() == []


def test_publishing_makes_a_course_visible_to_public_browse():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    client = TestClient(_app(db, _principal(trainer_id, frozenset({"trainer"}))))

    course_id = client.post(
        "/learning/courses",
        json={
            "trainer_id": trainer_id,
            "title": "Weather Station Maintenance",
            "description": "",
            "competency_id": "aws_maintenance",
        },
    ).json()["course_id"]

    publish = client.post(f"/learning/courses/{course_id}/publish", json={"trainer_id": trainer_id})
    assert publish.status_code == 200
    assert publish.json()["is_published"] is True

    published_list = client.get("/learning/courses")
    assert [row["course_id"] for row in published_list.json()] == [course_id]

    single = client.get(f"/learning/courses/{course_id}")
    assert single.status_code == 200


def test_a_trainer_cannot_publish_another_trainers_course():
    db = _db()
    owner_id = _make_player(db, username_prefix="owner")
    other_id = _make_player(db, username_prefix="other")

    owner_client = TestClient(_app(db, _principal(owner_id, frozenset({"trainer"}))))
    course_id = owner_client.post(
        "/learning/courses",
        json={
            "trainer_id": owner_id,
            "title": "Cyclone Response",
            "description": "",
            "competency_id": "cyclone_response",
        },
    ).json()["course_id"]

    other_client = TestClient(_app(db, _principal(other_id, frozenset({"trainer"}))))
    response = other_client.post(f"/learning/courses/{course_id}/publish", json={"trainer_id": other_id})
    assert response.status_code == 404


def test_a_trainer_cannot_publish_impersonating_a_different_trainer_id():
    db = _db()
    owner_id = _make_player(db, username_prefix="owner")
    other_id = _make_player(db, username_prefix="other")
    owner_client = TestClient(_app(db, _principal(owner_id, frozenset({"trainer"}))))
    course_id = owner_client.post(
        "/learning/courses",
        json={"trainer_id": owner_id, "title": "Impersonation Test", "description": "", "competency_id": "x"},
    ).json()["course_id"]

    other_client = TestClient(_app(db, _principal(other_id, frozenset({"trainer"}))))
    # other_id tries to publish by claiming to be owner_id in the body --
    # require_own_player must reject this using the bound principal, never
    # trusting the client-supplied trainer_id alone.
    response = other_client.post(f"/learning/courses/{course_id}/publish", json={"trainer_id": owner_id})
    assert response.status_code == 403


def test_learner_role_cannot_create_a_course():
    db = _db()
    learner_id = _make_player(db)
    client = TestClient(_app(db, _principal(learner_id, frozenset({"learner"}))))

    response = client.post(
        "/learning/courses",
        json={"trainer_id": learner_id, "title": "Should Fail", "description": "", "competency_id": "x"},
    )
    assert response.status_code == 403


def test_learner_can_browse_published_courses():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    trainer_client = TestClient(_app(db, _principal(trainer_id, frozenset({"trainer"}))))
    course_id = trainer_client.post(
        "/learning/courses",
        json={"trainer_id": trainer_id, "title": "Ocean Data Basics", "description": "", "competency_id": "ocean_data"},
    ).json()["course_id"]
    trainer_client.post(f"/learning/courses/{course_id}/publish", json={"trainer_id": trainer_id})

    learner_id = _make_player(db)
    learner_client = TestClient(_app(db, _principal(learner_id, frozenset({"learner"}))))
    response = learner_client.get("/learning/courses")
    assert response.status_code == 200
    assert [row["course_id"] for row in response.json()] == [course_id]


def test_unpublishing_removes_a_course_from_public_browse():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    client = TestClient(_app(db, _principal(trainer_id, frozenset({"trainer"}))))
    course_id = client.post(
        "/learning/courses",
        json={"trainer_id": trainer_id, "title": "Draft Again", "description": "", "competency_id": "x"},
    ).json()["course_id"]
    client.post(f"/learning/courses/{course_id}/publish", json={"trainer_id": trainer_id})
    client.post(f"/learning/courses/{course_id}/unpublish", json={"trainer_id": trainer_id})

    assert client.get("/learning/courses").json() == []
    assert client.get(f"/learning/courses/{course_id}").status_code == 404


def test_enrolling_in_a_published_internal_course_uses_its_real_title_and_competency():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    trainer_client = TestClient(_app(db, _principal(trainer_id, frozenset({"trainer"}))))
    course_id = trainer_client.post(
        "/learning/courses",
        json={
            "trainer_id": trainer_id,
            "title": "Monsoon Forecasting 101",
            "description": "",
            "competency_id": "monsoon_forecasting",
        },
    ).json()["course_id"]
    trainer_client.post(f"/learning/courses/{course_id}/publish", json={"trainer_id": trainer_id})

    learner_id = _make_player(db)
    learner_client = TestClient(_app(db, _principal(learner_id, frozenset({"learner"}))))
    response = learner_client.post(
        "/learning/catalogue/enroll",
        json={"player_id": learner_id, "course_id": f"internal::{course_id}", "title": "ignored"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider"] == "internal"
    assert body["title"] == "Monsoon Forecasting 101"
    assert body["competency_id"] == "monsoon_forecasting"


def test_enrolling_in_an_unpublished_internal_course_is_not_found():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    trainer_client = TestClient(_app(db, _principal(trainer_id, frozenset({"trainer"}))))
    course_id = trainer_client.post(
        "/learning/courses",
        json={"trainer_id": trainer_id, "title": "Still Draft", "description": "", "competency_id": "x"},
    ).json()["course_id"]

    learner_id = _make_player(db)
    learner_client = TestClient(_app(db, _principal(learner_id, frozenset({"learner"}))))
    response = learner_client.post(
        "/learning/catalogue/enroll",
        json={"player_id": learner_id, "course_id": f"internal::{course_id}", "title": "ignored"},
    )
    assert response.status_code == 404


def test_completing_an_internal_enrollment_writes_unscored_evidence_without_a_provider_call():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    trainer_client = TestClient(_app(db, _principal(trainer_id, frozenset({"trainer"}))))
    course_id = trainer_client.post(
        "/learning/courses",
        json={
            "trainer_id": trainer_id,
            "title": "Tsunami Drill Design",
            "description": "",
            "competency_id": "tsunami_drills",
        },
    ).json()["course_id"]
    trainer_client.post(f"/learning/courses/{course_id}/publish", json={"trainer_id": trainer_id})

    learner_id = _make_player(db)
    learner_client = TestClient(_app(db, _principal(learner_id, frozenset({"learner"}))))
    enrollment_id = learner_client.post(
        "/learning/catalogue/enroll",
        json={"player_id": learner_id, "course_id": f"internal::{course_id}", "title": "ignored"},
    ).json()["enrollment_id"]

    response = learner_client.post(
        f"/learning/catalogue/enrollments/{enrollment_id}/complete",
        json={"player_id": learner_id},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "completed"

    evidence = (
        db.query(EvidenceRecord)
        .filter(EvidenceRecord.player_id == learner_id, EvidenceRecord.competency_id == "tsunami_drills")
        .one()
    )
    assert evidence.evidence_type == "provider_imported"
    assert evidence.detail == f"internal:internal::{course_id}"


def test_trainer_lists_only_their_own_courses_draft_and_published():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    other_id = _make_player(db, username_prefix="other")
    client = TestClient(_app(db, _principal(trainer_id, frozenset({"trainer"}))))
    other_client = TestClient(_app(db, _principal(other_id, frozenset({"trainer"}))))

    client.post(
        "/learning/courses",
        json={"trainer_id": trainer_id, "title": "Mine, Draft", "description": "", "competency_id": "x"},
    )
    published_id = client.post(
        "/learning/courses",
        json={"trainer_id": trainer_id, "title": "Mine, Published", "description": "", "competency_id": "x"},
    ).json()["course_id"]
    client.post(f"/learning/courses/{published_id}/publish", json={"trainer_id": trainer_id})
    other_client.post(
        "/learning/courses",
        json={"trainer_id": other_id, "title": "Not Mine", "description": "", "competency_id": "x"},
    )

    response = client.get("/learning/courses/mine", params={"trainer_id": trainer_id})
    assert response.status_code == 200
    titles = {row["title"] for row in response.json()}
    assert titles == {"Mine, Draft", "Mine, Published"}


def test_a_trainer_cannot_list_courses_under_someone_elses_trainer_id():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    other_id = _make_player(db, username_prefix="other")
    other_client = TestClient(_app(db, _principal(other_id, frozenset({"trainer"}))))

    response = other_client.get("/learning/courses/mine", params={"trainer_id": trainer_id})
    assert response.status_code == 403
