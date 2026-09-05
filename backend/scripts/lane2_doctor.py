"""Privacy-safe operator network diagnostics -- Package 8.

Distinct from `scripts/database_status.py` (schema/row-count/env-flag
status, no network calls) -- this tool answers a different "why isn't this
working" question: is the configured OIDC provider actually reachable and
serving a well-formed discovery document and key set. It optionally makes
real HTTP calls, under a strict timeout, and never mints, verifies or
persists an identity -- it never handles a bearer token, a claim, or a
player/subject value of any kind.

Design constraints (all load-bearing, not stylistic, matching
`database_status.py`'s own):

- Every value this module reports is a boolean, a short error string, a URL
  (the configured issuer only -- never a JWKS/discovery document's own
  content) or a key count -- never a token, a claim, a connection string, or
  any other secret. `security.identity.OIDCVerifier.diagnose()` is the
  underlying primitive this wraps; see its own docstring for the same
  guarantee at the source.
- This module never accepts a player_id, subject id or free-text filter of
  any kind -- there is no code path here that can be pointed at one
  subject, exactly like `database_status.py`.
- A strict, short timeout on every network call (`OIDCVerifier`'s own
  `discovery_timeout_seconds`, default 5s) -- an operator running this
  interactively should never be left waiting on a hung connection.
- OIDC_ISSUER not being configured is a reportable fact, not a crash: this
  is meant to answer "why isn't OIDC working," and "it isn't configured at
  all" is one of the answers, not an exception to handle specially.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from security.identity import OIDCVerifier

# Audience is inert for a discovery/JWKS-only check (see
# OIDCVerifier.diagnose()'s own docstring) -- this placeholder is never sent
# anywhere or compared against anything, only required by the constructor's
# signature.
_DIAGNOSE_ONLY_PLACEHOLDER_AUDIENCE = "lane2-doctor-diagnose-only-unused-audience"


@dataclass(frozen=True)
class OidcDiagnosis:
    generated_at: str
    configured: bool
    issuer: str | None
    discovery_reachable: bool
    jwks_reachable: bool
    jwks_key_count: int | None
    error: str | None


def diagnose_oidc(env: dict[str, str] | None = None) -> OidcDiagnosis:
    """Read `OIDC_ISSUER` from `env` (defaults to `os.environ`) and report
    whether it's configured, reachable, and serving a usable key set.
    Never raises -- an unreachable or misconfigured issuer is a normal,
    reportable result, not this function's own failure."""
    source = env if env is not None else os.environ
    issuer = source.get("OIDC_ISSUER", "").strip()
    generated_at = datetime.now(timezone.utc).isoformat()

    if not issuer:
        return OidcDiagnosis(
            generated_at=generated_at,
            configured=False,
            issuer=None,
            discovery_reachable=False,
            jwks_reachable=False,
            jwks_key_count=None,
            error="OIDC_ISSUER is not configured",
        )

    try:
        verifier = OIDCVerifier(issuer=issuer, audience=_DIAGNOSE_ONLY_PLACEHOLDER_AUDIENCE)
    except ValueError as exc:
        # A malformed issuer (trailing slash, unsafe URL) is exactly the
        # kind of configuration mistake this tool exists to surface --
        # report it the same way an unreachable one would be, not as an
        # uncaught exception.
        return OidcDiagnosis(
            generated_at=generated_at,
            configured=True,
            issuer=issuer,
            discovery_reachable=False,
            jwks_reachable=False,
            jwks_key_count=None,
            error=str(exc),
        )

    result = verifier.diagnose()
    return OidcDiagnosis(
        generated_at=generated_at,
        configured=True,
        issuer=result["issuer"],
        discovery_reachable=result["discovery_reachable"],
        jwks_reachable=result["jwks_reachable"],
        jwks_key_count=result["jwks_key_count"],
        error=result["error"],
    )


def diagnosis_to_dict(diagnosis: OidcDiagnosis) -> dict:
    return asdict(diagnosis)


def format_human(diagnosis: OidcDiagnosis) -> str:
    lines = [f"generated_at: {diagnosis.generated_at}"]
    if not diagnosis.configured:
        lines.append("OIDC_ISSUER: not configured")
        return "\n".join(lines)
    lines.append(f"issuer: {diagnosis.issuer}")
    lines.append(f"discovery_reachable: {diagnosis.discovery_reachable}")
    lines.append(f"jwks_reachable: {diagnosis.jwks_reachable}")
    lines.append(f"jwks_key_count: {diagnosis.jwks_key_count if diagnosis.jwks_key_count is not None else 'n/a'}")
    if diagnosis.error:
        lines.append(f"error: {diagnosis.error}")
    return "\n".join(lines)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Machine-readable JSON output")
    args = parser.parse_args(argv)

    diagnosis = diagnose_oidc()

    if args.json:
        print(json.dumps(diagnosis_to_dict(diagnosis), indent=2, sort_keys=True))
    else:
        print(format_human(diagnosis))

    if not diagnosis.configured or not diagnosis.discovery_reachable or not diagnosis.jwks_reachable:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
