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
from models.learning import LearnerProfile
from models.player import Player
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
    resolve_subject_registration_status,
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
    # What the applicant declared about themselves, so an administrator can
    # decide on more than an opaque id. All self-declared and unverified.
    username: str | None = None
    full_name: str = ""
    designation: str = ""
    department: str = ""
    # The identity-provider account behind the request. Approving only
    # activates the local binding; the matching role must still be granted to
    # this subject in the identity provider before it has any permissions.
    issuer: str
    subject_id: str


class RegistrationDecisionRequest(BaseModel):
    decision: str = Field(..., description="'approved' or 'rejected'")
    notes: str = Field("", max_length=1000)


class RegistrationDecisionResponse(BaseModel):
    binding_id: str
    requested_role: str
    decision: str
    active: bool


class MeResponse(BaseModel):
    status: str  # "not_registered" | "pending_approval" | "rejected" | "approved"
    player_id: str | None
    username: str | None
    roles: list[str]
    requested_role: str | None


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


@router.get("/me", response_model=MeResponse)
def me(
    subject=Depends(_verified_subject),
    db: Session = Depends(get_db),
) -> MeResponse:
    """The real principal-hydration endpoint a live audit this session
    found missing: the frontend had no reliable way to tell a first-time
    registrant, a pending applicant, a rejected one, and an already-
    approved returning user apart after a real OIDC sign-in -- every case
    was routed through the same registration form. This is a verified-
    subject read, same trust boundary as POST /register, never requiring
    an existing active binding (unlike every other route in this file).
    """
    result = resolve_subject_registration_status(db, subject)
    return MeResponse(
        status=result.status,
        player_id=result.player_id,
        username=result.username,
        roles=sorted(result.roles),
        requested_role=result.requested_role,
    )


@router.get("/pending-registrations", response_model=list[PendingRegistrationSummary])
def get_pending_registrations(
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.IDENTITY_BINDING_MANAGE)
    ),
    db: Session = Depends(get_db),
) -> list[PendingRegistrationSummary]:
    pending = list_pending_registrations(db, actor=principal)
    player_ids = [binding.player_id for binding in pending if binding.player_id]
    usernames = {
        player_id: username
        for player_id, username in db.query(Player.player_id, Player.username)
        .filter(Player.player_id.in_(player_ids))
        .all()
    }
    profiles = {
        profile.player_id: profile
        for profile in db.query(LearnerProfile).filter(LearnerProfile.player_id.in_(player_ids)).all()
    }
    return [
        PendingRegistrationSummary(
            binding_id=binding.binding_id,
            player_id=binding.player_id,
            requested_role=binding.requested_role,
            registration_notes=binding.registration_notes,
            created_at=binding.created_at,
            username=usernames.get(binding.player_id),
            full_name=getattr(profiles.get(binding.player_id), "full_name", "") or "",
            designation=getattr(profiles.get(binding.player_id), "designation", "") or "",
            department=getattr(profiles.get(binding.player_id), "department", "") or "",
            issuer=binding.issuer,
            subject_id=binding.subject_id,
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
