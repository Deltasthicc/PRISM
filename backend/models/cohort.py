"""Real trainer/cohort assignment (SIH26075 CC-08/PS75-09).

Closes a gap this codebase has documented explicitly since Lane 2 first
wrote `security/rbac.py`'s trainer permission comment: "Cross-learner
trainer access is deliberately absent until a server-side trainer/cohort
assignment model exists. A role name alone is not object scope." This is
that model.

A `Cohort` is admin-assigned (`Permission.COHORT_MANAGE`, organization_admin
only) to exactly one trainer, who gets scoped read access
(`Permission.COHORT_READ`) to only that cohort's members' participation and
performance -- never organization-wide, never self-assigned. Membership is
a separate join table rather than a column on `Player` because a trainee
can belong to more than one cohort (different subjects/trainers), and
because an admin must be able to add/remove a single member without
touching the cohort or player row itself.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Cohort(Base):
    __tablename__ = "cohorts"

    cohort_id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    trainer_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)

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


class CohortMembership(Base):
    __tablename__ = "cohort_memberships"
    __table_args__ = (
        UniqueConstraint("cohort_id", "player_id", name="uq_cohort_membership_cohort_player"),
    )

    membership_id = Column(String, primary_key=True, default=generate_uuid)
    cohort_id = Column(String, ForeignKey("cohorts.cohort_id"), nullable=False, index=True)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)

    added_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
