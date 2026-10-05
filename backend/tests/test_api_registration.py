"""HTTP contract for routes/registration.py -- a real gap a live audit
this session found: the only existing coverage (test_core_self_
registration.py) calls the underlying security.rbac functions directly,
never through the actual FastAPI routes. This file drives the real HTTP
layer: request parsing, dependency wiring, status codes, response shapes.

Follows test_course_catalog.py's isolated-app + in-memory-SQLite pattern,
overriding `_verified_subject` (the actual `Depends(...)` callable
routes/registration.py uses) rather than `require_principal`, since
`/auth/register` and `/auth/me` deliberately don't require an existing
binding.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

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
from models.identity import IdentityBinding
from models.learning import CompetencyAssessment, GeneratedQuiz, LearnerProfile, LearningMaterial  # noqa: F401
from models.player import Player  # noqa: F401
from models.question import Question  # noqa: F401
from models.session import GameSession  # noqa: F401
from models.submission import AnswerSubmission  # noqa: F401
from routes.authorization import require_principal
from routes.registration import _verified_subject, router as registration_router
from security.rbac import BoundPrincipal

ISSUER = "https://issuer.example.test/realms/sih"


@dataclass(frozen=True)
class SyntheticSubject:
    subject_id: str
    issuer: str = ISSUER
    roles: frozenset[str] = frozenset()
    username: str | None = None
    expires_at: datetime = datetime(2030, 1, 1, tzinfo=timezone.utc)


class _PrincipalSubject:
    def __init__(self, subject_id: str, roles: frozenset[str]):
        self.issuer = ISSUER
        self.subject_id = subject_id
        self.roles = roles


def _principal(db, subject_id: str, player_id: str | None, roles: frozenset[str]) -> BoundPrincipal:
    """A fabricated BoundPrincipal backed by a real, active IdentityBinding
    row -- decide_self_registration re-verifies the acting principal's
    binding is still active in the DB (a real revoked-token defense), so a
    binding_id with no matching row is rejected as inactive, not just
    unauthorized."""
    binding_id = f"binding-{subject_id}"
    db.add(
        IdentityBinding(
            binding_id=binding_id,
            issuer=ISSUER,
            subject_id=subject_id,
            player_id=player_id,
            active=True,
        )
    )
    db.commit()
    return BoundPrincipal(
        subject=_PrincipalSubject(subject_id, roles),
        binding_id=binding_id,
        player_id=player_id,
        roles=roles,
    )


def _db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _app(db, *, subject=None, principal: BoundPrincipal | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(registration_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    if subject is not None:
        app.dependency_overrides[_verified_subject] = lambda: subject
    if principal is not None:
        app.dependency_overrides[require_principal] = lambda: principal
    return app


def test_register_over_http_creates_a_pending_account():
    db = _db()
    client = TestClient(_app(db, subject=SyntheticSubject(subject_id="http-register-subject")))

    response = client.post(
        "/auth/register",
        json={
            "username": "http_register_user",
            "full_name": "HTTP Register User",
            "requested_role": "trainer",
            "designation": "Officer",
            "department": "IMD",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["requested_role"] == "trainer"
    assert body["player_id"] is not None


def test_register_over_http_rejects_an_elevated_requested_role():
    db = _db()
    client = TestClient(_app(db, subject=SyntheticSubject(subject_id="http-elevate-subject")))
    response = client.post(
        "/auth/register",
        json={
            "username": "http_elevate_user",
            "full_name": "Elevate",
            "requested_role": "organization_admin",
        },
    )
    assert response.status_code == 422


def test_register_over_http_without_a_bearer_token_is_401():
    db = _db()
    client = TestClient(_app(db))  # no subject override -- real, unmocked auth path
    response = client.post(
        "/auth/register",
        json={"username": "no_token_user", "full_name": "No Token", "requested_role": "learner"},
    )
    assert response.status_code == 401


def test_me_over_http_for_a_brand_new_subject_is_not_registered():
    db = _db()
    client = TestClient(_app(db, subject=SyntheticSubject(subject_id="http-me-new-subject")))
    response = client.get("/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_registered"
    assert body["player_id"] is None


def test_me_over_http_after_registering_is_pending_approval():
    db = _db()
    subject = SyntheticSubject(subject_id="http-me-pending-subject")
    client = TestClient(_app(db, subject=subject))
    client.post(
        "/auth/register",
        json={"username": "http_me_pending", "full_name": "Pending", "requested_role": "learner"},
    )

    response = client.get("/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_approval"
    assert body["requested_role"] == "learner"
    assert body["roles"] == []


def test_me_over_http_for_an_approved_returning_user_reports_approved_and_roles():
    db = _db()
    subject = SyntheticSubject(subject_id="http-me-approved-subject", roles=frozenset({"learner"}))
    client = TestClient(_app(db, subject=subject))
    binding_id = client.post(
        "/auth/register",
        json={"username": "http_me_approved", "full_name": "Approved", "requested_role": "learner"},
    ).json()["binding_id"]

    admin = _principal(db, "admin-for-approval", None, frozenset({"organization_admin"}))
    admin_client = TestClient(_app(db, principal=admin))
    decide = admin_client.post(f"/auth/pending-registrations/{binding_id}/decide", json={"decision": "approved"})
    assert decide.status_code == 200

    # Same subject signs back in later -- real returning-user case this
    # endpoint exists for.
    response = client.get("/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "approved"
    assert body["username"] == "http_me_approved"
    assert body["roles"] == ["learner"]


def test_me_over_http_without_a_bearer_token_is_401():
    db = _db()
    client = TestClient(_app(db))
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_pending_registrations_over_http_requires_admin_permission():
    db = _db()
    non_admin = _principal(db, "some-subject", None, frozenset({"learner"}))
    client = TestClient(_app(db, principal=non_admin))
    response = client.get("/auth/pending-registrations")
    assert response.status_code == 403


def test_decide_over_http_for_unknown_binding_is_404():
    db = _db()
    admin = _principal(db, "admin-for-unknown-decide", None, frozenset({"organization_admin"}))
    client = TestClient(_app(db, principal=admin))
    response = client.post("/auth/pending-registrations/does-not-exist/decide", json={"decision": "approved"})
    assert response.status_code == 404
