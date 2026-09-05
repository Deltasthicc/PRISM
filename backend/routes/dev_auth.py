"""Local-development-only bridge between the demo username login and a real
verified OIDC bearer token.

Why this exists: `routes/learning_*.py` correctly requires a verified
`BoundPrincipal` (Package Z / the Lane 2 composed authorization dependency).
The frontend's demo login (`POST /game/player/create`, `POST
/game/player/by-username/{username}`) is username-only, with no password and
no token -- it never has, and that gap is already documented in README.md
and SIH26101_MASTER_CHECKLIST.md section 5.1 as open, Lane 1/5-owned browser
Authorization Code + PKCE work. Building that real flow is out of scope
here.

What this route does instead, only for local development: it exchanges the
just-created/just-logged-in demo `player_id` for a REAL Keycloak access
token (Resource Owner Password Credentials grant, against the same
`prism-backend-dev` client `backend/keycloak/README.md` already documents
for minting a token by hand), verifies that token through the exact same
`get_current_subject()` this deployment already uses for every other
request, and then points a single reusable local identity binding at
whichever `player_id` just logged in. The frontend can then attach the
returned token as a real `Authorization: Bearer` header.

This is NOT a login backdoor: the token is always a genuine, fully verified
Keycloak-issued JWT (signature, issuer, audience, expiry all checked exactly
as for any other request) -- nothing here weakens `security/identity.py` or
`security/rbac.py`. What is dev-only is the identity *binding*: normally a
binding is created once, out-of-band, by an operator
(`security/identity_bootstrap.py`). This route creates/repoints one
automatically so a single local developer clicking through the demo site
doesn't have to run that CLI by hand for every player they create. It always
grants exactly the `learner` role (the fixed Keycloak `demo-learner`
account's real realm role), matching what an ordinary demo player should
have -- never an elevated role.

Disabled by default. Only mounted at all when `ENABLE_DEV_LOGIN` is
explicitly truthy (see `main.py`) -- omitted entirely from the OpenAPI
surface and unroutable otherwise, not just permission-gated, so it cannot be
mistaken for a documented production endpoint.
"""
from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db
from models.identity import IdentityBinding
from security.identity import AuthenticationError, get_current_subject

router = APIRouter(prefix="/auth", tags=["Local Dev Login"])

# Render's free tier fully spins the Keycloak service down after a period of
# inactivity -- confirmed directly: a cold-start request measured at 335s
# before responding. 5s (this constant's original value) meant every cold
# -start login silently fell back to no-token mode instead of actually
# waiting, which then made every /learning/* call 401 and looked like a
# broken app rather than a slow-but-working one. 450s gives real margin
# above the measured worst case. This does mean a genuinely cold login can
# take several minutes -- upgrading prism-keycloak to a paid Render tier
# (no spin-down) is the real fix for that UX cost; this change only fixes
# the correctness bug of giving up before the service was actually reachable.
_TOKEN_REQUEST_TIMEOUT_SECONDS = 450.0


class DevLoginRequest(BaseModel):
    player_id: str = Field(..., min_length=1, max_length=100)


class DevLoginResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    role: str
    note: str = (
        "Local-dev-only token, minted via a real Keycloak Resource Owner "
        "Password grant against the fixed demo-learner account -- not a "
        "production login."
    )


def _dev_login_config() -> dict[str, str]:
    """Read the six env vars this route needs, or refuse clearly if any are missing."""
    required = {
        "token_url": os.environ.get("KEYCLOAK_DEV_TOKEN_URL"),
        "client_id": os.environ.get("KEYCLOAK_DEV_CLIENT_ID"),
        "client_secret": os.environ.get("KEYCLOAK_DEV_CLIENT_SECRET"),
        "username": os.environ.get("KEYCLOAK_DEV_USERNAME", "demo-learner"),
        "password": os.environ.get("KEYCLOAK_DEV_PASSWORD"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise HTTPException(
            status_code=503,
            detail=(
                "Local dev login is enabled but not configured -- missing "
                f"env var(s) for: {', '.join(missing)}. See backend/keycloak/README.md "
                "and .env.example."
            ),
        )
    return required


@router.post("/dev-login", response_model=DevLoginResponse)
def dev_login(body: DevLoginRequest, db: Session = Depends(get_db)) -> DevLoginResponse:
    config = _dev_login_config()

    try:
        token_response = httpx.post(
            config["token_url"],
            data={
                "grant_type": "password",
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "username": config["username"],
                "password": config["password"],
                "scope": "openid",
            },
            timeout=_TOKEN_REQUEST_TIMEOUT_SECONDS,
        )
        token_response.raise_for_status()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not reach the local Keycloak dev instance -- is it running? "
                "`docker compose -f docker-compose.dev.yml up -d --wait` from backend/."
            ),
        ) from exc

    payload = token_response.json()
    access_token = payload.get("access_token")
    expires_in = payload.get("expires_in", 0)
    if not access_token:
        raise HTTPException(
            status_code=503,
            detail="Keycloak's token response did not include an access_token.",
        )

    # Verify the token through the exact same path every other request uses --
    # this route never trusts Keycloak's response blindly, and never invents
    # or reads claims out of the token by hand.
    try:
        subject = get_current_subject(f"Bearer {access_token}")
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Minted token failed this deployment's own verification: {exc}",
        ) from exc

    existing = (
        db.query(IdentityBinding)
        .filter(
            IdentityBinding.issuer == subject.issuer,
            IdentityBinding.subject_id == subject.subject_id,
            IdentityBinding.active.is_(True),
        )
        .one_or_none()
    )
    if existing is not None:
        existing.player_id = body.player_id
    else:
        db.add(
            IdentityBinding(
                issuer=subject.issuer,
                subject_id=subject.subject_id,
                player_id=body.player_id,
                active=True,
            )
        )
    db.commit()

    role = next(iter(subject.roles), "learner")
    return DevLoginResponse(access_token=access_token, expires_in=expires_in, role=role)
