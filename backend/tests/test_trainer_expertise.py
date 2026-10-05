"""HTTP contract for a trainer's declared expertise
(routes/trainer_expertise.py). Follows test_cohorts.py's isolated-app +
in-memory-SQLite + require_principal-override pattern."""
from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import routes.trainer_expertise as expertise_routes
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
from models.governance import EvidenceRecord, RoleTarget, SourceVersion, AuditEvent  # noqa: F401
from models.identity import IdentityBinding  # noqa: F401
from models.question_bank import QuestionBankItem, QuestionBankAttempt  # noqa: F401
from models.dsa_submission import DsaSubmission  # noqa: F401
from models.course import Course  # noqa: F401
from models.course_enrollment import CourseEnrollment  # noqa: F401
from models.certificate import Certificate  # noqa: F401
from models.feedback import CourseFeedback  # noqa: F401
from models.cohort import Cohort, CohortMembership  # noqa: F401
from models.trainer_expertise import TrainerExpertise
from routes.authorization import require_principal
from routes.trainer_expertise import router as trainer_expertise_router
from security.rbac import BoundPrincipal

COMPETENCY = "arrays"
BODY = {"declared_level": 4, "basis": "degree", "basis_detail": "M.Sc. Meteorology", "years_teaching": 6}


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


def _client(db, principal: BoundPrincipal) -> TestClient:
    app = FastAPI()
    app.include_router(trainer_expertise_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_principal] = lambda: principal
    return TestClient(app)


def _player(db, prefix="p") -> str:
    player_id = str(uuid.uuid4())
    db.add(Player(player_id=player_id, username=f"{prefix}-{player_id[:8]}"))
    db.commit()
    return player_id


def _trainer(db):
    trainer_id = _player(db, "trainer")
    return trainer_id, _client(db, _principal(trainer_id, frozenset({"trainer"})))


def _url(trainer_id, competency=COMPETENCY):
    return f"/learning/trainers/{trainer_id}/expertise/{competency}"


# ------------------------------------------------------------------ writes


def test_trainer_declares_expertise_and_it_is_flagged_unverified():
    db = _db()
    trainer_id, client = _trainer(db)
    response = client.put(_url(trainer_id), json=BODY)
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "expertise_id", "trainer_id", "competency_id", "competency_label", "declared_level",
        "basis", "basis_detail", "years_teaching", "self_declared", "verified",
        "created_at", "updated_at",
    }
    assert body["trainer_id"] == trainer_id
    assert body["declared_level"] == 4
    assert body["competency_label"]
    assert body["self_declared"] is True and body["verified"] is False


def test_unknown_competency_is_422_and_nothing_is_stored():
    db = _db()
    trainer_id, client = _trainer(db)
    assert client.put(_url(trainer_id, "not_a_competency"), json=BODY).status_code == 422
    assert db.query(TrainerExpertise).count() == 0


@pytest.mark.parametrize("level", [0, 6, -1])
def test_level_outside_1_to_5_is_422(level):
    db = _db()
    trainer_id, client = _trainer(db)
    assert client.put(_url(trainer_id), json={**BODY, "declared_level": level}).status_code == 422


@pytest.mark.parametrize(
    "patch",
    [
        {"basis": "vibes"},
        {"years_teaching": -1},
        {"basis_detail": "x" * 501},
        {"declared_level": "high"},
    ],
)
def test_other_invalid_fields_are_422(patch):
    db = _db()
    trainer_id, client = _trainer(db)
    assert client.put(_url(trainer_id), json={**BODY, **patch}).status_code == 422


def test_basis_detail_at_limit_is_accepted_and_years_defaults_to_zero():
    db = _db()
    trainer_id, client = _trainer(db)
    response = client.put(_url(trainer_id), json={"declared_level": 1, "basis": "other", "basis_detail": "x" * 500})
    assert response.status_code == 200
    assert response.json()["years_teaching"] == 0


def test_put_is_idempotent_and_updates_in_place():
    db = _db()
    trainer_id, client = _trainer(db)
    first = client.put(_url(trainer_id), json=BODY).json()
    again = client.put(_url(trainer_id), json=BODY).json()
    assert again["expertise_id"] == first["expertise_id"]
    updated = client.put(_url(trainer_id), json={**BODY, "declared_level": 2, "years_teaching": 1}).json()
    assert updated["expertise_id"] == first["expertise_id"]
    assert updated["declared_level"] == 2 and updated["years_teaching"] == 1
    assert db.query(TrainerExpertise).count() == 1


def test_concurrent_insert_race_returns_updated_winner(monkeypatch):
    """Simulate losing the insert race: the existence check sees no row, but
    another request has already inserted it, so the unique constraint fires."""
    db = _db()
    trainer_id, client = _trainer(db)
    winner = client.put(_url(trainer_id), json={**BODY, "declared_level": 1}).json()

    real_find = expertise_routes._find
    calls = {"n": 0}

    def stale_first(db_, trainer, competency):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_find(db_, trainer, competency)

    monkeypatch.setattr(expertise_routes, "_find", stale_first)
    response = client.put(_url(trainer_id), json={**BODY, "declared_level": 5})
    assert response.status_code == 200
    assert response.json()["expertise_id"] == winner["expertise_id"]
    assert response.json()["declared_level"] == 5
    assert db.query(TrainerExpertise).count() == 1


def test_database_constraints_back_the_validation():
    db = _db()
    trainer_id = _player(db)
    for bad in (
        dict(declared_level=0, basis="degree", years_teaching=0),
        dict(declared_level=6, basis="degree", years_teaching=0),
        dict(declared_level=3, basis="rumour", years_teaching=0),
        dict(declared_level=3, basis="degree", years_teaching=-1),
    ):
        db.add(TrainerExpertise(trainer_id=trainer_id, competency_id=COMPETENCY, basis_detail="", **bad))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    ok = dict(trainer_id=trainer_id, competency_id=COMPETENCY, declared_level=3, basis="degree",
              basis_detail="", years_teaching=0)
    db.add(TrainerExpertise(**ok))
    db.commit()
    db.add(TrainerExpertise(**ok))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# --------------------------------------------------------------- ownership


def test_trainer_cannot_write_another_trainers_expertise():
    db = _db()
    _, client = _trainer(db)
    other = _player(db, "other-trainer")
    response = client.put(_url(other), json=BODY)
    assert response.status_code == 403  # require_own_player's behaviour
    assert db.query(TrainerExpertise).count() == 0


def test_even_an_admin_cannot_write_someone_elses_expertise():
    db = _db()
    admin = _player(db, "admin")
    trainer_id = _player(db, "trainer")
    client = _client(db, _principal(admin, frozenset({"organization_admin"})))
    assert client.put(_url(trainer_id), json=BODY).status_code == 403


def test_learner_cannot_manage_expertise():
    db = _db()
    learner = _player(db, "learner")
    client = _client(db, _principal(learner, frozenset({"learner"})))
    assert client.put(_url(learner), json=BODY).status_code == 403
    assert client.get(f"/learning/trainers/{learner}/expertise").status_code == 403
    assert client.get(f"/learning/trainers/{learner}/profile").status_code == 403


def test_ownership_is_checked_before_existence_so_probing_learns_nothing():
    db = _db()
    _, client = _trainer(db)
    ghost = str(uuid.uuid4())
    other = _player(db, "real-other")
    assert client.put(_url(ghost), json=BODY).status_code == 403
    assert client.put(_url(other), json=BODY).status_code == 403
    assert client.delete(_url(other)).status_code == 403


def test_writing_for_own_but_nonexistent_player_is_404():
    db = _db()
    ghost = str(uuid.uuid4())
    client = _client(db, _principal(ghost, frozenset({"trainer"})))
    assert client.put(_url(ghost), json=BODY).status_code == 404


# ------------------------------------------------------------------- reads


def test_trainer_reads_own_expertise_sorted_with_notice():
    db = _db()
    trainer_id, client = _trainer(db)
    client.put(_url(trainer_id, "linked_lists"), json=BODY)
    client.put(_url(trainer_id, "arrays"), json=BODY)
    body = client.get(f"/learning/trainers/{trainer_id}/expertise").json()
    assert body["trainer_id"] == trainer_id
    assert [e["competency_id"] for e in body["expertise"]] == ["arrays", "linked_lists"]
    assert "self-declared" in body["notice"]


def test_trainer_cannot_read_another_trainers_expertise_or_profile():
    db = _db()
    _, client = _trainer(db)
    other = _player(db, "other")
    assert client.get(f"/learning/trainers/{other}/expertise").status_code == 403
    assert client.get(f"/learning/trainers/{other}/profile").status_code == 403


def test_admin_can_read_any_trainers_expertise_and_profile():
    db = _db()
    admin = _player(db, "admin")
    trainer_id, trainer_client = _trainer(db)
    trainer_client.put(_url(trainer_id), json=BODY)
    admin_client = _client(db, _principal(admin, frozenset({"organization_admin"})))
    listing = admin_client.get(f"/learning/trainers/{trainer_id}/expertise")
    assert listing.status_code == 200 and len(listing.json()["expertise"]) == 1
    assert admin_client.get(f"/learning/trainers/{trainer_id}/profile").status_code == 200


def test_profile_combines_learner_profile_with_expertise():
    db = _db()
    trainer_id, client = _trainer(db)
    db.add(LearnerProfile(player_id=trainer_id, full_name="Dr. Meera Iyer", designation="Scientist C",
                          department="Forecasting", educational_qualifications="PhD Atmospheric Science"))
    db.commit()
    client.put(_url(trainer_id), json=BODY)
    body = client.get(f"/learning/trainers/{trainer_id}/profile").json()
    assert body["trainer_id"] == trainer_id
    assert body["profile"]["designation"] == "Scientist C"
    assert body["profile"]["educational_qualifications"] == "PhD Atmospheric Science"
    assert [e["competency_id"] for e in body["expertise"]] == [COMPETENCY]
    assert "self-declared" in body["notice"]


def test_profile_without_a_base_profile_is_null_not_invented():
    db = _db()
    trainer_id, client = _trainer(db)
    body = client.get(f"/learning/trainers/{trainer_id}/profile").json()
    assert body["profile"] is None
    assert body["expertise"] == []


# ------------------------------------------------------------------ delete


def test_delete_removes_own_row_then_404():
    db = _db()
    trainer_id, client = _trainer(db)
    client.put(_url(trainer_id), json=BODY)
    assert client.delete(_url(trainer_id)).json() == {"removed": True}
    assert db.query(TrainerExpertise).count() == 0
    assert client.delete(_url(trainer_id)).status_code == 404


def test_delete_does_not_touch_other_trainers_rows():
    db = _db()
    trainer_id, client = _trainer(db)
    other_id, other_client = _trainer(db)
    client.put(_url(trainer_id), json=BODY)
    other_client.put(_url(other_id), json=BODY)
    client.delete(_url(trainer_id))
    assert [r.trainer_id for r in db.query(TrainerExpertise)] == [other_id]
