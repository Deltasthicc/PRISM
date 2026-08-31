"""Local binding between a verified external OIDC subject and app data.

OIDC ``sub`` is unique only within its issuer and is deliberately not stored
on ``players`` or treated as a player id.  The deployment-selected database is
the tenant boundary today; this table supplies the missing object-ownership
link without pretending that row-level multi-tenancy already exists.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, UniqueConstraint

from db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class IdentityBinding(Base):
    """One issuer-scoped external subject's optional local player binding.

    Administrative identities can exist without a player record.  A player
    can be associated with at most one retained identity-binding row in v1;
    even a disabled row reserves that link. Rebinding/account-linking requires
    a separately reviewed recovery contract and migration rather than silent
    row replacement.
    Deactivation is retained instead of deleting the row so audit references
    remain intelligible.
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
    )
