"""Bearer-token authentication (AuthN only).

Verifies a Bearer JWT against a real, standards-compliant OIDC issuer's JWKS
(RFC 7517) via its discovery document (RFC 8414 / OpenID Connect Discovery):
signature, issuer, audience and expiry are all checked, informed by RFC 8725
(JWT Best Current Practices) and RFC 9700 (OAuth 2.0 Security BCP) -- an
unsigned, wrong-issuer, wrong-audience, wrong-algorithm or expired token is
always rejected, never accepted as a fallback. This is NOT a claim of full
RFC 9068 (JWT access-token profile) compliance: RFC 9068 mandates a header
`typ: at+jwt`, and this deployment's Keycloak does not set it. Instead,
`verify()` REQUIRES the payload-level `typ: Bearer` claim Keycloak always
sets on its access tokens (and never on ID tokens), as a practical,
Keycloak-specific mitigation against an ID token being replayed as an access
token. This is a real, deliberate restriction, not a general OIDC
guarantee: a token from a different, spec-conformant OIDC provider that
omits `typ` entirely would be rejected here, not silently accepted.

This module answers only "who verifiably sent this request, per the token".
It never turns that into an authorization decision, and it never treats its
`AuthenticatedSubject.subject_id` as equal to an application `players
.player_id` -- OIDC `sub` is unique only within its issuer.
security.rbac.resolve_bound_principal() is what turns a verified subject
into an actual local principal, through an explicit, administrator-created
binding; see LANE2_SYNC.md's Phase 2 contract for why the two must not be
conflated.

There is no government-approved IdP available (SIH26101_MASTER_CHECKLIST.md
section 5.1, BLOCKED-EXTERNAL). Keycloak in backend/docker-compose.dev.yml
is a real, local OIDC provider used to test this module honestly -- it is
not a claim of a production identity integration.
"""
from __future__ import annotations

import functools
import math
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
import jwt
from jwt import PyJWKClient

SUPPORTED_ALGORITHMS = ["RS256"]
DEFAULT_JWKS_CACHE_SECONDS = 300.0
DEFAULT_DISCOVERY_TIMEOUT_SECONDS = 5.0
_LOOPBACK_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}


def _require_nonblank_string(value: object, *, label: str) -> str:
    """Reject a non-string, boolean, or blank/whitespace-only value.

    `issuer`/`audience` used to be checked only with `if not issuer:`,
    which correctly rejects `None`/`""`/`[]`/`{}` (all falsy) but silently
    lets a TRUTHY non-string value like `True` or `123` through
    construction -- and `bool` is an `int` subclass, so `isinstance(True,
    str)` alone would not catch it either without also excluding `bool`
    explicitly. That value then reached `issuer.endswith("/")` a few lines
    later and raised a raw `AttributeError`, not the documented `ValueError`
    boundary this class promises at construction. A whitespace-only string
    (`"   "`) is also truthy and was accepted despite being meaningless.
    """
    if isinstance(value, bool) or not isinstance(value, str):
        raise ValueError(f"{label} must be a string, got {type(value).__name__}")
    if not value.strip():
        raise ValueError(f"{label} is required")
    return value


def _require_positive_finite_seconds(value: object, *, label: str) -> float:
    """Reject a non-numeric, boolean, NaN/infinite, or non-positive duration.

    Both `jwks_cache_seconds` and `discovery_timeout_seconds` used to be
    stored as given, with no validation at all. A NaN cache duration (e.g.
    from a misconfigured environment variable) would silently reach
    `int(self._jwks_cache_seconds)` inside `_get_jwks_client()` --
    `int(float('nan'))` raises a bare `ValueError`, which is not a
    `jwt.PyJWTError` and therefore was not caught by `verify()`'s exception
    boundary, leaking a raw `ValueError` in violation of this module's own
    "callers only ever see AuthenticationError" contract. Validating here,
    at construction, catches a bad value immediately and with a clear
    message instead of letting it surface later as a confusing crash deep
    inside token verification.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a real number of seconds, got {value!r}")
    if not math.isfinite(value):
        raise ValueError(f"{label} must be finite, got {value!r}")
    if value <= 0:
        raise ValueError(f"{label} must be positive, got {value!r}")
    return float(value)


def _require_safe_absolute_url(url: str, *, label: str) -> None:
    """Reject anything that isn't a plain, absolute `scheme://host[:port]/path`
    issuer or JWKS URL.

    Rejects a relative URL (no host), and rejects userinfo (`user:pass@host`),
    a query string, or a fragment -- all classic vectors for tricking a URL
    parser into treating a string as safe when a different parser (or a
    human) would read it differently. An OIDC issuer/JWKS URL has no
    legitimate reason to carry any of those.
    """
    # Python's urlparse() silently tolerates (and effectively strips) leading/
    # trailing whitespace and control characters when it determines scheme
    # and hostname -- confirmed directly, not assumed. That means a string
    # like " https://issuer.example/realm" parses as a clean, valid HTTPS
    # URL even though the raw value still carries the leading space, so the
    # exact-match check against a JWT's `iss` claim or the discovery
    # document's own issuer field would (usually) just fail later -- but
    # relying on THAT to catch it is exactly the parser-differential trap
    # this function exists to close. Reject any C0 control character, DEL,
    # or space anywhere in the string outright, before urlparse ever sees it.
    if any(ord(character) < 0x21 or ord(character) == 0x7F for character in url):
        raise ValueError(f"{label} must not contain whitespace or control characters (got {url!r})")

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.hostname:
        raise ValueError(f"{label} must be an absolute URL with a host (got {url!r})")
    if parsed.username or parsed.password:
        raise ValueError(f"{label} must not contain userinfo (got {url!r})")
    if parsed.query:
        raise ValueError(f"{label} must not contain a query string (got {url!r})")
    if parsed.fragment:
        raise ValueError(f"{label} must not contain a fragment (got {url!r})")
    try:
        parsed.port  # urlsplit/urlparse validate the port lazily, only on access
    except ValueError as exc:
        raise ValueError(f"{label} has an invalid port (got {url!r})") from exc

    if parsed.scheme == "https":
        return
    if parsed.scheme == "http" and parsed.hostname in _LOOPBACK_HOSTNAMES:
        return
    raise ValueError(
        f"{label} must use https, or http only for an explicit loopback host "
        f"for local dev (got {url!r})"
    )


class AuthenticationError(Exception):
    """Raised when a bearer token is missing, malformed, expired, or fails
    signature/issuer/audience verification. Callers must treat this as an
    unauthenticated request (HTTP 401), never partially trust the token."""


@dataclass(frozen=True)
class AuthenticatedSubject:
    """A verified external identity, exactly as asserted by its issuer.

    Nothing here is an application-level authorization decision. `roles` are
    IdP-asserted claims, not application permissions -- security.rbac must
    allowlist them before they mean anything (see effective_roles() there).
    """

    subject_id: str          # OIDC "sub" -- stable only within `issuer`. Never compared
                              # to players.player_id; see module docstring.
    username: str | None     # "preferred_username" -- display only, never an authorization key.
    roles: frozenset[str]    # raw asserted roles from "realm_access.roles". Unfiltered.
    issuer: str               # verified "iss" claim.
    expires_at: datetime      # verified "exp" claim, as a UTC datetime.
    raw_claims: dict[str, Any]  # full verified claim set, for anything not modeled explicitly.


class OIDCVerifier:
    """Verifies bearer tokens against one configured OIDC issuer.

    One instance per issuer. The JWKS client is cached and only re-fetched
    after `jwks_cache_seconds`, so normal request handling never re-fetches
    the discovery document or key set on every request -- but a rotated key
    is still picked up within that window without a restart.
    """

    def __init__(
        self,
        issuer: str,
        audience: str,
        jwks_cache_seconds: float = DEFAULT_JWKS_CACHE_SECONDS,
        discovery_timeout_seconds: float = DEFAULT_DISCOVERY_TIMEOUT_SECONDS,
    ) -> None:
        issuer = _require_nonblank_string(issuer, label="issuer")
        audience = _require_nonblank_string(audience, label="audience")
        jwks_cache_seconds = _require_positive_finite_seconds(
            jwks_cache_seconds, label="jwks_cache_seconds"
        )
        discovery_timeout_seconds = _require_positive_finite_seconds(
            discovery_timeout_seconds, label="discovery_timeout_seconds"
        )
        # No normalization: a trailing slash is rejected outright rather than
        # silently stripped. OIDC issuer identifiers are canonically written
        # without one (RFC 8414 / OIDC Discovery); silently rewriting
        # security-critical identity input -- even in a seemingly harmless
        # way -- masks real configuration mistakes instead of surfacing them.
        if issuer.endswith("/"):
            raise ValueError(
                f"issuer must not have a trailing slash -- configure it exactly "
                f"as the provider's canonical issuer identifier (got {issuer!r})"
            )
        _require_safe_absolute_url(issuer, label="issuer")
        self._issuer = issuer
        self._audience = audience
        self._jwks_cache_seconds = jwks_cache_seconds
        self._discovery_timeout_seconds = discovery_timeout_seconds
        self._jwks_client: PyJWKClient | None = None
        self._jwks_client_fetched_at = 0.0

    def _discover_jwks_uri(self) -> str:
        discovery_url = f"{self._issuer}/.well-known/openid-configuration"
        try:
            response = httpx.get(discovery_url, timeout=self._discovery_timeout_seconds)
            response.raise_for_status()
            document = response.json()
        except (httpx.HTTPError, httpx.InvalidURL) as exc:
            # httpx.InvalidURL does NOT subclass httpx.HTTPError (confirmed via
            # their MRO) -- it's a sibling under plain Exception. Construction
            # already rejects a malformed port before self._issuer can ever
            # reach this f-string, so this branch shouldn't be reachable
            # through the normal flow; it's here as a belt-and-suspenders
            # backstop so a future code path can never leak a bare httpx
            # exception in violation of "callers only ever see
            # AuthenticationError".
            raise AuthenticationError(
                f"could not reach OIDC discovery document at {discovery_url}: {exc}"
            ) from exc
        except ValueError as exc:  # json.JSONDecodeError subclasses ValueError
            raise AuthenticationError(
                f"OIDC discovery document at {discovery_url} is not valid JSON: {exc}"
            ) from exc

        if not isinstance(document, dict):
            raise AuthenticationError(
                f"OIDC discovery document at {discovery_url} is not a JSON object"
            )

        # OIDC Discovery 1.0 section 4.3: the document's own "issuer" MUST
        # exactly match the issuer used to locate it. Skipping this check is
        # exactly the kind of gap that enables an issuer-confusion attack via
        # a compromised or misconfigured discovery endpoint.
        document_issuer = document.get("issuer")
        if document_issuer != self._issuer:
            raise AuthenticationError(
                f"OIDC discovery document issuer {document_issuer!r} does not exactly "
                f"match the configured issuer {self._issuer!r}"
            )

        jwks_uri = document.get("jwks_uri")
        if not isinstance(jwks_uri, str) or not jwks_uri:
            raise AuthenticationError(
                f"OIDC discovery document at {discovery_url} has no jwks_uri"
            )
        try:
            _require_safe_absolute_url(jwks_uri, label="jwks_uri")
        except ValueError as exc:
            raise AuthenticationError(f"OIDC discovery document's jwks_uri is unsafe: {exc}") from exc
        return jwks_uri

    def _get_jwks_client(self) -> PyJWKClient:
        now = time.monotonic()
        stale = (now - self._jwks_client_fetched_at) > self._jwks_cache_seconds
        if self._jwks_client is None or stale:
            jwks_uri = self._discover_jwks_uri()
            # PyJWKClient has its OWN independent JWKS-fetch cache
            # (`cache_jwk_set`/`lifespan`, default 300s) on top of the
            # rebuild-the-client cache this method already implements. Left
            # unset, that inner cache silently uses its own 300s default
            # regardless of `jwks_cache_seconds` -- so a non-default value
            # here (e.g. an hour) would look configured but the underlying
            # signing keys would still get refetched every 300s anyway.
            # Passing `lifespan` explicitly keeps both layers in agreement.
            self._jwks_client = PyJWKClient(
                jwks_uri,
                timeout=self._discovery_timeout_seconds,
                lifespan=max(1, int(self._jwks_cache_seconds)),
            )
            self._jwks_client_fetched_at = now
        return self._jwks_client

    def verify(self, bearer_token: str) -> AuthenticatedSubject:
        """Verify signature, issuer, audience, algorithm and expiry. Raises
        AuthenticationError on any failure -- never returns a partially
        trusted subject."""
        if not bearer_token or not isinstance(bearer_token, str):
            raise AuthenticationError("bearer token is required")

        try:
            signing_key = self._get_jwks_client().get_signing_key_from_jwt(bearer_token)
            claims = jwt.decode(
                bearer_token,
                signing_key.key,
                algorithms=SUPPORTED_ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "iss", "sub"]},
            )
        except jwt.PyJWTError as exc:
            raise AuthenticationError(f"token verification failed: {exc}") from exc

        # `options={"require": [...]}` above only proves "sub" is PRESENT, not
        # that it's a usable value -- a token with `"sub": ""` would satisfy
        # that check and then flow through as an empty-string subject_id,
        # which is not a stable external identity key and could collide
        # ambiguously with another empty/malformed subject downstream.
        subject_claim = claims.get("sub")
        if not isinstance(subject_claim, str) or not subject_claim.strip():
            raise AuthenticationError("token 'sub' claim must be a non-empty string")

        # Keycloak-specific access-vs-ID-token discriminator (see module
        # docstring): REQUIRE the payload to assert itself as a Bearer access
        # token. A missing `typ` is rejected too, not treated as "unknown,
        # allow it" -- an absent claim is indistinguishable here from an ID
        # token, which never carries typ="Bearer", so treating "missing" as
        # "fine" would silently defeat the whole discrimination check this
        # exists for.
        token_type = claims.get("typ")
        if token_type != "Bearer":
            raise AuthenticationError(f"expected an access token (typ=Bearer), got typ={token_type!r}")

        # realm_access.roles must be a JSON array of strings, ALL of them --
        # not "salvage whichever entries happen to look like strings". A
        # cleanly-shaped list[str] is accepted whole; anything else (a dict,
        # a non-list, or a list with even one non-string entry) fails closed
        # to zero roles rather than partially trusting a malformed claim.
        # Cherry-picking the string-looking entries out of a malformed array
        # is not actually "failing closed" -- it's failing partially open,
        # and a privileged-looking string sitting in an otherwise-broken
        # array must not grant that role just because it happened to parse.
        realm_access = claims.get("realm_access")
        raw_roles = realm_access.get("roles") if isinstance(realm_access, dict) else None
        is_clean_string_list = isinstance(raw_roles, list) and all(
            isinstance(role, str) for role in raw_roles
        )
        roles = frozenset(raw_roles) if is_clean_string_list else frozenset()

        # jwt.decode() with options={"require": ["exp", ...]} only proves
        # "exp" is PRESENT, not that it is a usable numeric value -- e.g. a
        # numeric STRING exp ("1788269436") decodes and expiry-checks
        # successfully (PyJWT compares it as a string that happens to look
        # numeric), and an absurdly large integer exp can pass PyJWT's own
        # expiry check too. Both then reached datetime.fromtimestamp()
        # below, outside the try/except jwt.PyJWTError block above, and
        # raised a raw TypeError (non-numeric) or OverflowError (out of
        # platform time_t range) -- neither is a jwt.PyJWTError, so both
        # leaked past this module's "callers only ever see
        # AuthenticationError" boundary. Validate explicitly first.
        exp_claim = claims["exp"]
        if isinstance(exp_claim, bool) or not isinstance(exp_claim, (int, float)):
            raise AuthenticationError(
                f"token 'exp' claim must be a number, got {type(exp_claim).__name__}"
            )
        try:
            expires_at = datetime.fromtimestamp(exp_claim, tz=timezone.utc)
        except (OverflowError, OSError, ValueError) as exc:
            raise AuthenticationError(f"token 'exp' claim is out of range: {exc}") from exc

        return AuthenticatedSubject(
            subject_id=subject_claim,
            username=claims.get("preferred_username"),
            roles=roles,
            issuer=claims["iss"],
            expires_at=expires_at,
            raw_claims=claims,
        )


def verifier_from_env() -> OIDCVerifier:
    """Build an OIDCVerifier from OIDC_ISSUER / OIDC_AUDIENCE env vars.

    Raises AuthenticationError (not a bare KeyError/ValueError) so a missing
    configuration surfaces the same way an invalid token would to any code
    that only expects AuthenticationError from this module.
    """
    issuer = os.environ.get("OIDC_ISSUER")
    audience = os.environ.get("OIDC_AUDIENCE")
    if not issuer or not audience:
        raise AuthenticationError(
            "OIDC_ISSUER and OIDC_AUDIENCE must both be configured to verify bearer tokens"
        )
    return OIDCVerifier(issuer=issuer, audience=audience)


def extract_bearer_token(authorization_header: str | None) -> str:
    """Pull the token out of an `Authorization: Bearer <token>` header value.

    Takes the raw header value (not a request object) so this stays
    framework-agnostic -- FastAPI route wiring is Lane 5's job, not this
    module's.
    """
    if not authorization_header:
        raise AuthenticationError("missing Authorization header")
    scheme, _, token = authorization_header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AuthenticationError("Authorization header must be 'Bearer <token>'")
    return token


@functools.lru_cache(maxsize=1)
def _default_verifier() -> OIDCVerifier:
    """The process-wide default verifier, built once from the environment.

    Without this, every get_current_subject() call with no explicit
    `verifier` would build a brand new OIDCVerifier -- discarding its JWKS
    cache and re-running OIDC discovery on every single request, which
    defeats the whole point of OIDCVerifier's cache. Call
    `_default_verifier.cache_clear()` (tests only) if OIDC_ISSUER/
    OIDC_AUDIENCE change within a process lifetime.
    """
    return verifier_from_env()


def get_current_subject(
    authorization_header: str | None, verifier: OIDCVerifier | None = None
) -> AuthenticatedSubject:
    """Verify a raw `Authorization` header value and return the subject it
    proves. Pass `verifier` explicitly in tests/callers that already built
    one; omitted, this reuses one process-wide verifier built from
    OIDC_ISSUER/OIDC_AUDIENCE (see _default_verifier), not a fresh one per call."""
    token = extract_bearer_token(authorization_header)
    verifier = verifier or _default_verifier()
    return verifier.verify(token)
