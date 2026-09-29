"""SIH26075 CC-01/CC-10: self-service signup with a requested role, plus
admin approval before a new account can act.

Two distinct trust boundaries meet in this file, and every route below is
built to keep them separate:

1. **Authentication** (proven by a real Keycloak-verified bearer token,
   `security.identity.get_current_subject`) -- required by every route
   here, including registration itself. A brand-new registrant must still
   have logged into Keycloak at least once (e.g. as one of the fixed
   `demo-*` accounts in local dev, or a real IdP account in production)
   before they can register a PRISM account; this route never accepts an
   unverified identity.
2. **Authorization** (`security.rbac`) -- ``POST /auth/register`` composes
   only #1 (`Depends(get_current_subject)`), deliberately NOT
   `require_principal`, because `require_principal` requires an *existing*
   active binding a new registrant does not have yet. Every other route
   here requires a full `BoundPrincipal` with `Permission.
   IDENTITY_BINDING_MANAGE` (held only by `organization_admin`).

See `security/rbac.py`'s `create_self_service_registration` /
`decide_self_registration` docstrings for what "approval" does and does not
grant -- it activates the local binding, it never mints or elevates a role
claim in the underlying token.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db
from models.identity import SELF_SERVICE_REQUESTABLE_ROLES
from routes.authorization import require_permission_dependency
from security.identity import AuthenticationError, get_current_subject
from security.rbac import (
    AuthorizationError,
    BoundPrincipal,
    IdentityBindingConflict,
    Permission,
    PrincipalBindingError,
    create_self_service_registration,
    decide_self_registration,
    list_pending_registrations,
)

router = APIRouter(prefix="/auth", tags=["Registration"])


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=200)
    requested_role: str = Field(..., description="One of: " + ", ".join(sorted(SELF_SERVICE_REQUESTABLE_ROLES)))
    designation: str = Field("", max_length=200)
    department: str = Field("", max_length=200)
    notes: str = Field("", max_length=1000, description="Optional note for the reviewing admin")


class RegistrationResponse(BaseModel):
    binding_id: str
    player_id: str | None
    requested_role: str
    status: str = "pending"
    note: str = (
        "Your account has been created and is pending admin approval. "
        "You will be able to sign in with full access once approved."
    )


class PendingRegistrationSummary(BaseModel):
    binding_id: str
    player_id: str | None
    requested_role: str
    registration_notes: str | None
    created_at: datetime


class RegistrationDecisionRequest(BaseModel):
    decision: str = Field(..., description="'approved' or 'rejected'")
    notes: str = Field("", max_length=1000)


class RegistrationDecisionResponse(BaseModel):
    binding_id: str
    requested_role: str
    decision: str
    active: bool


def _verified_subject(authorization: str | None = Header(default=None)):
    """A verified OIDC subject, with no requirement that a binding already
    exists -- the one route in this file that must accept an otherwise-
    unbound caller. Still real, signature/issuer/audience-verified
    authentication; never a weaker check than `require_principal` uses."""
    try:
        return get_current_subject(authorization)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


@router.post("/register", response_model=RegistrationResponse)
def register(
    body: RegisterRequest,
    subject=Depends(_verified_subject),
    db: Session = Depends(get_db),
) -> RegistrationResponse:
    if body.requested_role not in SELF_SERVICE_REQUESTABLE_ROLES:
        raise HTTPException(
            status_code=422,
            detail=f"requested_role must be one of {sorted(SELF_SERVICE_REQUESTABLE_ROLES)}",
        )
    try:
        binding = create_self_service_registration(
            db,
            subject=subject,
            username=body.username,
            requested_role=body.requested_role,
            full_name=body.full_name,
            designation=body.designation,
            department=body.department,
            notes=body.notes,
        )
    except IdentityBindingConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AuthorizationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RegistrationResponse(
        binding_id=binding.binding_id,
        player_id=binding.player_id,
        requested_role=binding.requested_role,
    )


@router.get("/pending-registrations", response_model=list[PendingRegistrationSummary])
def get_pending_registrations(
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.IDENTITY_BINDING_MANAGE)
    ),
    db: Session = Depends(get_db),
) -> list[PendingRegistrationSummary]:
    pending = list_pending_registrations(db, actor=principal)
    return [
        PendingRegistrationSummary(
            binding_id=binding.binding_id,
            player_id=binding.player_id,
            requested_role=binding.requested_role,
            registration_notes=binding.registration_notes,
            created_at=binding.created_at,
        )
        for binding in pending
    ]


@router.post(
    "/pending-registrations/{binding_id}/decide",
    response_model=RegistrationDecisionResponse,
)
def decide_registration(
    binding_id: str,
    body: RegistrationDecisionRequest,
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.IDENTITY_BINDING_MANAGE)
    ),
    db: Session = Depends(get_db),
) -> RegistrationDecisionResponse:
    try:
        binding = decide_self_registration(
            db,
            actor=principal,
            binding_id=binding_id,
            decision=body.decision,
            notes=body.notes,
        )
    except PrincipalBindingError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AuthorizationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return RegistrationDecisionResponse(
        binding_id=binding.binding_id,
        requested_role=binding.requested_role,
        decision=binding.registration_decision,
        active=binding.active,
    )
