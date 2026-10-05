"""Fail-closed authorization over verified OIDC subjects.

Authentication and authorization stay separate: ``security.identity`` verifies
the bearer token, while this module allowlists application roles, resolves the
issuer-scoped subject through local persistence, and enforces object scope.
Nothing here is an HTTP route and no browser-supplied player or tenant value is
treated as authority.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Callable, Protocol
from urllib.parse import urlsplit

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.identity import SELF_SERVICE_REQUESTABLE_ROLES, IdentityBinding
from models.learning import LearnerProfile
from models.player import Player
from security.audit import record_audit_event


DEPLOYMENT_TENANT_SCOPE = "deployment-database"

ROLE_NAMES = frozenset(
    {
        "learner",
        "trainer",
        "content_reviewer",
        "department_admin",
        "organization_admin",
        "auditor",
    }
)


class Permission(StrEnum):
    PLAYER_SELF_READ = "player.self.read"
    PLAYER_SELF_WRITE = "player.self.write"
    PROFILE_SELF_READ = "profile.self.read"
    PROFILE_SELF_WRITE = "profile.self.write"
    ASSESSMENT_SELF_READ = "assessment.self.read"
    ASSESSMENT_SELF_WRITE = "assessment.self.write"
    PATHWAY_SELF_READ = "pathway.self.read"
    PRACTICE_SELF_WRITE = "practice.self.write"
    CONTENT_DRAFT_CREATE = "content.draft.create"
    CONTENT_REVIEW = "content.review"
    CONTENT_APPROVE = "content.approve"
    COURSE_READ = "course.read"
    COURSE_MANAGE = "course.manage"
    CERTIFICATE_READ = "certificate.read"
    COURSE_FEEDBACK_WRITE = "course_feedback.write"
    COHORT_MANAGE = "cohort.manage"
    COHORT_READ = "cohort.read"
    QUESTIONNAIRE_MANAGE = "questionnaire.manage"
    QUESTIONNAIRE_ATTEMPT = "questionnaire.attempt"
    DEPARTMENT_ANALYTICS_READ = "analytics.department.read"
    ORGANIZATION_ANALYTICS_READ = "analytics.organization.read"
    ROLE_TARGET_MANAGE = "role_target.manage"
    IDENTITY_BINDING_MANAGE = "identity_binding.manage"
    AUDIT_READ = "audit.read"
    SUBJECT_DATA_EXPORT = "subject_data.export"
    SUBJECT_DATA_DELETE = "subject_data.delete"


ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    "learner": frozenset(
        {
            Permission.PLAYER_SELF_READ,
            Permission.PLAYER_SELF_WRITE,
            Permission.PROFILE_SELF_READ,
            Permission.PROFILE_SELF_WRITE,
            Permission.ASSESSMENT_SELF_READ,
            Permission.ASSESSMENT_SELF_WRITE,
            Permission.PATHWAY_SELF_READ,
            Permission.PRACTICE_SELF_WRITE,
            Permission.CONTENT_DRAFT_CREATE,
            Permission.COURSE_READ,
            Permission.CERTIFICATE_READ,
            Permission.COURSE_FEEDBACK_WRITE,
            Permission.QUESTIONNAIRE_ATTEMPT,
        }
    ),
    # Cross-learner trainer access used to be deliberately absent here
    # pending a server-side trainer/cohort assignment model -- that model
    # now exists (models/cohort.py, routes/cohorts.py). COHORT_READ is
    # still not "see any learner": routes/cohorts.py additionally checks
    # the requesting trainer owns the specific cohort before returning
    # anything, the same ownership-check pattern
    # require_own_player_dependency already establishes for players and
    # routes/course_catalog.py established for courses. A role name alone
    # is still never object scope.
    "trainer": frozenset(
        {
            # A trainer-only account (no "learner" role alongside it) could
            # not read or edit even its own generic profile before this --
            # confirmed by reading this set, not assumed. PS75-07 requires
            # trainers to manage their own profile; a trainer authenticated
            # purely as "trainer" needs these same self-scoped permissions
            # a learner already has, not a separate trainer-profile
            # permission family (the underlying player/profile rows are
            # shared, not role-specific).
            Permission.PLAYER_SELF_READ,
            Permission.PLAYER_SELF_WRITE,
            Permission.PROFILE_SELF_READ,
            Permission.PROFILE_SELF_WRITE,
            Permission.CONTENT_DRAFT_CREATE,
            Permission.COURSE_READ,
            Permission.COURSE_MANAGE,
            Permission.CERTIFICATE_READ,
            Permission.COURSE_FEEDBACK_WRITE,
            Permission.COHORT_READ,
            Permission.QUESTIONNAIRE_MANAGE,
        }
    ),
    "content_reviewer": frozenset(
        {Permission.CONTENT_REVIEW, Permission.CONTENT_APPROVE}
    ),
    # No department key/scope exists in the schema yet. Keep the named role
    # recognized but grant it nothing until server-derived department scope
    # and negative row-filter tests exist.
    "department_admin": frozenset(),
    "organization_admin": frozenset(
        {
            Permission.ORGANIZATION_ANALYTICS_READ,
            Permission.ROLE_TARGET_MANAGE,
            Permission.IDENTITY_BINDING_MANAGE,
            Permission.SUBJECT_DATA_EXPORT,
            Permission.SUBJECT_DATA_DELETE,
            Permission.COHORT_MANAGE,
            Permission.COHORT_READ,
            Permission.QUESTIONNAIRE_MANAGE,
        }
    ),
    "auditor": frozenset({Permission.AUDIT_READ, Permission.SUBJECT_DATA_EXPORT}),
}


class AuthenticatedSubjectLike(Protocol):
    subject_id: str
    issuer: str
    roles: frozenset[str]


@dataclass(frozen=True)
class BoundPrincipal:
    """A verified external identity resolved to this deployment's local data."""

    subject: AuthenticatedSubjectLike
    binding_id: str
    player_id: str | None
    roles: frozenset[str]
    tenant_scope: str = DEPLOYMENT_TENANT_SCOPE

    @property
    def audit_actor(self) -> str:
        """A stable, unambiguous audit-log identity for this principal.

        A plain `f"{issuer}|{subject_id}"` join (the original shape here) is
        not injective: `validate_issuer()` only rejects control characters,
        not a literal `|`, and `security.identity.verify()` accepts any
        non-empty string as `sub`. Two different (issuer, subject_id) pairs
        could in principle collide into the same joined string. This is a
        narrow risk today (one issuer per deployment, so only subject_id
        varies), but the codebase already fixed the identical pattern in
        `identity_bootstrap.expected_bootstrap_confirmation()` -- use the
        same canonical JSON encoding here for consistency and genuine
        collision-freedom rather than relying on today's single-issuer
        deployment shape to make it safe.
        """
        return json.dumps(
            {"issuer": self.subject.issuer, "subject_id": self.subject.subject_id},
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        )


class AuthorizationError(PermissionError):
    """Base class for a fail-closed authorization decision."""


class PrincipalBindingError(AuthorizationError):
    """A verified OIDC subject has no active local binding."""


class IdentityBindingConflict(AuthorizationError):
    """The requested subject/player binding conflicts with an existing row."""


def _required(value: str, name: str, maximum: int = 500) -> str:
    if not isinstance(value, str):
        raise AuthorizationError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise AuthorizationError(f"{name} is required")
    if len(normalized) > maximum:
        raise AuthorizationError(f"{name} exceeds {maximum} characters")
    return normalized


def validate_issuer(value: str) -> str:
    """Validate and return an exact issuer URL for persisted identity keys."""
    issuer = _required(value, "issuer")
    if issuer != value:
        raise AuthorizationError("issuer must match the verified value exactly")
    if any(ord(character) < 0x21 or ord(character) == 0x7F for character in issuer):
        raise AuthorizationError("issuer must not contain whitespace or control characters")
    parsed = urlsplit(issuer)
    try:
        parsed.port
    except ValueError as exc:
        raise AuthorizationError("issuer port is invalid") from exc
    local_http = parsed.scheme == "http" and parsed.hostname in {
        "localhost",
        "127.0.0.1",
        "::1",
    }
    if parsed.scheme != "https" and not local_http:
        raise AuthorizationError("issuer must use HTTPS except on loopback development")
    if (
        not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise AuthorizationError(
            "issuer must be an absolute URL without userinfo, query or fragment"
        )
    return issuer


def effective_roles(subject: AuthenticatedSubjectLike) -> frozenset[str]:
    """Return only application roles from the verified token assertion."""
    return frozenset(role for role in subject.roles if role in ROLE_NAMES)


def resolve_bound_principal(
    db: Session, subject: AuthenticatedSubjectLike
) -> BoundPrincipal:
    """Resolve exact ``(issuer, sub)`` through an active local binding."""
    issuer = validate_issuer(subject.issuer)
    subject_id = _required(subject.subject_id, "subject_id")
    binding = (
        db.query(IdentityBinding)
        .filter(
            IdentityBinding.issuer == issuer,
            IdentityBinding.subject_id == subject_id,
            IdentityBinding.active.is_(True),
        )
        .one_or_none()
    )
    if binding is None:
        raise PrincipalBindingError("verified subject has no active local binding")
    return BoundPrincipal(
        subject=subject,
        binding_id=binding.binding_id,
        player_id=binding.player_id,
        roles=effective_roles(subject),
    )


@dataclass(frozen=True)
class SubjectRegistrationStatus:
    """What `GET /auth/me` (routes/registration.py) reports back to a
    verified-but-not-necessarily-bound caller -- purely informational,
    never an authorization decision. A caller with "pending_approval" or
    "rejected" status still holds zero permissions; this exists only so
    the frontend can route them to the right screen instead of a bare
    403/404 with no explanation, closing the real gap a live audit this
    session found: the OIDC callback had no way to tell a first-time
    registrant from an already-approved returning user, so a returning
    user with a perfectly valid, active binding was being routed back
    through the registration form every time.
    """

    status: str  # "not_registered" | "pending_approval" | "rejected" | "approved"
    player_id: str | None
    username: str | None
    roles: frozenset[str]
    requested_role: str | None


def resolve_subject_registration_status(
    db: Session, subject: AuthenticatedSubjectLike
) -> SubjectRegistrationStatus:
    """Unlike `resolve_bound_principal`, this never raises on a missing or
    inactive binding -- it reports the subject's real registration state
    instead, active or not. Still fails closed on a malformed issuer/
    subject_id exactly like every other entry point here; the only
    difference from `resolve_bound_principal` is what happens once a
    verified subject's binding turns out not to be active.
    """
    issuer = validate_issuer(subject.issuer)
    subject_id = _required(subject.subject_id, "subject_id")
    binding = (
        db.query(IdentityBinding)
        .filter(IdentityBinding.issuer == issuer, IdentityBinding.subject_id == subject_id)
        .one_or_none()
    )
    if binding is None:
        return SubjectRegistrationStatus(
            status="not_registered", player_id=None, username=None, roles=frozenset(), requested_role=None
        )
    if binding.active:
        player = db.query(Player).filter(Player.player_id == binding.player_id).one_or_none()
        return SubjectRegistrationStatus(
            status="approved",
            player_id=binding.player_id,
            username=player.username if player else None,
            roles=effective_roles(subject),
            requested_role=binding.requested_role,
        )
    if binding.registration_decision == "rejected":
        status = "rejected"
    else:
        status = "pending_approval"
    return SubjectRegistrationStatus(
        status=status,
        player_id=binding.player_id,
        username=None,
        roles=frozenset(),
        requested_role=binding.requested_role,
    )


def require_any_role(
    *allowed_roles: str,
) -> Callable[[BoundPrincipal], BoundPrincipal]:
    """Build a pure validator suitable for composition in a FastAPI dependency."""
    requested = frozenset(allowed_roles)
    if not requested:
        raise ValueError("at least one allowed role is required")
    unknown = requested - ROLE_NAMES
    if unknown:
        raise ValueError(f"unknown application roles: {sorted(unknown)}")

    def _require(principal: BoundPrincipal) -> BoundPrincipal:
        if principal.roles.isdisjoint(requested):
            raise AuthorizationError("principal does not hold a required role")
        return principal

    return _require


def permissions_for(principal: BoundPrincipal) -> frozenset[Permission]:
    permissions: set[Permission] = set()
    for role in principal.roles:
        permissions.update(ROLE_PERMISSIONS.get(role, ()))
    return frozenset(permissions)


def require_permission(principal: BoundPrincipal, permission: Permission) -> None:
    if permission not in permissions_for(principal):
        raise AuthorizationError(f"missing permission: {permission.value}")


def scoped_to_own_player(
    principal: BoundPrincipal, requested_player_id: str
) -> None:
    """Enforce object ownership using the local binding, never OIDC ``sub``."""
    if principal.player_id is None or requested_player_id != principal.player_id:
        raise AuthorizationError("requested player is outside the bound subject scope")


def require_deployment_tenant(principal: BoundPrincipal) -> None:
    """Fail closed if a principal did not originate in this DB-selected tenant."""
    if principal.tenant_scope != DEPLOYMENT_TENANT_SCOPE:
        raise AuthorizationError("principal tenant scope does not match deployment database")


def _require_active_actor_binding(db: Session, actor: BoundPrincipal) -> None:
    """Re-check the persisted actor binding at a privileged write boundary."""
    active = (
        db.query(IdentityBinding.binding_id)
        .filter(
            IdentityBinding.binding_id == actor.binding_id,
            IdentityBinding.issuer == actor.subject.issuer,
            IdentityBinding.subject_id == actor.subject.subject_id,
            IdentityBinding.active.is_(True),
        )
        .first()
    )
    if active is None:
        raise PrincipalBindingError("actor identity binding is no longer active")


def create_identity_binding(
    db: Session,
    *,
    actor: BoundPrincipal,
    issuer: str,
    subject_id: str,
    player_id: str | None,
    reason: str,
) -> IdentityBinding:
    """Create and audit a binding after an organization-admin decision."""
    require_permission(actor, Permission.IDENTITY_BINDING_MANAGE)
    require_deployment_tenant(actor)
    _require_active_actor_binding(db, actor)
    issuer = validate_issuer(issuer)
    subject_id = _required(subject_id, "subject_id")
    reason = _required(reason, "reason")
    if player_id is not None:
        player_id = _required(player_id, "player_id", maximum=200)
        if db.query(Player).filter(Player.player_id == player_id).first() is None:
            raise PrincipalBindingError(f"player not found: {player_id}")

    binding = IdentityBinding(
        issuer=issuer,
        subject_id=subject_id,
        player_id=player_id,
        active=True,
    )
    try:
        db.add(binding)
        db.flush()
        record_audit_event(
            db,
            actor=actor.audit_actor,
            action="identity_binding.create",
            entity_type="identity_binding",
            entity_id=binding.binding_id,
            details={"reason": reason, "player_id": player_id},
            commit=False,
        )
        db.commit()
        db.refresh(binding)
        return binding
    except IntegrityError as exc:
        db.rollback()
        raise IdentityBindingConflict(
            "issuer/subject or player is already bound"
        ) from exc
    except Exception:
        db.rollback()
        raise


def deactivate_identity_binding(
    db: Session,
    *,
    actor: BoundPrincipal,
    binding_id: str,
    reason: str,
) -> IdentityBinding:
    """Disable and audit a binding; the historical row remains queryable."""
    require_permission(actor, Permission.IDENTITY_BINDING_MANAGE)
    require_deployment_tenant(actor)
    _require_active_actor_binding(db, actor)
    binding_id = _required(binding_id, "binding_id", maximum=200)
    reason = _required(reason, "reason")
    binding = (
        db.query(IdentityBinding)
        .filter(IdentityBinding.binding_id == binding_id)
        .with_for_update()
        .one_or_none()
    )
    if binding is None or not binding.active:
        raise PrincipalBindingError("active identity binding not found")
    try:
        binding.active = False
        record_audit_event(
            db,
            actor=actor.audit_actor,
            action="identity_binding.deactivate",
            entity_type="identity_binding",
            entity_id=binding.binding_id,
            details={"reason": reason, "player_id": binding.player_id},
            commit=False,
        )
        db.commit()
        db.refresh(binding)
        return binding
    except Exception:
        db.rollback()
        raise


def create_self_service_registration(
    db: Session,
    *,
    subject: AuthenticatedSubjectLike,
    username: str,
    requested_role: str,
    full_name: str,
    designation: str = "",
    department: str = "",
    notes: str = "",
) -> IdentityBinding:
    """Let a freshly-verified subject with no binding yet request an account.

    This is the one self-service exception to "only an admin creates a
    binding" (`create_identity_binding` above). It differs from that
    function in every way that matters for security:

    - ``subject`` need not hold any application role yet -- by definition a
      brand-new registrant has none. The caller (`routes/registration.py`)
      must still have proven ``subject`` is a genuine, freshly-verified OIDC
      token (`get_current_subject`); this function trusts verification, not
      authorization, from its caller.
    - ``requested_role`` is a request, not a grant: it is checked against
      ``SELF_SERVICE_REQUESTABLE_ROLES`` (learner/trainer only -- an
      admin role can never be self-requested) and stored for an admin to
      see, but it grants no permission by itself. The binding starts
      ``active=False``; nothing this deployment enforces
      (`resolve_bound_principal`) treats an inactive binding as usable.
      The requester's *actual* role, once approved, still comes only from
      whatever role claim their own verified token carries -- unchanged by
      this call.
    - It creates the ``Player``/``LearnerProfile`` rows the applicant's
      profile needs to exist at all, which `create_identity_binding` never
      does (it always binds to an already-existing player).
    """
    if requested_role not in SELF_SERVICE_REQUESTABLE_ROLES:
        raise AuthorizationError(
            f"requested_role must be one of {sorted(SELF_SERVICE_REQUESTABLE_ROLES)}"
        )
    issuer = validate_issuer(subject.issuer)
    subject_id = _required(subject.subject_id, "subject_id")
    username = _required(username, "username", maximum=100)
    full_name = _required(full_name, "full_name", maximum=200)
    designation = (designation or "").strip()[:200]
    department = (department or "").strip()[:200]
    notes = (notes or "").strip()[:1000]

    existing_binding = (
        db.query(IdentityBinding)
        .filter(
            IdentityBinding.issuer == issuer,
            IdentityBinding.subject_id == subject_id,
        )
        .one_or_none()
    )
    if existing_binding is not None:
        raise IdentityBindingConflict(
            "this verified identity has already registered or been bound"
        )
    if db.query(Player).filter(Player.username == username).first() is not None:
        raise IdentityBindingConflict("username already taken")

    player = Player(username=username)
    try:
        db.add(player)
        db.flush()
        db.add(
            LearnerProfile(
                player_id=player.player_id,
                full_name=full_name,
                designation=designation,
                department=department,
            )
        )
        binding = IdentityBinding(
            issuer=issuer,
            subject_id=subject_id,
            player_id=player.player_id,
            active=False,
            requested_role=requested_role,
            registration_notes=notes,
        )
        db.add(binding)
        db.flush()
        record_audit_event(
            db,
            actor=json.dumps(
                {"issuer": issuer, "subject_id": subject_id},
                ensure_ascii=True,
                separators=(",", ":"),
                sort_keys=True,
            ),
            action="identity_binding.self_register",
            entity_type="identity_binding",
            entity_id=binding.binding_id,
            details={"requested_role": requested_role, "player_id": player.player_id},
            commit=False,
        )
        db.commit()
        db.refresh(binding)
        return binding
    except IntegrityError as exc:
        db.rollback()
        raise IdentityBindingConflict(
            "username or verified identity is already registered"
        ) from exc
    except Exception:
        db.rollback()
        raise


def list_pending_registrations(db: Session, *, actor: BoundPrincipal) -> list[IdentityBinding]:
    """Admin-only: every self-service registration awaiting a decision."""
    require_permission(actor, Permission.IDENTITY_BINDING_MANAGE)
    require_deployment_tenant(actor)
    return (
        db.query(IdentityBinding)
        .filter(
            IdentityBinding.requested_role.isnot(None),
            IdentityBinding.registration_decision.is_(None),
        )
        .order_by(IdentityBinding.created_at.asc())
        .all()
    )


def decide_self_registration(
    db: Session,
    *,
    actor: BoundPrincipal,
    binding_id: str,
    decision: str,
    notes: str = "",
) -> IdentityBinding:
    """Admin approves or rejects one pending self-service registration.

    Approval flips ``active`` to True through the exact same state
    transition `reactivate_identity_binding` already uses (inlined here so
    the decision stamp commits in the same transaction as one audited
    event, not two). Rejection never sets ``active`` at all -- a rejected
    applicant stays unable to authenticate as before, and the
    ``registration_decision`` stamp is what distinguishes "reviewed and
    rejected" from "still pending" in `list_pending_registrations`.

    This still only gates whether the local binding is usable. The
    requester's actual role claim continues to come from their own verified
    token (Keycloak realm role), unchanged by this decision -- see
    `create_self_service_registration`'s docstring.
    """
    if decision not in ("approved", "rejected"):
        raise AuthorizationError("decision must be 'approved' or 'rejected'")
    require_permission(actor, Permission.IDENTITY_BINDING_MANAGE)
    require_deployment_tenant(actor)
    _require_active_actor_binding(db, actor)
    binding_id = _required(binding_id, "binding_id", maximum=200)
    notes = (notes or "").strip()[:1000]

    binding = (
        db.query(IdentityBinding)
        .filter(
            IdentityBinding.binding_id == binding_id,
            IdentityBinding.requested_role.isnot(None),
            IdentityBinding.registration_decision.is_(None),
        )
        .with_for_update()
        .one_or_none()
    )
    if binding is None:
        raise PrincipalBindingError("pending registration not found")
    try:
        if decision == "approved":
            binding.active = True
        binding.registration_decision = decision
        binding.registration_reviewed_by = actor.audit_actor
        binding.registration_reviewed_at = datetime.now(timezone.utc)
        record_audit_event(
            db,
            actor=actor.audit_actor,
            action="identity_binding.registration_decided",
            entity_type="identity_binding",
            entity_id=binding.binding_id,
            details={
                "decision": decision,
                "requested_role": binding.requested_role,
                "notes": notes,
                "player_id": binding.player_id,
            },
            commit=False,
        )
        db.commit()
        db.refresh(binding)
        return binding
    except Exception:
        db.rollback()
        raise


def reactivate_identity_binding(
    db: Session,
    *,
    actor: BoundPrincipal,
    binding_id: str,
    reason: str,
) -> IdentityBinding:
    """Re-enable and audit the same retained binding after approved recovery."""
    require_permission(actor, Permission.IDENTITY_BINDING_MANAGE)
    require_deployment_tenant(actor)
    _require_active_actor_binding(db, actor)
    binding_id = _required(binding_id, "binding_id", maximum=200)
    reason = _required(reason, "reason")
    binding = (
        db.query(IdentityBinding)
        .filter(IdentityBinding.binding_id == binding_id)
        .with_for_update()
        .one_or_none()
    )
    if binding is None or binding.active:
        raise PrincipalBindingError("inactive identity binding not found")
    try:
        binding.active = True
        record_audit_event(
            db,
            actor=actor.audit_actor,
            action="identity_binding.reactivate",
            entity_type="identity_binding",
            entity_id=binding.binding_id,
            details={"reason": reason, "player_id": binding.player_id},
            commit=False,
        )
        db.commit()
        db.refresh(binding)
        return binding
    except Exception:
        db.rollback()
        raise
