"""FastAPI adapters for Lane 2 authentication and authorization primitives."""

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
)


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
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    except AuthorizationError as exc:
        raise HTTPException(status_code=403, detail="Access denied") from exc


def require_permission_dependency(permission: Permission):
    """Build a dependency that checks one fixed application permission."""

    def dependency(
        principal: BoundPrincipal = Depends(require_principal),
    ) -> BoundPrincipal:
        try:
            require_permission(principal, permission)
        except AuthorizationError as exc:
            raise HTTPException(status_code=403, detail="Access denied") from exc
        return principal

    return dependency