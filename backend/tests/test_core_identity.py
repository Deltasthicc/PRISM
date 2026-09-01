"""Tests for security/identity.py bearer-token verification.

Fully offline: generates its own RSA keypair and signs test tokens directly,
so this suite never needs a running OIDC provider -- the real Keycloak
container in backend/docker-compose.dev.yml is verified manually instead
(see LANE2_SYNC.md's Activity log for that evidence), matching the
SEED_DEMO_DATA/Postgres precedent of not making pytest hard-depend on an
external service.
"""
from __future__ import annotations

import base64
import json
import time
from types import SimpleNamespace

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from security.identity import (
    AuthenticationError,
    OIDCVerifier,
    extract_bearer_token,
    get_current_subject,
    verifier_from_env,
)

ISSUER = "https://test-issuer.invalid/realms/test"
AUDIENCE = "sih-backend-test"
KID = "test-key-1"


@pytest.fixture(scope="module")
def keypair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _make_token(
    private_key,
    kid=KID,
    issuer=ISSUER,
    audience=AUDIENCE,
    subject="user-1",
    roles=("learner",),
    extra_claims=None,
    expires_in=300,
):
    now = int(time.time())
    payload = {
        "iss": issuer,
        "sub": subject,
        "aud": audience,
        "iat": now,
        "exp": now + expires_in,
        "realm_access": {"roles": list(roles)},
        "preferred_username": f"{subject}-username",
        "typ": "Bearer",  # required since verify() now rejects a missing/wrong typ claim
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": kid})


class _StubJWKClient:
    """Stands in for PyJWKClient -- returns a fixed public key instead of
    fetching one over the network, so these tests need no live JWKS endpoint."""

    def __init__(self, public_key):
        self._public_key = public_key

    def get_signing_key_from_jwt(self, token):
        return SimpleNamespace(key=self._public_key)


@pytest.fixture
def verifier(keypair, monkeypatch):
    _, public_key = keypair
    v = OIDCVerifier(issuer=ISSUER, audience=AUDIENCE)
    monkeypatch.setattr(v, "_get_jwks_client", lambda: _StubJWKClient(public_key))
    return v


def test_verify_accepts_a_valid_token(keypair, verifier):
    private_key, _ = keypair
    token = _make_token(private_key)
    subject = verifier.verify(token)
    assert subject.subject_id == "user-1"
    assert subject.username == "user-1-username"
    assert subject.roles == frozenset({"learner"})
    assert subject.issuer == ISSUER


def test_verify_rejects_expired_token(keypair, verifier):
    private_key, _ = keypair
    token = _make_token(private_key, expires_in=-10)
    with pytest.raises(AuthenticationError):
        verifier.verify(token)


def test_verify_rejects_wrong_issuer(keypair, verifier):
    private_key, _ = keypair
    token = _make_token(private_key, issuer="https://attacker.invalid/realm")
    with pytest.raises(AuthenticationError):
        verifier.verify(token)


def test_verify_rejects_wrong_audience(keypair, verifier):
    private_key, _ = keypair
    token = _make_token(private_key, audience="some-other-service")
    with pytest.raises(AuthenticationError):
        verifier.verify(token)


def test_verify_rejects_token_signed_by_a_different_key(verifier):
    other_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    token = _make_token(other_private_key)
    with pytest.raises(AuthenticationError):
        verifier.verify(token)


def test_verify_rejects_none_algorithm_token(verifier):
    # A hand-built, unsigned "alg: none" token -- the classic JWT library
    # vulnerability class called out in RFC 8725 section 3.1. Must never
    # verify just because the claims inside look valid.
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=")
    payload = base64.urlsafe_b64encode(
        json.dumps(
            {
                "iss": ISSUER,
                "sub": "attacker",
                "aud": AUDIENCE,
                "iat": int(time.time()),
                "exp": int(time.time()) + 300,
            }
        ).encode()
    ).rstrip(b"=")
    token = (header + b"." + payload + b".").decode()
    with pytest.raises(AuthenticationError):
        verifier.verify(token)


def test_verify_rejects_token_missing_a_required_claim(keypair, verifier):
    private_key, _ = keypair
    now = int(time.time())
    payload = {"iss": ISSUER, "aud": AUDIENCE, "iat": now, "exp": now + 300}  # no "sub"
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": KID})
    with pytest.raises(AuthenticationError):
        verifier.verify(token)


def test_verify_rejects_an_empty_string_sub_claim(keypair, verifier):
    # "sub" being merely PRESENT is not enough -- an empty string satisfies
    # PyJWT's require-claim check but is not a usable stable identity key.
    private_key, _ = keypair
    now = int(time.time())
    payload = {
        "iss": ISSUER, "sub": "", "aud": AUDIENCE, "iat": now, "exp": now + 300,
        "typ": "Bearer",
    }
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": KID})
    with pytest.raises(AuthenticationError, match="non-empty string"):
        verifier.verify(token)


def test_verify_rejects_a_whitespace_only_sub_claim(keypair, verifier):
    private_key, _ = keypair
    now = int(time.time())
    payload = {
        "iss": ISSUER, "sub": "   ", "aud": AUDIENCE, "iat": now, "exp": now + 300,
        "typ": "Bearer",
    }
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": KID})
    with pytest.raises(AuthenticationError, match="non-empty string"):
        verifier.verify(token)


def test_verify_returns_empty_roles_when_realm_access_is_absent(keypair, verifier):
    private_key, _ = keypair
    now = int(time.time())
    payload = {
        "iss": ISSUER, "sub": "user-2", "aud": AUDIENCE, "iat": now, "exp": now + 300,
        "typ": "Bearer",
    }
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": KID})
    subject = verifier.verify(token)
    assert subject.roles == frozenset()


@pytest.mark.parametrize(
    "malformed_realm_access",
    [
        {"roles": {"learner": True, "trainer": True}},  # dict, not a list -- must not become {"learner","trainer"}
        {"roles": ["learner", 123, None]},  # non-string entries must be dropped, not crash
        {"roles": "learner"},  # a bare string is iterable but is not a list of roles
        "not-even-a-dict",
    ],
)
def test_verify_ignores_malformed_realm_access_shapes(keypair, verifier, malformed_realm_access):
    private_key, _ = keypair
    now = int(time.time())
    payload = {
        "iss": ISSUER, "sub": "user-3", "aud": AUDIENCE, "iat": now, "exp": now + 300,
        "typ": "Bearer", "realm_access": malformed_realm_access,
    }
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": KID})
    subject = verifier.verify(token)
    assert subject.roles == frozenset()  # malformed shape -> fail closed to zero roles, never a crash


def test_verify_accepts_a_clean_string_list_of_roles(keypair, verifier):
    private_key, _ = keypair
    now = int(time.time())
    payload = {
        "iss": ISSUER, "sub": "user-4", "aud": AUDIENCE, "iat": now, "exp": now + 300,
        "typ": "Bearer", "realm_access": {"roles": ["learner", "trainer"]},
    }
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": KID})
    subject = verifier.verify(token)
    assert subject.roles == frozenset({"learner", "trainer"})


def test_verify_fails_closed_on_a_mixed_type_roles_list_rather_than_salvaging_strings(keypair, verifier):
    # A privileged-looking string sitting in an otherwise-malformed array
    # must not grant that role just because it happened to parse as a
    # string -- the whole claim is untrusted, not just the non-string entries.
    private_key, _ = keypair
    now = int(time.time())
    payload = {
        "iss": ISSUER, "sub": "user-5", "aud": AUDIENCE, "iat": now, "exp": now + 300,
        "typ": "Bearer", "realm_access": {"roles": ["organization_admin", 42, None]},
    }
    token = jwt.encode(payload, private_key, algorithm="RS256", headers={"kid": KID})
    subject = verifier.verify(token)
    assert subject.roles == frozenset()


def test_extract_bearer_token_requires_the_bearer_scheme():
    assert extract_bearer_token("Bearer abc.def.ghi") == "abc.def.ghi"
    with pytest.raises(AuthenticationError):
        extract_bearer_token(None)
    with pytest.raises(AuthenticationError):
        extract_bearer_token("Basic abc123")
    with pytest.raises(AuthenticationError):
        extract_bearer_token("Bearer ")


def test_get_current_subject_composes_extraction_and_verification(keypair, verifier):
    private_key, _ = keypair
    token = _make_token(private_key)
    subject = get_current_subject(f"Bearer {token}", verifier=verifier)
    assert subject.subject_id == "user-1"


def test_oidc_verifier_requires_issuer_and_audience():
    with pytest.raises(ValueError):
        OIDCVerifier(issuer="", audience=AUDIENCE)
    with pytest.raises(ValueError):
        OIDCVerifier(issuer=ISSUER, audience="")


def test_verifier_from_env_requires_both_env_vars(monkeypatch):
    monkeypatch.delenv("OIDC_ISSUER", raising=False)
    monkeypatch.delenv("OIDC_AUDIENCE", raising=False)
    with pytest.raises(AuthenticationError):
        verifier_from_env()


# --- issuer scheme, discovery-document, and typ hardening
# (findings from Codex's pre-commit review of this file, LANE2_SYNC.md
# Phase 2 Activity log) ---


def test_oidc_verifier_rejects_non_loopback_http_issuer():
    with pytest.raises(ValueError):
        OIDCVerifier(issuer="http://issuer.example.com/realm", audience=AUDIENCE)


def test_oidc_verifier_allows_https_issuer():
    # Construction alone must not require network access.
    OIDCVerifier(issuer="https://issuer.example.com/realm", audience=AUDIENCE)


def test_oidc_verifier_allows_loopback_http_issuer():
    OIDCVerifier(issuer="http://localhost:8180/realms/test", audience=AUDIENCE)


def test_oidc_verifier_rejects_trailing_slash_issuer_instead_of_silently_stripping_it():
    with pytest.raises(ValueError, match="trailing slash"):
        OIDCVerifier(issuer="https://issuer.example.com/realm/", audience=AUDIENCE)


def test_oidc_verifier_rejects_leading_whitespace_issuer_even_though_urlparse_tolerates_it():
    # urlparse(" https://issuer.example/realm") parses to a clean https URL
    # with the right hostname -- confirmed directly against this Python
    # version -- so relying on urlparse alone to catch this would silently
    # accept a value carrying a leading space that a different HTTP client
    # or the exact-match check against a real `iss` claim might handle
    # differently. Found by Codex's review of Package I; verified before
    # fixing.
    with pytest.raises(ValueError, match="whitespace or control characters"):
        OIDCVerifier(issuer=" https://issuer.example.com/realm", audience=AUDIENCE)


@pytest.mark.parametrize("control_character", ["\n", "\t", "\r", "\x00", "\x7f"])
def test_oidc_verifier_rejects_embedded_control_characters_in_issuer(control_character):
    with pytest.raises(ValueError, match="whitespace or control characters"):
        OIDCVerifier(
            issuer=f"https://issuer.example.com/re{control_character}alm", audience=AUDIENCE
        )


@pytest.mark.parametrize(
    "bad_issuer",
    [
        "realms/test",  # relative -- no scheme/host at all
        "https://user:pass@issuer.example.com/realm",  # userinfo
        "https://issuer.example.com/realm?next=/admin",  # query string
        "https://issuer.example.com/realm#fragment",  # fragment
        "https://issuer.example.com:invalid/realm",  # non-numeric port
        "https://issuer.example.com:70000/realm",  # out-of-range port
    ],
)
def test_oidc_verifier_rejects_unsafe_issuer_url_shapes(bad_issuer):
    # The port cases were found by symmetry with Codex's equivalent fix in
    # security/rbac.py's independent _issuer() validator: urlsplit/urlparse
    # only validate a URL's port lazily, on first access of `.port` -- until
    # that attribute is actually read, a malformed port sails through
    # unnoticed. Confirmed this module had the same gap before fixing it.
    with pytest.raises(ValueError):
        OIDCVerifier(issuer=bad_issuer, audience=AUDIENCE)


def test_discover_jwks_uri_rejects_unsafe_jwks_uri_shapes(monkeypatch):
    v = OIDCVerifier(issuer=ISSUER, audience=AUDIENCE)
    monkeypatch.setattr(
        "security.identity.httpx.get",
        lambda *a, **k: _FakeHttpxResponse(
            {"issuer": ISSUER, "jwks_uri": "https://user:pass@test-issuer.invalid/jwks"}
        ),
    )
    with pytest.raises(AuthenticationError, match="unsafe"):
        v._discover_jwks_uri()


class _FakeHttpxResponse:
    def __init__(self, json_value=None, json_error=None):
        self._json_value = json_value
        self._json_error = json_error

    def raise_for_status(self):
        pass

    def json(self):
        if self._json_error is not None:
            raise self._json_error
        return self._json_value


def test_discover_jwks_uri_rejects_mismatched_document_issuer(monkeypatch):
    v = OIDCVerifier(issuer=ISSUER, audience=AUDIENCE)
    monkeypatch.setattr(
        "security.identity.httpx.get",
        lambda *a, **k: _FakeHttpxResponse({"issuer": "https://wrong-issuer.invalid", "jwks_uri": "https://x/jwks"}),
    )
    with pytest.raises(AuthenticationError, match="does not exactly match"):
        v._discover_jwks_uri()


def test_discover_jwks_uri_rejects_non_object_document(monkeypatch):
    v = OIDCVerifier(issuer=ISSUER, audience=AUDIENCE)
    monkeypatch.setattr(
        "security.identity.httpx.get", lambda *a, **k: _FakeHttpxResponse(["not", "an", "object"])
    )
    with pytest.raises(AuthenticationError, match="not a JSON object"):
        v._discover_jwks_uri()


def test_discover_jwks_uri_rejects_malformed_json(monkeypatch):
    v = OIDCVerifier(issuer=ISSUER, audience=AUDIENCE)
    monkeypatch.setattr(
        "security.identity.httpx.get",
        lambda *a, **k: _FakeHttpxResponse(json_error=ValueError("boom")),
    )
    with pytest.raises(AuthenticationError, match="not valid JSON"):
        v._discover_jwks_uri()


def test_discover_jwks_uri_never_leaks_a_bare_httpx_invalid_url(monkeypatch):
    # httpx.InvalidURL does not subclass httpx.HTTPError -- confirmed via
    # their MRO -- so it needed its own except clause to honor "callers only
    # ever see AuthenticationError". Construction-time port validation should
    # make this unreachable through the normal flow, but this test pins the
    # backstop directly by making httpx.get raise it, rather than relying on
    # the (also tested) construction-time rejection alone.
    v = OIDCVerifier(issuer=ISSUER, audience=AUDIENCE)
    monkeypatch.setattr(
        "security.identity.httpx.get",
        lambda *a, **k: (_ for _ in ()).throw(httpx.InvalidURL("boom")),
    )
    with pytest.raises(AuthenticationError, match="could not reach"):
        v._discover_jwks_uri()


def test_malformed_port_issuer_is_rejected_before_any_network_call(monkeypatch):
    # Pins the actual scenario found during cross-review: OIDCVerifier(...)
    # must reject a malformed-port issuer at construction, so
    # _discover_jwks_uri() is never even reachable with a bad URL.
    def _network_call_should_never_happen(*args, **kwargs):
        raise AssertionError("httpx.get must not be called for a rejected issuer")

    monkeypatch.setattr("security.identity.httpx.get", _network_call_should_never_happen)
    with pytest.raises(ValueError, match="invalid port"):
        OIDCVerifier(issuer="https://issuer.example.com:bad/realm", audience=AUDIENCE)


def test_discover_jwks_uri_rejects_insecure_jwks_uri(monkeypatch):
    v = OIDCVerifier(issuer=ISSUER, audience=AUDIENCE)
    monkeypatch.setattr(
        "security.identity.httpx.get",
        lambda *a, **k: _FakeHttpxResponse({"issuer": ISSUER, "jwks_uri": "http://attacker.example.com/jwks"}),
    )
    with pytest.raises(AuthenticationError, match="unsafe"):
        v._discover_jwks_uri()


def test_discover_jwks_uri_accepts_a_matching_secure_document(monkeypatch):
    v = OIDCVerifier(issuer=ISSUER, audience=AUDIENCE)
    monkeypatch.setattr(
        "security.identity.httpx.get",
        lambda *a, **k: _FakeHttpxResponse({"issuer": ISSUER, "jwks_uri": "https://test-issuer.invalid/jwks"}),
    )
    assert v._discover_jwks_uri() == "https://test-issuer.invalid/jwks"


def test_jwks_client_lifespan_matches_configured_jwks_cache_seconds(monkeypatch):
    # Found during a self-audit: PyJWKClient has its OWN independent
    # cache_jwk_set/lifespan (default 300s), separate from OIDCVerifier's
    # own jwks_cache_seconds-gated rebuild logic. Left unwired, a non-default
    # jwks_cache_seconds would look configured but the underlying signing
    # keys would silently still refresh on PyJWKClient's own 300s default.
    v = OIDCVerifier(issuer=ISSUER, audience=AUDIENCE, jwks_cache_seconds=3600)
    monkeypatch.setattr(
        "security.identity.httpx.get",
        lambda *a, **k: _FakeHttpxResponse({"issuer": ISSUER, "jwks_uri": "https://test-issuer.invalid/jwks"}),
    )
    client = v._get_jwks_client()
    assert client.jwk_set_cache is not None
    assert client.jwk_set_cache.lifespan == 3600


def test_verify_accepts_explicit_bearer_typ_claim(keypair, verifier):
    private_key, _ = keypair
    token = _make_token(private_key, extra_claims={"typ": "Bearer"})
    subject = verifier.verify(token)
    assert subject.subject_id == "user-1"


def test_verify_rejects_non_bearer_typ_claim(keypair, verifier):
    private_key, _ = keypair
    token = _make_token(private_key, extra_claims={"typ": "ID"})
    with pytest.raises(AuthenticationError, match="expected an access token"):
        verifier.verify(token)


def test_default_verifier_is_a_cached_singleton_per_process(monkeypatch):
    from security.identity import _default_verifier

    _default_verifier.cache_clear()
    monkeypatch.setenv("OIDC_ISSUER", "http://localhost:9999/realms/cache-test")
    monkeypatch.setenv("OIDC_AUDIENCE", "cache-test-audience")
    try:
        first = _default_verifier()
        second = _default_verifier()
        assert first is second
    finally:
        _default_verifier.cache_clear()
