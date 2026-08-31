"""
The one write path for models.governance.AuditEvent.

Lane 2 (SIH26101_TEAM_ORCHESTRATION.md section 5, "Object/function
authorization matrix" acceptance evidence) -- route code should call
record_audit_event() rather than constructing an AuditEvent row directly, so
every audit write goes through one place if the shape ever needs to change.

This does not yet enforce WHO may call it -- there is no RBAC/authentication
in this repository yet (see CODEX.md "Current verified reality"). Once real
identity lands, the caller-authorization check belongs here, not scattered
across every route that writes an audit event.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from models.governance import AuditEvent


def record_audit_event(
    db: Session,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    details: dict | None = None,
    *,
    commit: bool = True,
) -> AuditEvent:
    """Insert one append-only audit row and return it. Never updates a
    previous row -- a correction is always a new event, not an edit.

    `commit=False` flushes without committing so a larger security-sensitive
    operation can keep its audit row in the same transaction. Existing callers
    retain the original commit-and-refresh behavior by default.
    """
    event = AuditEvent(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details or {},
    )
    db.add(event)
    if commit:
        db.commit()
        db.refresh(event)
    else:
        db.flush()
    return event
