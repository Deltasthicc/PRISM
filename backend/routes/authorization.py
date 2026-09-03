"""FastAPI adapters for Lane 2 authentication and authorization primitives.

Lane 5 routes should compose the narrowest dependency that matches the
operation.  For example, a learner-owned route whose path parameter is
``player_id`` can attach both permission and object scope without repeating
error translation in the handler::

    principal: BoundPrincipal = Depends(
        require_own_player_dependency(Permission.ASSESSMENT_SELF_READ)
    )

The returned object is the exact :class:`BoundPrincipal` produced by the
verified-subject/binding boundary; dependency adapters never reconstruct it
or accept role, player, or tenant authority from request data.
"""

from collections.abc import Callable

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from security.identity import AuthenticationError, get_current_subject
from security.rbac import (
    AuthorizationError,
    BoundPrincipal,
    Permission,
    require_deployment_tenant,
    require_permission,
    resolve_bound_principal,
    scoped_to_own_player,
)


_AUTHENTICATION_REQUIRED = "Authentication required"
_ACCESS_DENIED = "Access denied"


def _raise_forbidden(exc: AuthorizationError) -> None:
    """Translate policy detail into one stable, non-sensitive HTTP envelope."""
    raise HTTPException(status_code=403, detail=_ACCESS_DENIED) from exc


def require_principal(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> BoundPrincipal:
    """Resolve a verified, locally bound principal or return a safe HTTP error."""
    try:
        subject = get_current_subject(authorization)
        principal = resolve_bound_principal(db, subject)
        require_deployment_tenant(principal)
        return principal
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=401,
            detail=_AUTHENTICATION_REQUIRED,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except AuthorizationError as exc:
        _raise_forbidden(exc)


def require_deployment_tenant_dependency(
    principal: BoundPrincipal = Depends(require_principal),
) -> BoundPrincipal:
    """Require the server-selected deployment database tenant.

    ``require_principal`` already performs this check for principals it
    resolves itself.  Keeping this adapter separately composable is
    intentional: dependency overrides used by tests and future route layers
    must still be able to prove that a forged/non-deployment principal fails
    closed instead of bypassing tenant validation.
    """
    try:
        require_deployment_tenant(principal)
    except AuthorizationError as exc:
        _raise_forbidden(exc)
    return principal


def require_permission_dependency(
    permission: Permission,
) -> Callable[..., BoundPrincipal]:
    """Build a dependency that checks one fixed application permission."""

    def dependency(
        principal: BoundPrincipal = Depends(require_deployment_tenant_dependency),
    ) -> BoundPrincipal:
        try:
            require_permission(principal, permission)
        except AuthorizationError as exc:
            _raise_forbidden(exc)
        return principal

    return dependency


def require_own_player_dependency(
    permission: Permission,
) -> Callable[..., BoundPrincipal]:
    """Build a permission + own-player object-scope dependency.

    The consuming route must expose a path parameter named ``player_id``.
    Ownership is checked against the locally persisted identity binding, not
    against OIDC ``sub`` or any body/query/header value.
    """
    permission_dependency = require_permission_dependency(permission)

    def dependency(
        player_id: str,
        principal: BoundPrincipal = Depends(permission_dependency),
    ) -> BoundPrincipal:
        try:
            scoped_to_own_player(principal, player_id)
        except AuthorizationError as exc:
            _raise_forbidden(exc)
        return principal

    return dependency
