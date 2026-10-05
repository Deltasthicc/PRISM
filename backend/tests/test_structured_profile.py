"""SIH26075 PS75-02: structured, self-declared profile lists.

HTTP contract for PUT/GET /learning/profile/{player_id}. Follows the isolated
app + in-memory SQLite + require_principal override pattern of
tests/test_course_enrollment.py.
"""
from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base, get_db
from models.accuracy_history import AccuracyHistory  # noqa: F401
from models.dungeon import Dungeon, Room  # noqa: F401
from models.governance import AuditEvent  # noqa: F401
from models.guild import Guild  # noqa: F401
from models.identity import IdentityBinding  # noqa: F401
from models.learning import CompetencyAssessment, GeneratedQuiz, LearnerProfile, LearningMaterial  # noqa: F401
from models.player import Player
from models.question import Question  # noqa: F401
from models.session import GameSession  # noqa: F401
from models.submission import AnswerSubmission  # noqa: F401
from routes.authorization import require_principal
from routes.learning_profile import router as profile_router
from security.rbac import BoundPrincipal


class _Subject:
    issuer = "https://issuer.example/realm"
    subject_id = "subject-1"
    roles = frozenset({"learner"})


def _db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _client(db, player_id: str) -> TestClient:
    app = FastAPI()
    app.include_router(profile_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    principal = BoundPrincipal(subject=_Subject(), binding_id="b-1", player_id=player_id, roles=_Subject.roles)
    app.dependency_overrides[require_principal] = lambda: principal
    return TestClient(app)


def _player(db) -> str:
    player_id = str(uuid.uuid4())
    db.add(Player(player_id=player_id, username=f"p-{player_id[:8]}"))
    db.commit()
    return player_id


STRUCTURED = {
    "qualifications": [{"degree": "M.Sc. Meteorology", "institution": "IITM Pune", "year": 2014}],
    "work_experience": [
        {"title": "Forecaster", "organization": "IMD", "start_year": 2015, "end_year": 2020, "description": "Daily forecasts"}
    ],
    "interests": ["Climate modelling", "Open data"],
    "skills": ["Python", "GIS"],
    "external_certificates": [{"name": "GIS Professional", "issuer": "Esri", "year": 2019, "credential_id": "ABC-123"}],
}


def test_structured_fields_round_trip():
    db = _db()
    pid = _player(db)
    client = _client(db, pid)

    put = client.put(f"/learning/profile/{pid}", json={"full_name": "Asha", **STRUCTURED})
    assert put.status_code == 200

    profile = client.get(f"/learning/profile/{pid}").json()["profile"]
    assert profile["qualifications"] == [{"degree": "M.Sc. Meteorology", "institution": "IITM Pune", "year": 2014}]
    assert profile["work_experience"][0]["title"] == "Forecaster"
    assert profile["interests"] == ["Climate modelling", "Open data"]
    assert profile["skills"] == ["Python", "GIS"]
    assert profile["external_certificates"][0]["credential_id"] == "ABC-123"


def test_a_profile_never_saved_with_them_reads_as_empty_lists():
    db = _db()
    pid = _player(db)
    client = _client(db, pid)
    client.put(f"/learning/profile/{pid}", json={"full_name": "Asha"})
    profile = client.get(f"/learning/profile/{pid}").json()["profile"]
    for field in STRUCTURED:
        assert profile[field] == []


def test_an_older_client_that_omits_the_fields_does_not_wipe_them():
    db = _db()
    pid = _player(db)
    client = _client(db, pid)
    client.put(f"/learning/profile/{pid}", json={"full_name": "Asha", **STRUCTURED})

    client.put(f"/learning/profile/{pid}", json={"full_name": "Asha K", "designation": "Scientist"})

    profile = client.get(f"/learning/profile/{pid}").json()["profile"]
    assert profile["designation"] == "Scientist"
    assert profile["skills"] == ["Python", "GIS"]
    assert len(profile["qualifications"]) == 1


def test_an_empty_list_clears_a_field():
    db = _db()
    pid = _player(db)
    client = _client(db, pid)
    client.put(f"/learning/profile/{pid}", json={"full_name": "Asha", **STRUCTURED})
    client.put(f"/learning/profile/{pid}", json={"full_name": "Asha", "skills": []})
    assert client.get(f"/learning/profile/{pid}").json()["profile"]["skills"] == []


def test_strings_are_trimmed_and_duplicate_tags_collapsed():
    db = _db()
    pid = _player(db)
    client = _client(db, pid)
    client.put(
        f"/learning/profile/{pid}",
        json={"skills": [" Python ", "python", "", "GIS"], "qualifications": [{"degree": "  B.Tech  "}]},
    )
    profile = client.get(f"/learning/profile/{pid}").json()["profile"]
    assert profile["skills"] == ["Python", "GIS"]
    assert profile["qualifications"][0]["degree"] == "B.Tech"


def test_invalid_entries_are_rejected():
    db = _db()
    pid = _player(db)
    client = _client(db, pid)
    url = f"/learning/profile/{pid}"
    assert client.put(url, json={"qualifications": [{"degree": ""}]}).status_code == 422
    assert client.put(url, json={"qualifications": [{"degree": "B.Sc", "year": 1800}]}).status_code == 422
    assert client.put(url, json={"work_experience": [{"title": "X", "start_year": 2020, "end_year": 2010}]}).status_code == 422
    assert client.put(url, json={"external_certificates": [{"name": ""}]}).status_code == 422
    assert client.put(url, json={"skills": ["x" * 81]}).status_code == 422
    assert client.put(url, json={"skills": [f"s{i}" for i in range(51)]}).status_code == 422
    assert client.put(url, json={"qualifications": [{"degree": "d"}] * 31}).status_code == 422
    assert client.put(url, json={"work_experience": [{"title": "t", "description": "d" * 1001}]}).status_code == 422


def test_another_learners_profile_cannot_be_written():
    db = _db()
    mine, theirs = _player(db), _player(db)
    response = _client(db, mine).put(f"/learning/profile/{theirs}", json={"skills": ["x"]})
    assert response.status_code in (403, 404)
    assert db.query(LearnerProfile).filter_by(player_id=theirs).count() == 0
