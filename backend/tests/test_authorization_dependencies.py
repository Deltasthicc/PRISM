"""HTTP-level contract for the composed Lane 5 authorization adapters."""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from routes.authorization import (
    require_deployment_tenant_dependency,
    require_own_player_dependency,
    require_permission_dependency,
    require_principal,
)
from security.identity import AuthenticationError
from security.rbac import AuthorizationError, BoundPrincipal, Permission


class _Subject:
    issuer = "https://issuer.example.test/realm"
    subject_id = "subject-1"
    roles = frozenset({"learner"})


@pytest.fixture
def principal() -> BoundPrincipal:
    return BoundPrincipal(
        subject=_Subject(),
        binding_id="binding-1",
        player_id="player-1",
        roles=frozenset({"learner"}),
    )


@pytest.fixture
def app() -> FastAPI:
    application = FastAPI()

    @application.get("/principal")
    def principal_endpoint(
        current: BoundPrincipal = Depends(require_principal),
    ):
        return {"binding_id": current.binding_id}

    @application.get("/tenant")
    def tenant_endpoint(
        current: BoundPrincipal = Depends(require_deployment_tenant_dependency),
    ):
        return {"binding_id": current.binding_id}

    @application.get("/admin")
    def admin_endpoint(
        current: BoundPrincipal = Depends(
            require_permission_dependency(Permission.ORGANIZATION_ANALYTICS_READ)
        ),
    ):
        return {"binding_id": current.binding_id}

    @application.get("/players/{player_id}")
    def own_player_endpoint(
        player_id: str,
        current: BoundPrincipal = Depends(
            require_own_player_dependency(Permission.PLAYER_SELF_READ)
        ),
    ):
        return {"binding_id": current.binding_id, "player_id": player_id}

    return application


def test_missing_or_invalid_token_has_stable_sanitized_401_and_bearer_challenge(
    app, monkeypatch
):
    sensitive_detail = "invalid token carried secret-claim-value"

    def reject(_authorization):
        raise AuthenticationError(sensitive_detail)

    monkeypatch.setattr("routes.authorization.get_current_subject", reject)
    response = TestClient(app).get(
        "/principal", headers={"Authorization": "Bearer secret-token-body"}
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
    assert response.headers["www-authenticate"] == "Bearer"
    assert sensitive_detail not in response.text
    assert "secret-token-body" not in response.text


def test_missing_token_uses_the_same_401_contract(app, monkeypatch):
    def reject(authorization):
        assert authorization is None
        raise AuthenticationError("missing bearer token")

    monkeypatch.setattr("routes.authorization.get_current_subject", reject)
    response = TestClient(app).get("/principal")

    assert response.status_code == 401
    assert response.json() == {"detail": "Authentication required"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_binding_failure_has_stable_sanitized_403(app, monkeypatch):
    monkeypatch.setattr("routes.authorization.get_current_subject", lambda _header: _Subject())

    def reject_binding(_db, _subject):
        raise AuthorizationError("private binding lookup detail")

    monkeypatch.setattr("routes.authorization.resolve_bound_principal", reject_binding)
    response = TestClient(app).get(
        "/principal", headers={"Authorization": "Bearer syntactically-valid"}
    )

    assert response.status_code == 403
    assert response.json() == {"detail": "Access denied"}
    assert "private binding lookup detail" not in response.text


def test_principal_dependency_returns_the_exact_resolved_object(
    principal, monkeypatch
):
    subject = _Subject()
    monkeypatch.setattr(
        "routes.authorization.get_current_subject", lambda _header: subject
    )

    def resolve(_db, resolved_subject):
        assert resolved_subject is subject
        return principal

    monkeypatch.setattr("routes.authorization.resolve_bound_principal", resolve)

    assert require_principal("Bearer verified", object()) is principal


def test_permission_dependency_returns_the_exact_principal_object(principal):
    dependency = require_permission_dependency(Permission.PLAYER_SELF_READ)

    assert dependency(principal) is principal


def test_permission_failure_is_403_and_dependency_override_is_composable(
    app, principal
):
    app.dependency_overrides[require_principal] = lambda: principal
    response = TestClient(app).get("/admin")

    assert response.status_code == 403
    assert response.json() == {"detail": "Access denied"}


def test_deployment_tenant_check_remains_separately_composable(app, principal):
    assert require_deployment_tenant_dependency(principal) is principal

    forged = replace(principal, tenant_scope="browser-supplied-tenant")
    app.dependency_overrides[require_principal] = lambda: forged
    response = TestClient(app).get("/tenant")

    assert response.status_code == 403
    assert response.json() == {"detail": "Access denied"}


def test_own_player_dependency_accepts_bound_player_and_returns_same_principal(
    app, principal
):
    dependency = require_own_player_dependency(Permission.PLAYER_SELF_READ)
    assert dependency("player-1", principal) is principal

    app.dependency_overrides[require_principal] = lambda: principal
    response = TestClient(app).get("/players/player-1")

    assert response.status_code == 200
    assert response.json() == {"binding_id": "binding-1", "player_id": "player-1"}


def test_own_player_dependency_rejects_cross_player_object_scope(app, principal):
    app.dependency_overrides[require_principal] = lambda: principal
    response = TestClient(app).get("/players/player-2")

    assert response.status_code == 403
    assert response.json() == {"detail": "Access denied"}


def test_own_player_dependency_rejects_unbound_administrative_identity(
    app, principal
):
    unbound = replace(principal, player_id=None)
    app.dependency_overrides[require_principal] = lambda: unbound
    response = TestClient(app).get("/players/player-1")

    assert response.status_code == 403
    assert response.json() == {"detail": "Access denied"}
