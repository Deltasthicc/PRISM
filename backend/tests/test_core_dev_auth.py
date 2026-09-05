"""Package: local-dev-only bridge from the demo username login to a real
verified Keycloak bearer token (`routes/dev_auth.py`).

This never talks to a real Keycloak -- `httpx.post` and `get_current_subject`
are both mocked, so these tests prove the route's own logic (config
validation, error translation, identity-binding upsert), not that a live
Keycloak instance actually works. That live path can only be proven by hand
against `docker-compose.dev.yml` -- see `backend/keycloak/README.md`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base, get_db
from models.accuracy_history import AccuracyHistory  # noqa: F401 -- relationship target
from models.dungeon import Dungeon, Room  # noqa: F401 -- relationship target
from models.guild import Guild  # noqa: F401 -- relationship target
from models.identity import IdentityBinding
from models.player import Player
from models.question import Question  # noqa: F401 -- relationship target
from models.session import GameSession  # noqa: F401 -- relationship target
from models.submission import AnswerSubmission  # noqa: F401 -- relationship target
import routes.dev_auth as dev_auth
from security.identity import AuthenticatedSubject, AuthenticationError

ISSUER = "http://localhost:8180/realms/prism"
SUBJECT_ID = "11111111-2222-3333-4444-555555555555"
DEV_ENV = {
    "KEYCLOAK_DEV_TOKEN_URL": "http://localhost:8180/realms/prism/protocol/openid-connect/token",
    "KEYCLOAK_DEV_CLIENT_ID": "prism-backend-dev",
    "KEYCLOAK_DEV_CLIENT_SECRET": "prism_dev_local_only_client_secret",
    "KEYCLOAK_DEV_USERNAME": "demo-learner",
    "KEYCLOAK_DEV_PASSWORD": "prism_dev_local_only",
}


class _FakeTokenResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def _fake_subject(player_hint: str = "irrelevant") -> AuthenticatedSubject:
    return AuthenticatedSubject(
        subject_id=SUBJECT_ID,
        username="demo-learner",
        roles=frozenset({"learner"}),
        issuer=ISSUER,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
        raw_claims={},
    )


@pytest.fixture
def client(monkeypatch):
    for key, value in DEV_ENV.items():
        monkeypatch.setenv(key, value)

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(dev_auth.router)
    app.dependency_overrides[get_db] = override_get_db

    with TestingSessionLocal() as db:
        db.add(Player(player_id="player-a", username="alice"))
        db.add(Player(player_id="player-b", username="bob"))
        db.commit()

    with TestClient(app) as test_client:
        yield test_client, TestingSessionLocal


def test_missing_config_returns_503_not_a_crash(client, monkeypatch):
    test_client, _ = client
    monkeypatch.delenv("KEYCLOAK_DEV_CLIENT_SECRET", raising=False)
    response = test_client.post("/auth/dev-login", json={"player_id": "player-a"})
    assert response.status_code == 503
    assert "client_secret" in response.json()["detail"]


def test_unreachable_keycloak_returns_503_not_a_crash(client, monkeypatch):
    test_client, _ = client

    def _boom(*args, **kwargs):
        import httpx

        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(dev_auth.httpx, "post", _boom)
    response = test_client.post("/auth/dev-login", json={"player_id": "player-a"})
    assert response.status_code == 503
    assert "Keycloak" in response.json()["detail"]


def test_a_token_that_fails_this_deployments_own_verification_is_rejected(client, monkeypatch):
    test_client, _ = client
    monkeypatch.setattr(
        dev_auth.httpx,
        "post",
        lambda *a, **k: _FakeTokenResponse({"access_token": "not-a-real-jwt", "expires_in": 300}),
    )

    def _reject(_header):
        raise AuthenticationError("signature verification failed")

    monkeypatch.setattr(dev_auth, "get_current_subject", _reject)
    response = test_client.post("/auth/dev-login", json={"player_id": "player-a"})
    assert response.status_code == 503
    assert "failed this deployment's own verification" in response.json()["detail"]


def test_successful_login_creates_a_binding_and_returns_a_usable_token(client, monkeypatch):
    test_client, SessionLocal = client
    monkeypatch.setattr(
        dev_auth.httpx,
        "post",
        lambda *a, **k: _FakeTokenResponse({"access_token": "real-looking-jwt", "expires_in": 300}),
    )
    monkeypatch.setattr(dev_auth, "get_current_subject", lambda header: _fake_subject())

    response = test_client.post("/auth/dev-login", json={"player_id": "player-a"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["access_token"] == "real-looking-jwt"
    assert body["role"] == "learner"

    with SessionLocal() as db:
        binding = db.query(IdentityBinding).filter(IdentityBinding.issuer == ISSUER).one()
        assert binding.subject_id == SUBJECT_ID
        assert binding.player_id == "player-a"
        assert binding.active is True


def test_a_second_login_as_a_different_player_repoints_the_same_binding_not_a_duplicate(
    client, monkeypatch
):
    """The fixed demo-learner Keycloak identity is shared across whichever
    local demo player is active -- this proves repointing an existing
    binding, not silently accumulating a second active row for the same
    (issuer, subject_id), which resolve_bound_principal()'s `.one_or_none()`
    lookup would then raise MultipleResultsFound on."""
    test_client, SessionLocal = client
    monkeypatch.setattr(
        dev_auth.httpx,
        "post",
        lambda *a, **k: _FakeTokenResponse({"access_token": "token-1", "expires_in": 300}),
    )
    monkeypatch.setattr(dev_auth, "get_current_subject", lambda header: _fake_subject())
    first = test_client.post("/auth/dev-login", json={"player_id": "player-a"})
    assert first.status_code == 200

    monkeypatch.setattr(
        dev_auth.httpx,
        "post",
        lambda *a, **k: _FakeTokenResponse({"access_token": "token-2", "expires_in": 300}),
    )
    second = test_client.post("/auth/dev-login", json={"player_id": "player-b"})
    assert second.status_code == 200

    with SessionLocal() as db:
        bindings = db.query(IdentityBinding).filter(IdentityBinding.issuer == ISSUER).all()
        assert len(bindings) == 1
        assert bindings[0].player_id == "player-b"
        assert bindings[0].active is True
