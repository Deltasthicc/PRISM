"""Controlled, one-time bootstrap for the first local organization admin.

This is deliberately an out-of-band database operation, not an HTTP route.
It creates only an issuer-scoped identity binding; the verified access token
must still assert ``organization_admin`` before RBAC grants any permission.
No token, password, client secret, or unverified username is accepted here.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from db.database import SessionLocal, require_database_at_migration_head
from models import (
    accuracy_history,
    dungeon,
    governance,
    guild,
    identity,
    learning,
    player,
    question,
    session,
    submission,
)
from models.governance import AuditEvent
from models.identity import IdentityBinding
from security.audit import record_audit_event
from security.rbac import AuthorizationError, validate_issuer


BOOTSTRAP_LOCK_KEY = 0x5349484C414E4532
BOOTSTRAP_CONFIRMATION_PREFIX = "BOOTSTRAP ORGANIZATION ADMIN"
BOOTSTRAP_AUDIT_ACTION = "identity_binding.bootstrap"
BOOTSTRAP_AUDIT_ENTITY_TYPE = "identity_binding"

# Importing every model module is intentional: SQLAlchemy configures string-
# referenced relationships lazily, and this module runs directly without
# importing FastAPI's ``main`` registry first.
_REGISTERED_MODEL_MODULES = (
    accuracy_history,
    dungeon,
    governance,
    guild,
    identity,
    learning,
    player,
    question,
    session,
    submission,
)


class IdentityBootstrapError(RuntimeError):
    """Base failure for the controlled first-binding workflow."""


class IdentityBootstrapValidationError(IdentityBootstrapError):
    """Bootstrap input or exact confirmation is invalid."""


class IdentityBootstrapConflict(IdentityBootstrapError):
    """The deployment already has an identity binding."""


def _required_text(value: str, name: str, *, maximum: int) -> str:
    if not isinstance(value, str):
        raise IdentityBootstrapValidationError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise IdentityBootstrapValidationError(f"{name} is required")
    if normalized != value:
        raise IdentityBootstrapValidationError(f"{name} must not have surrounding whitespace")
    if any(ord(character) < 0x20 or ord(character) == 0x7F for character in value):
        raise IdentityBootstrapValidationError(
            f"{name} must not contain control characters"
        )
    if len(value) > maximum:
        raise IdentityBootstrapValidationError(
            f"{name} exceeds {maximum} characters"
        )
    return value


def expected_bootstrap_confirmation(issuer: str, subject_id: str) -> str:
    """Return the exact destructive-style acknowledgement required to apply."""
    try:
        validated_issuer = validate_issuer(issuer)
    except AuthorizationError as exc:
        raise IdentityBootstrapValidationError(str(exc)) from exc
    validated_subject = _required_text(subject_id, "subject_id", maximum=500)
    identity_key = json.dumps(
        {"issuer": validated_issuer, "subject_id": validated_subject},
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return f"{BOOTSTRAP_CONFIRMATION_PREFIX} {identity_key}"


def _acquire_bootstrap_lock(db: Session) -> None:
    """Serialize the empty-table check across competing bootstrap processes."""
    bind = db.get_bind()
    dialect = bind.dialect.name
    if dialect == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": BOOTSTRAP_LOCK_KEY},
        )
        return
    if dialect == "sqlite":
        db.execute(text("BEGIN IMMEDIATE"))
        return
    raise IdentityBootstrapError(
        f"identity bootstrap supports only PostgreSQL or SQLite, not {dialect}"
    )


def bootstrap_initial_organization_admin(
    db: Session,
    *,
    issuer: str,
    subject_id: str,
    operator_reference: str,
    reason: str,
    confirmation: str,
) -> IdentityBinding:
    """Create and audit the deployment's first identity binding exactly once.

    The caller must supply a fresh session with no active transaction. This
    lets the function acquire a transaction-scoped PostgreSQL advisory lock
    (or SQLite's immediate write lock) before checking that no binding exists.
    """
    if db.in_transaction():
        raise IdentityBootstrapError("identity bootstrap requires a fresh database session")

    bind = db.get_bind()
    try:
        require_database_at_migration_head(bind)
    except RuntimeError as exc:
        raise IdentityBootstrapError(f"database revision check failed: {exc}") from exc
    expected_confirmation = expected_bootstrap_confirmation(issuer, subject_id)
    operator_reference = _required_text(
        operator_reference, "operator_reference", maximum=200
    )
    reason = _required_text(reason, "reason", maximum=1000)
    if confirmation != expected_confirmation:
        raise IdentityBootstrapValidationError(
            "confirmation must exactly match the documented issuer-scoped subject acknowledgement"
        )

    try:
        _acquire_bootstrap_lock(db)
        existing_binding_count = db.scalar(
            select(func.count()).select_from(IdentityBinding)
        )
        completed_bootstrap_count = db.scalar(
            select(func.count())
            .select_from(AuditEvent)
            .where(
                AuditEvent.action == BOOTSTRAP_AUDIT_ACTION,
                AuditEvent.entity_type == BOOTSTRAP_AUDIT_ENTITY_TYPE,
            )
        )
        if existing_binding_count or completed_bootstrap_count:
            raise IdentityBootstrapConflict(
                "identity bootstrap is permanently closed because an identity binding "
                "already exists or a retained bootstrap audit proves it ran before"
            )

        binding = IdentityBinding(
            issuer=issuer,
            subject_id=subject_id,
            player_id=None,
            active=True,
        )
        db.add(binding)
        db.flush()
        record_audit_event(
            db,
            actor=f"out-of-band-bootstrap:{operator_reference}",
            action=BOOTSTRAP_AUDIT_ACTION,
            entity_type=BOOTSTRAP_AUDIT_ENTITY_TYPE,
            entity_id=binding.binding_id,
            details={
                "reason": reason,
                "expected_runtime_role": "organization_admin",
                "operator_reference_is_verified_oidc_identity": False,
            },
            commit=False,
        )
        db.commit()
        db.refresh(binding)
        return binding
    except Exception:
        db.rollback()
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create the first issuer-scoped identity binding in a migrated database. "
            "This does not assign an IdP role and never accepts a token or password."
        )
    )
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--operator-reference", required=True)
    parser.add_argument("--reason", required=True)
    parser.add_argument("--confirmation", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    db = SessionLocal()
    try:
        binding = bootstrap_initial_organization_admin(
            db,
            issuer=args.issuer,
            subject_id=args.subject_id,
            operator_reference=args.operator_reference,
            reason=args.reason,
            confirmation=args.confirmation,
        )
    except (IdentityBootstrapError, AuthorizationError, SQLAlchemyError) as exc:
        print(f"Bootstrap refused: {exc}", file=sys.stderr)
        return 2
    finally:
        db.close()

    print(
        "Created first identity binding "
        f"{binding.binding_id} for {binding.issuer}|{binding.subject_id}. "
        "Runtime access still requires a verified organization_admin role assertion."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
