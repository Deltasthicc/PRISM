"""Pin exactly which HTTP operations do not require a verified, bound principal.

Every operation must depend on `routes.authorization.require_principal`
(directly or through a permission / ownership dependency) unless it appears
in OPEN_OPERATIONS below with a reason. Adding an unauthenticated route, or
protecting one listed here, fails this test until the list is updated, so an
accidentally unprotected endpoint cannot ship unnoticed.

`require_principal` is the check in every mode: under DISABLE_AUTH (the
documented demo bypass) it returns a synthetic principal instead, so this
test shows where protection is *wired*, not that the hosted demo is secure.
The dev-login bridge (tag "Local Dev Login") only exists when
ENABLE_DEV_LOGIN is set and necessarily mints tokens, so it is excluded.
"""
from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.routing import APIRoute

from main import app
from routes.authorization import require_principal

_EXCLUDED_TAGS = frozenset({"Local Dev Login"})

OPEN_OPERATIONS: dict[tuple[str, str], str] = {
    ("GET", "/"): "service banner",
    ("GET", "/health"): "liveness probe",
    ("POST", "/auth/register"): "requires a verified OIDC token but, by design, no existing binding",
    ("GET", "/auth/me"): "requires a verified OIDC token but, by design, no existing binding",
    ("GET", "/learning/certificates/verify/{verification_code}"): "public certificate verification by unguessable code",
    ("GET", "/learning/curricula"): "public curriculum catalogue",
    ("GET", "/learning/competency-quiz/topics"): "public question-bank metadata",
    ("GET", "/learning/competency-quiz/questions"): "public practice questions (answers are not returned)",
    ("POST", "/learning/competency-quiz/submit"): "anonymous practice; a player_id, when supplied, must be the caller's own",
    ("GET", "/learning/dsa-sandbox/problems"): "public problem statements",
    ("GET", "/learning/sampling-lab/tasks"): "public lab task statements",
    ("GET", "/learning/integrations/status"): "public, honestly-labelled integration status",
    ("POST", "/game/player/create"): "demo username bootstrap; creates an inert player with no binding or permissions",
    ("GET", "/game/player/by-username/{username}"): "demo username bootstrap; returns only player_id and username",
}


def _api_routes(routes):
    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router"):
            yield from _api_routes(route.original_router.routes)


def _requires_principal(dependant) -> bool:
    return dependant.call is require_principal or any(
        _requires_principal(child) for child in dependant.dependencies
    )


def _open_operations(target=app) -> set[tuple[str, str]]:
    found = set()
    for route in _api_routes(target.routes):
        if _EXCLUDED_TAGS.intersection(route.tags or []):
            continue
        if _requires_principal(route.dependant):
            continue
        for method in route.methods - {"HEAD", "OPTIONS"}:
            found.add((method, route.path))
    return found


def test_only_the_documented_operations_are_open():
    actual = _open_operations()
    expected = set(OPEN_OPERATIONS)
    assert actual - expected == set(), f"unprotected routes not in the allowlist: {sorted(actual - expected)}"
    assert expected - actual == set(), f"allowlisted routes that are now protected or gone: {sorted(expected - actual)}"


def test_the_protected_majority_is_not_trivially_small():
    protected = sum(
        1
        for route in _api_routes(app.routes)
        if not _EXCLUDED_TAGS.intersection(route.tags or []) and _requires_principal(route.dependant)
    )
    assert protected >= 80


def test_detector_flags_an_unprotected_route_and_accepts_a_protected_one():
    probe = FastAPI()

    @probe.get("/forgot-auth")
    def forgot_auth():
        return {}

    @probe.get("/has-auth")
    def has_auth(principal=Depends(require_principal)):
        return {}

    assert _open_operations(probe) == {("GET", "/forgot-auth")}
