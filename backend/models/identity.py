"""Local binding between a verified external OIDC subject and app data.

OIDC ``sub`` is unique only within its issuer and is deliberately not stored
on ``players`` or treated as a player id.  The deployment-selected database is
the tenant boundary today; this table supplies the missing object-ownership
link without pretending that row-level multi-tenancy already exists.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)

from db.database import Base

# Self-service registration may only ever request one of these roles. Never
# 'department_admin', 'organization_admin', 'content_reviewer', or 'auditor'
# -- an elevated role can only reach a token claim via an operator granting
# it directly in Keycloak (security/identity_bootstrap.py's existing
# one-time, lock-protected pattern), never through anything a requester's
# own HTTP body controls. This constraint is the server-side backstop for
# that rule, independent of what routes/registration.py itself validates.
SELF_SERVICE_REQUESTABLE_ROLES = frozenset({"learner", "trainer"})


def generate_uuid() -> str:
    return str(uuid.uuid4())


class IdentityBinding(Base):
    """One issuer-scoped external subject's optional local player binding.

    Administrative identities can exist without a player record.  A player
    can be associated with at most one retained identity-binding row in v1;
    even a disabled row reserves that link. Rebinding/account-linking requires
    a separately reviewed recovery contract and migration rather than silent
    row replacement.
    Administrative deactivation retains the row so audit references remain
    intelligible. Verified subject deletion is the explicit exception: it may
    remove a player-linked binding, while the retained bootstrap audit keeps
    the one-time first-admin gate permanently closed.
    """

    __tablename__ = "identity_bindings"

    binding_id = Column(String, primary_key=True, default=generate_uuid)
    issuer = Column(String, nullable=False)
    subject_id = Column(String, nullable=False)
    player_id = Column(
        String,
        ForeignKey("players.player_id"),
        nullable=True,
        unique=True,
        index=True,
    )
    active = Column(Boolean, nullable=False, default=True)

    # Self-service registration (routes/registration.py, SIH26075 CC-01/CC-10).
    # All five columns below are additive and purely informational/audit --
    # nothing here changes what `active` means or how any existing enforcement
    # path (`resolve_bound_principal`, every `require_principal` route) reads
    # this table. A binding created by an admin via `create_identity_binding`
    # (the pre-existing path) leaves all five NULL, exactly as before this
    # change. A binding created by a new self-service applicant instead sets
    # `requested_role` and starts `active=False`; an admin decision later
    # stamps the remaining four columns without ever touching `active`
    # through this code path except via the existing, unmodified
    # `reactivate_identity_binding()`.
    requested_role = Column(String, nullable=True)
    registration_notes = Column(String, nullable=True)
    registration_decision = Column(String, nullable=True)  # 'approved' | 'rejected' | NULL (pending)
    registration_reviewed_by = Column(String, nullable=True)
    registration_reviewed_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("issuer", "subject_id", name="uq_identity_binding_subject"),
        CheckConstraint(
            "requested_role IS NULL OR requested_role IN ('learner', 'trainer')",
            name="ck_identity_bindings_requestable_role",
        ),
        CheckConstraint(
            "registration_decision IS NULL OR registration_decision IN ('approved', 'rejected')",
            name="ck_identity_bindings_registration_decision",
        ),
    )
