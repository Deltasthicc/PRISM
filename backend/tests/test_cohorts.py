"""HTTP contract for real trainer/cohort assignment (routes/cohorts.py).

Follows test_course_catalog.py's isolated-app + in-memory-SQLite +
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
from models.learning import LearnerProfile, CompetencyAssessment, LearningMaterial, GeneratedQuiz
from models.governance import EvidenceRecord, RoleTarget, SourceVersion, AuditEvent  # noqa: F401
from models.identity import IdentityBinding  # noqa: F401
from models.question_bank import QuestionBankItem, QuestionBankAttempt  # noqa: F401
from models.dsa_submission import DsaSubmission  # noqa: F401
from models.course import Course  # noqa: F401
from models.course_enrollment import CourseEnrollment
from models.certificate import Certificate  # noqa: F401
from models.feedback import CourseFeedback  # noqa: F401
from models.cohort import Cohort, CohortMembership
from routes.authorization import require_principal
from routes.cohorts import router as cohorts_router
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
    app.include_router(cohorts_router)

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


def test_admin_creates_a_cohort_and_assigns_a_trainer():
    db = _db()
    admin_id = _make_player(db, username_prefix="admin")
    trainer_id = _make_player(db, username_prefix="trainer")
    client = TestClient(_app(db, _principal(admin_id, frozenset({"organization_admin"}))))

    response = client.post("/learning/cohorts", json={"name": "Coastal Hazard Cohort", "trainer_id": trainer_id})
    assert response.status_code == 200
    body = response.json()
    assert body["trainer_id"] == trainer_id
    assert body["member_count"] == 0


def test_trainer_cannot_create_a_cohort():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    client = TestClient(_app(db, _principal(trainer_id, frozenset({"trainer"}))))

    response = client.post("/learning/cohorts", json={"name": "Should Fail", "trainer_id": trainer_id})
    assert response.status_code == 403


def test_admin_adds_and_removes_a_member():
    db = _db()
    admin_id = _make_player(db, username_prefix="admin")
    trainer_id = _make_player(db, username_prefix="trainer")
    trainee_id = _make_player(db, username_prefix="trainee")
    client = TestClient(_app(db, _principal(admin_id, frozenset({"organization_admin"}))))

    cohort_id = client.post(
        "/learning/cohorts", json={"name": "Test Cohort", "trainer_id": trainer_id}
    ).json()["cohort_id"]

    added = client.post(f"/learning/cohorts/{cohort_id}/members", params={"player_id": trainee_id})
    assert added.status_code == 200
    assert added.json()["player_id"] == trainee_id

    members = client.get(f"/learning/cohorts/{cohort_id}/members")
    assert [m["player_id"] for m in members.json()] == [trainee_id]

    removed = client.delete(f"/learning/cohorts/{cohort_id}/members/{trainee_id}")
    assert removed.status_code == 200
    assert client.get(f"/learning/cohorts/{cohort_id}/members").json() == []


def test_adding_the_same_member_twice_is_idempotent():
    db = _db()
    admin_id = _make_player(db, username_prefix="admin")
    trainer_id = _make_player(db, username_prefix="trainer")
    trainee_id = _make_player(db, username_prefix="trainee")
    client = TestClient(_app(db, _principal(admin_id, frozenset({"organization_admin"}))))
    cohort_id = client.post(
        "/learning/cohorts", json={"name": "Idempotent Cohort", "trainer_id": trainer_id}
    ).json()["cohort_id"]

    client.post(f"/learning/cohorts/{cohort_id}/members", params={"player_id": trainee_id})
    client.post(f"/learning/cohorts/{cohort_id}/members", params={"player_id": trainee_id})
    assert db.query(CohortMembership).filter_by(cohort_id=cohort_id, player_id=trainee_id).count() == 1


def test_trainer_lists_only_their_own_cohorts():
    db = _db()
    admin_id = _make_player(db, username_prefix="admin")
    trainer_a = _make_player(db, username_prefix="trainer-a")
    trainer_b = _make_player(db, username_prefix="trainer-b")
    admin_client = TestClient(_app(db, _principal(admin_id, frozenset({"organization_admin"}))))
    admin_client.post("/learning/cohorts", json={"name": "A's Cohort", "trainer_id": trainer_a})
    admin_client.post("/learning/cohorts", json={"name": "B's Cohort", "trainer_id": trainer_b})

    trainer_a_client = TestClient(_app(db, _principal(trainer_a, frozenset({"trainer"}))))
    response = trainer_a_client.get("/learning/cohorts/mine", params={"trainer_id": trainer_a})
    assert response.status_code == 200
    names = [c["name"] for c in response.json()]
    assert names == ["A's Cohort"]


def test_a_trainer_cannot_list_cohorts_under_someone_elses_trainer_id():
    db = _db()
    trainer_a = _make_player(db, username_prefix="trainer-a")
    trainer_b = _make_player(db, username_prefix="trainer-b")
    trainer_a_client = TestClient(_app(db, _principal(trainer_a, frozenset({"trainer"}))))
    response = trainer_a_client.get("/learning/cohorts/mine", params={"trainer_id": trainer_b})
    assert response.status_code == 403


def test_a_trainer_cannot_read_another_trainers_cohort_members():
    db = _db()
    admin_id = _make_player(db, username_prefix="admin")
    owner_trainer = _make_player(db, username_prefix="owner")
    other_trainer = _make_player(db, username_prefix="other")
    admin_client = TestClient(_app(db, _principal(admin_id, frozenset({"organization_admin"}))))
    cohort_id = admin_client.post(
        "/learning/cohorts", json={"name": "Owner's Cohort", "trainer_id": owner_trainer}
    ).json()["cohort_id"]

    other_client = TestClient(_app(db, _principal(other_trainer, frozenset({"trainer"}))))
    response = other_client.get(f"/learning/cohorts/{cohort_id}/members")
    assert response.status_code == 404


def test_owning_trainer_can_read_their_cohort_members():
    db = _db()
    admin_id = _make_player(db, username_prefix="admin")
    trainer_id = _make_player(db, username_prefix="trainer")
    trainee_id = _make_player(db, username_prefix="trainee")
    admin_client = TestClient(_app(db, _principal(admin_id, frozenset({"organization_admin"}))))
    cohort_id = admin_client.post(
        "/learning/cohorts", json={"name": "Owned Cohort", "trainer_id": trainer_id}
    ).json()["cohort_id"]
    admin_client.post(f"/learning/cohorts/{cohort_id}/members", params={"player_id": trainee_id})

    trainer_client = TestClient(_app(db, _principal(trainer_id, frozenset({"trainer"}))))
    response = trainer_client.get(f"/learning/cohorts/{cohort_id}/members")
    assert response.status_code == 200
    assert [m["player_id"] for m in response.json()] == [trainee_id]


def test_admin_can_read_any_cohorts_members():
    db = _db()
    admin_id = _make_player(db, username_prefix="admin")
    trainer_id = _make_player(db, username_prefix="trainer")
    trainee_id = _make_player(db, username_prefix="trainee")
    admin_client = TestClient(_app(db, _principal(admin_id, frozenset({"organization_admin"}))))
    cohort_id = admin_client.post(
        "/learning/cohorts", json={"name": "Admin View Cohort", "trainer_id": trainer_id}
    ).json()["cohort_id"]
    admin_client.post(f"/learning/cohorts/{cohort_id}/members", params={"player_id": trainee_id})

    response = admin_client.get(f"/learning/cohorts/{cohort_id}/members")
    assert response.status_code == 200
    assert [m["player_id"] for m in response.json()] == [trainee_id]


def test_performance_reflects_real_enrollment_and_assessment_data():
    db = _db()
    admin_id = _make_player(db, username_prefix="admin")
    trainer_id = _make_player(db, username_prefix="trainer")
    trainee_id = _make_player(db, username_prefix="trainee")
    admin_client = TestClient(_app(db, _principal(admin_id, frozenset({"organization_admin"}))))
    cohort_id = admin_client.post(
        "/learning/cohorts", json={"name": "Performance Cohort", "trainer_id": trainer_id}
    ).json()["cohort_id"]
    admin_client.post(f"/learning/cohorts/{cohort_id}/members", params={"player_id": trainee_id})

    # Real enrollment + completion rows, same shape course_enrollment.py writes.
    db.add(
        CourseEnrollment(
            player_id=trainee_id,
            course_id="internal::some-course",
            provider="internal",
            competency_id="hazard_response",
            title="Hazard Response",
            status="completed",
        )
    )
    # Real assessment row with a known skill_gaps length.
    db.add(
        CompetencyAssessment(
            player_id=trainee_id,
            curriculum_slug="official-statistics",
            self_ratings={},
            measured_scores={},
            skill_gaps=["os_sampling_design", "os_survey_design"],
            recommended_course_ids=[],
        )
    )
    db.commit()

    trainer_client = TestClient(_app(db, _principal(trainer_id, frozenset({"trainer"}))))
    response = trainer_client.get(f"/learning/cohorts/{cohort_id}/performance")
    assert response.status_code == 200
    rows = response.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["player_id"] == trainee_id
    assert row["courses_enrolled"] == 1
    assert row["courses_completed"] == 1
    assert row["assessments_taken"] == 1
    assert row["open_skill_gaps"] == 2
    assert row["latest_assessment_at"] is not None


def test_performance_for_a_member_with_no_activity_is_honestly_zero_not_fabricated():
    db = _db()
    admin_id = _make_player(db, username_prefix="admin")
    trainer_id = _make_player(db, username_prefix="trainer")
    trainee_id = _make_player(db, username_prefix="trainee")
    admin_client = TestClient(_app(db, _principal(admin_id, frozenset({"organization_admin"}))))
    cohort_id = admin_client.post(
        "/learning/cohorts", json={"name": "Empty Activity Cohort", "trainer_id": trainer_id}
    ).json()["cohort_id"]
    admin_client.post(f"/learning/cohorts/{cohort_id}/members", params={"player_id": trainee_id})

    trainer_client = TestClient(_app(db, _principal(trainer_id, frozenset({"trainer"}))))
    row = trainer_client.get(f"/learning/cohorts/{cohort_id}/performance").json()[0]
    assert row["courses_enrolled"] == 0
    assert row["assessments_taken"] == 0
    assert row["latest_assessment_at"] is None
    assert row["open_skill_gaps"] is None


def test_list_all_cohorts_requires_admin_not_just_any_trainer():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    client = TestClient(_app(db, _principal(trainer_id, frozenset({"trainer"}))))
    response = client.get("/learning/cohorts")
    assert response.status_code == 403
