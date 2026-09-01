"""Adversarial AuthN exception-boundary checks for Package R.

These tests are separate from Claude Code's Package P identity tests.  They
exercise malformed but signed/configured inputs that must fail at the public
boundary rather than leaking incidental Python/PyJWT exception types.
"""
from __future__ import annotations

import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from security.identity import AuthenticationError, OIDCVerifier


ISSUER = "https://test-issuer.invalid/realms/test"
AUDIENCE = "sih-backend-test"


class _StubJWKClient:
    def __init__(self, public_key):
        self._public_key = public_key

    def get_signing_key_from_jwt(self, token):
        return SimpleNamespace(key=self._public_key)


@pytest.mark.parametrize("issuer", [True, 123, [], {}, None])
def test_oidc_verifier_rejects_non_string_issuer_at_construction(issuer):
    with pytest.raises(ValueError, match="issuer"):
        OIDCVerifier(issuer=issuer, audience=AUDIENCE)  # type: ignore[arg-type]


@pytest.mark.parametrize("audience", [True, 123, [], {}, None, "", "   "])
def test_oidc_verifier_rejects_non_string_or_blank_audience_at_construction(audience):
    with pytest.raises(ValueError, match="audience"):
        OIDCVerifier(issuer=ISSUER, audience=audience)  # type: ignore[arg-type]


@pytest.mark.parametrize("invalid_exp", [str(int(time.time()) + 300), 10**100])
def test_signed_token_with_unusable_exp_never_leaks_raw_python_error(
    invalid_exp, monkeypatch
):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    verifier = OIDCVerifier(issuer=ISSUER, audience=AUDIENCE)
    monkeypatch.setattr(
        verifier,
        "_get_jwks_client",
        lambda: _StubJWKClient(private_key.public_key()),
    )
    now = int(time.time())
    token = jwt.encode(
        {
            "iss": ISSUER,
            "sub": "package-r-user",
            "aud": AUDIENCE,
            "iat": now,
            "exp": invalid_exp,
            "typ": "Bearer",
            "realm_access": {"roles": ["learner"]},
        },
        private_key,
        algorithm="RS256",
        headers={"kid": "package-r-key"},
    )

    with pytest.raises(AuthenticationError):
        verifier.verify(token)

