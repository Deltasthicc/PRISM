"""Package 8 -- tests/scripts/lane2_doctor.py and
security.identity.OIDCVerifier.diagnose().

Uses the same real local-HTTP-server pattern as
test_core_identity.py::rotation_server for the offline mock-provider cases
(a genuine HTTP round trip, not a stubbed client), and a separate opt-in
check against the real local Keycloak container
(docker-compose.dev.yml/keycloak/README.md) for live verification -- skips
cleanly if that container isn't running, matching every other live-service
test in this suite.
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from scripts import lane2_doctor
from scripts.lane2_doctor import diagnose_oidc, diagnosis_to_dict, format_human
from security.identity import OIDCVerifier


def _real_rsa_jwk(kid: str) -> dict:
    """A genuinely valid RSA JWK (not a placeholder n/e pair, which PyJWT's
    RSA algorithm implementation correctly rejects as mathematically
    invalid -- confirmed by an earlier version of this fixture failing with
    "e must be >= 3 and < n")."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(RSAAlgorithm.to_jwk(private_key.public_key()))
    jwk["kid"] = kid
    jwk["use"] = "sig"
    jwk["alg"] = "RS256"
    return jwk


_FORBIDDEN_ANYWHERE = (
    "Bearer ",
    "client_secret",
    "access_token",
    "id_token",
    "refresh_token",
    "password",
)


class _MockOidcHandler(BaseHTTPRequestHandler):
    """Serves a discovery document + JWKS at class-configurable paths, or a
    404/connection-refused shape depending on the test. Class attributes are
    mutated per test rather than per instance -- matches
    test_core_identity.py's own `_RotatingDiscoveryHandler` pattern."""

    issuer = ""
    jwks_document: dict = {"keys": []}  # always overwritten by the mock_provider fixture below
    jwks_path = "/jwks"
    serve_jwks = True

    def log_message(self, format, *args):  # noqa: A002 - stdlib signature
        pass

    def do_GET(self):
        if self.path == "/.well-known/openid-configuration":
            body = json.dumps(
                {"issuer": self.issuer, "jwks_uri": f"{self.issuer}{self.jwks_path}"}
            ).encode()
        elif self.path == self.jwks_path and self.serve_jwks:
            body = json.dumps(self.jwks_document).encode()
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture
def mock_provider():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockOidcHandler)
    issuer = f"http://127.0.0.1:{server.server_port}"
    _MockOidcHandler.issuer = issuer
    _MockOidcHandler.jwks_document = {"keys": [_real_rsa_jwk("k1")]}
    _MockOidcHandler.jwks_path = "/jwks"
    _MockOidcHandler.serve_jwks = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield issuer
    finally:
        server.shutdown()
        thread.join(timeout=5)


# --- OIDCVerifier.diagnose() ------------------------------------------------


def test_diagnose_reports_reachable_with_key_count_against_a_real_server(mock_provider):
    verifier = OIDCVerifier(issuer=mock_provider, audience="unused")
    result = verifier.diagnose()
    assert result["discovery_reachable"] is True
    assert result["jwks_reachable"] is True
    assert result["jwks_key_count"] == 1
    assert result["error"] is None


def test_diagnose_reports_discovery_unreachable_for_a_closed_port():
    verifier = OIDCVerifier(issuer="http://127.0.0.1:1", audience="unused")
    result = verifier.diagnose()
    assert result["discovery_reachable"] is False
    assert result["jwks_reachable"] is False
    assert result["error"] is not None


def test_diagnose_reports_jwks_unreachable_when_discovery_ok_but_jwks_endpoint_missing(mock_provider):
    _MockOidcHandler.serve_jwks = False
    verifier = OIDCVerifier(issuer=mock_provider, audience="unused")
    result = verifier.diagnose()
    assert result["discovery_reachable"] is True
    assert result["jwks_reachable"] is False
    assert result["error"] is not None


def test_diagnose_never_raises_even_on_malformed_jwks_json(mock_provider):
    """A 200 response whose body isn't a real JWKS shape must produce a
    reported error, not an uncaught exception from PyJWT's own parser."""
    original_do_get = _MockOidcHandler.do_GET

    def _serve_garbage_jwks(self):
        if self.path == "/jwks":
            body = b"not a jwks document"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            original_do_get(self)

    _MockOidcHandler.do_GET = _serve_garbage_jwks
    try:
        verifier = OIDCVerifier(issuer=mock_provider, audience="unused")
        result = verifier.diagnose()  # must not raise
        assert result["jwks_reachable"] is False
        assert result["error"] is not None
    finally:
        _MockOidcHandler.do_GET = original_do_get


def test_diagnose_result_never_contains_secret_shaped_content(mock_provider):
    verifier = OIDCVerifier(issuer=mock_provider, audience="unused")
    serialized = json.dumps(verifier.diagnose())
    for forbidden in _FORBIDDEN_ANYWHERE:
        assert forbidden not in serialized


# --- diagnose_oidc() / CLI --------------------------------------------------


def test_diagnose_oidc_reports_unconfigured_when_issuer_missing():
    diagnosis = diagnose_oidc(env={})
    assert diagnosis.configured is False
    assert diagnosis.discovery_reachable is False
    assert "not configured" in diagnosis.error


def test_diagnose_oidc_rejects_a_trailing_slash_issuer_as_a_reportable_error():
    diagnosis = diagnose_oidc(env={"OIDC_ISSUER": "http://127.0.0.1:1/"})
    assert diagnosis.configured is True
    assert diagnosis.discovery_reachable is False
    assert "trailing slash" in diagnosis.error


def test_diagnose_oidc_reports_success_against_a_real_server(mock_provider):
    diagnosis = diagnose_oidc(env={"OIDC_ISSUER": mock_provider})
    assert diagnosis.configured is True
    assert diagnosis.discovery_reachable is True
    assert diagnosis.jwks_reachable is True
    assert diagnosis.jwks_key_count == 1
    assert diagnosis.error is None


def test_diagnosis_to_dict_and_format_human_do_not_raise(mock_provider):
    diagnosis = diagnose_oidc(env={"OIDC_ISSUER": mock_provider})
    payload = diagnosis_to_dict(diagnosis)
    assert payload["issuer"] == mock_provider
    rendered = format_human(diagnosis)
    assert "discovery_reachable: True" in rendered


def test_format_human_on_unconfigured_does_not_print_none_issuer():
    diagnosis = diagnose_oidc(env={})
    rendered = format_human(diagnosis)
    assert "not configured" in rendered
    assert "issuer: None" not in rendered


def test_main_json_exits_zero_on_success(monkeypatch, mock_provider, capsys):
    monkeypatch.setenv("OIDC_ISSUER", mock_provider)
    exit_code = lane2_doctor._main(["--json"])
    assert exit_code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["discovery_reachable"] is True
    assert parsed["jwks_reachable"] is True


def test_main_exits_nonzero_when_not_configured(monkeypatch, capsys):
    monkeypatch.delenv("OIDC_ISSUER", raising=False)
    exit_code = lane2_doctor._main([])
    assert exit_code == 1
    capsys.readouterr()


def test_main_exits_nonzero_when_unreachable(monkeypatch, capsys):
    monkeypatch.setenv("OIDC_ISSUER", "http://127.0.0.1:1")
    exit_code = lane2_doctor._main([])
    assert exit_code == 1
    capsys.readouterr()


def test_diagnose_oidc_accepts_no_player_or_free_text_argument_of_any_kind():
    """Executable documentation, matching database_status.py's
    `get_database_status` equivalent: this function's signature has no
    parameter that could be pointed at one subject or one free-text filter."""
    import inspect

    parameters = inspect.signature(diagnose_oidc).parameters
    assert set(parameters) == {"env"}


# --- Live Keycloak (opt-in) --------------------------------------------------


def test_diagnose_against_real_local_keycloak():
    """Opt-in: connects to the real local Keycloak container documented in
    backend/keycloak/README.md. Skips cleanly, not failed, if it isn't
    running -- matching every other live-service test in this suite."""
    issuer = "http://localhost:8180/realms/prism"
    try:
        httpx.get(f"{issuer}/.well-known/openid-configuration", timeout=2.0)
    except httpx.HTTPError as exc:
        pytest.skip(f"Real local Keycloak not reachable at {issuer} -- skipping: {exc}")

    diagnosis = diagnose_oidc(env={"OIDC_ISSUER": issuer})
    assert diagnosis.configured is True
    assert diagnosis.discovery_reachable is True
    assert diagnosis.jwks_reachable is True
    assert diagnosis.jwks_key_count is not None and diagnosis.jwks_key_count >= 1
    assert diagnosis.error is None
