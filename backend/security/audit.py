"""
The one write path for models.governance.AuditEvent.

Lane 2 (SIH26101_TEAM_ORCHESTRATION.md section 5, "Object/function
authorization matrix" acceptance evidence) -- route code should call
record_audit_event() rather than constructing an AuditEvent row directly, so
every audit write goes through one place if the shape ever needs to change.

This helper does not itself decide WHO may call it. Lane 2 now supplies OIDC
verification, local identity binding and RBAC primitives, and privileged
security services enforce them before calling this helper. Existing HTTP
routes still need Lane 5 to compose those checks; the presence of this write
path alone does not make a route authenticated or audited.
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
