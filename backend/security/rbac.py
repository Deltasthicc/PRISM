"""Fail-closed authorization over verified OIDC subjects.

Authentication and authorization stay separate: ``security.identity`` verifies
the bearer token, while this module allowlists application roles, resolves the
issuer-scoped subject through local persistence, and enforces object scope.
Nothing here is an HTTP route and no browser-supplied player or tenant value is
treated as authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Callable, Protocol
from urllib.parse import urlsplit

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.identity import IdentityBinding
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
        }
    ),
    # Cross-learner trainer access is deliberately absent until a server-side
    # trainer/cohort assignment model exists. A role name alone is not object
    # scope.
    "trainer": frozenset({Permission.CONTENT_DRAFT_CREATE}),
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
        return f"{self.subject.issuer}|{self.subject.subject_id}"


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


def _issuer(value: str) -> str:
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
    issuer = _issuer(subject.issuer)
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
    issuer = _issuer(issuer)
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
