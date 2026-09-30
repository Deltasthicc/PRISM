"""HTTP contract for certificate issuance (routes/course_enrollment.py's
complete() side effect + routes/certificates.py) and course feedback
(routes/course_feedback.py). Follows test_course_catalog.py's isolated-app
+ in-memory-SQLite + require_principal-override pattern.
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
from models.certificate import Certificate
from models.feedback import CourseFeedback
from routes.authorization import require_principal
from routes.course_catalog import router as course_catalog_router
from routes.course_enrollment import router as course_enrollment_router
from routes.course_feedback import router as course_feedback_router
from routes.certificates import router as certificates_router
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
    app.include_router(course_feedback_router)
    app.include_router(certificates_router)

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


def _publish_course(db, trainer_id: str, title: str, competency_id: str) -> str:
    client = TestClient(_app(db, _principal(trainer_id, frozenset({"trainer"}))))
    course_id = client.post(
        "/learning/courses",
        json={"trainer_id": trainer_id, "title": title, "description": "", "competency_id": competency_id},
    ).json()["course_id"]
    client.post(f"/learning/courses/{course_id}/publish", json={"trainer_id": trainer_id})
    return course_id


def _enroll_and_complete(db, learner_id: str, course_id: str) -> str:
    client = TestClient(_app(db, _principal(learner_id, frozenset({"learner"}))))
    enrollment = client.post(
        "/learning/catalogue/enroll",
        json={"player_id": learner_id, "course_id": f"internal::{course_id}", "title": "ignored"},
    ).json()
    client.post(
        f"/learning/catalogue/enrollments/{enrollment['enrollment_id']}/complete",
        json={"player_id": learner_id},
    )
    return enrollment["enrollment_id"]


# ---------- Certificates ----------


def test_completing_an_internal_course_issues_a_certificate():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    course_id = _publish_course(db, trainer_id, "Cyclone Response Basics", "cyclone_response")
    learner_id = _make_player(db)
    _enroll_and_complete(db, learner_id, course_id)

    client = TestClient(_app(db, _principal(learner_id, frozenset({"learner"}))))
    response = client.get("/learning/certificates", params={"player_id": learner_id})
    assert response.status_code == 200
    certs = response.json()
    assert len(certs) == 1
    assert certs[0]["title"] == "Cyclone Response Basics"
    assert certs[0]["course_id"] == course_id
    assert certs[0]["revoked"] is False


def test_completing_twice_does_not_issue_a_second_certificate():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    course_id = _publish_course(db, trainer_id, "Repeatable", "x")
    learner_id = _make_player(db)
    enrollment_id = _enroll_and_complete(db, learner_id, course_id)

    client = TestClient(_app(db, _principal(learner_id, frozenset({"learner"}))))
    client.post(
        f"/learning/catalogue/enrollments/{enrollment_id}/complete", json={"player_id": learner_id}
    )
    assert db.query(Certificate).filter_by(player_id=learner_id).count() == 1


def test_completing_an_igot_course_does_not_issue_a_certificate():
    db = _db()
    learner_id = _make_player(db)
    client = TestClient(_app(db, _principal(learner_id, frozenset({"learner"}))))
    enrollment = client.post(
        "/learning/catalogue/enroll",
        json={"player_id": learner_id, "course_id": "igot::os_sampling_design", "title": "Sampling"},
    ).json()
    client.post(
        f"/learning/catalogue/enrollments/{enrollment['enrollment_id']}/complete",
        json={"player_id": learner_id},
    )
    assert db.query(Certificate).count() == 0


def test_certificate_verification_by_public_code_requires_no_auth():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    course_id = _publish_course(db, trainer_id, "Public Verify Test", "x")
    learner_id = _make_player(db)
    _enroll_and_complete(db, learner_id, course_id)
    code = db.query(Certificate).filter_by(player_id=learner_id).one().verification_code

    anonymous_client = TestClient(_app(db, principal=None))
    response = anonymous_client.get(f"/learning/certificates/verify/{code}")
    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["title"] == "Public Verify Test"


def test_certificate_verification_rejects_an_unknown_code():
    db = _db()
    anonymous_client = TestClient(_app(db, principal=None))
    response = anonymous_client.get("/learning/certificates/verify/not-a-real-code")
    assert response.status_code == 200
    assert response.json()["valid"] is False


def test_a_learner_cannot_list_another_learners_certificates():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    course_id = _publish_course(db, trainer_id, "Privacy Test", "x")
    owner_id = _make_player(db, username_prefix="owner")
    _enroll_and_complete(db, owner_id, course_id)

    other_id = _make_player(db, username_prefix="other")
    other_client = TestClient(_app(db, _principal(other_id, frozenset({"learner"}))))
    response = other_client.get("/learning/certificates", params={"player_id": owner_id})
    assert response.status_code == 403


# ---------- Feedback ----------


def test_enrolled_learner_can_submit_feedback():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    course_id = _publish_course(db, trainer_id, "Feedback Course", "x")
    learner_id = _make_player(db)
    client = TestClient(_app(db, _principal(learner_id, frozenset({"learner"}))))
    client.post(
        "/learning/catalogue/enroll",
        json={"player_id": learner_id, "course_id": f"internal::{course_id}", "title": "ignored"},
    )

    response = client.post(
        f"/learning/courses/{course_id}/feedback",
        json={"player_id": learner_id, "rating": 4, "comment": "Solid course"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["rating"] == 4
    assert body["comment"] == "Solid course"


def test_unenrolled_learner_cannot_submit_feedback():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    course_id = _publish_course(db, trainer_id, "Gatekept Course", "x")
    learner_id = _make_player(db)
    client = TestClient(_app(db, _principal(learner_id, frozenset({"learner"}))))

    response = client.post(
        f"/learning/courses/{course_id}/feedback",
        json={"player_id": learner_id, "rating": 5, "comment": "never enrolled"},
    )
    assert response.status_code == 403


def test_resubmitting_feedback_updates_in_place_not_a_second_row():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    course_id = _publish_course(db, trainer_id, "Upsert Course", "x")
    learner_id = _make_player(db)
    client = TestClient(_app(db, _principal(learner_id, frozenset({"learner"}))))
    client.post(
        "/learning/catalogue/enroll",
        json={"player_id": learner_id, "course_id": f"internal::{course_id}", "title": "ignored"},
    )

    first = client.post(
        f"/learning/courses/{course_id}/feedback",
        json={"player_id": learner_id, "rating": 2, "comment": "meh"},
    ).json()
    second = client.post(
        f"/learning/courses/{course_id}/feedback",
        json={"player_id": learner_id, "rating": 5, "comment": "actually great on reflection"},
    ).json()

    assert first["feedback_id"] == second["feedback_id"]
    assert db.query(CourseFeedback).filter_by(player_id=learner_id, course_id=course_id).count() == 1
    assert second["rating"] == 5


def test_feedback_summary_aggregates_without_exposing_reviewer_identity():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    course_id = _publish_course(db, trainer_id, "Summary Course", "x")

    for rating, comment in [(4, "good"), (2, "meh"), (5, "great")]:
        learner_id = _make_player(db)
        client = TestClient(_app(db, _principal(learner_id, frozenset({"learner"}))))
        client.post(
            "/learning/catalogue/enroll",
            json={"player_id": learner_id, "course_id": f"internal::{course_id}", "title": "ignored"},
        )
        client.post(
            f"/learning/courses/{course_id}/feedback",
            json={"player_id": learner_id, "rating": rating, "comment": comment},
        )

    reader_id = _make_player(db, username_prefix="reader")
    reader_client = TestClient(_app(db, _principal(reader_id, frozenset({"learner"}))))
    summary = reader_client.get(f"/learning/courses/{course_id}/feedback").json()
    assert summary["count"] == 3
    assert summary["average_rating"] == round((4 + 2 + 5) / 3, 2)
    assert set(summary["comments"]) == {"good", "meh", "great"}
    assert "player_id" not in str(summary)


def test_invalid_rating_is_rejected():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    course_id = _publish_course(db, trainer_id, "Bad Rating Course", "x")
    learner_id = _make_player(db)
    client = TestClient(_app(db, _principal(learner_id, frozenset({"learner"}))))
    client.post(
        "/learning/catalogue/enroll",
        json={"player_id": learner_id, "course_id": f"internal::{course_id}", "title": "ignored"},
    )
    response = client.post(
        f"/learning/courses/{course_id}/feedback",
        json={"player_id": learner_id, "rating": 7, "comment": "out of range"},
    )
    assert response.status_code == 422
