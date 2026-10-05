"""Admin-authored announcements for the in-app home feed (SIH26075 PS75-13).

"Notifications" in this product means this in-app feed only: nothing here
pushes, emails or texts anyone. An `Announcement` is a plain record an
organization admin writes, publishes and later retires by unpublishing --
rows are never deleted, so the history of what was shown stays intact.

`kind` and `audience` are small closed vocabularies enforced by CHECK
constraints (not just by the API schema) so a bad value can never be
persisted by any code path. `created_by` is the acting admin's audit actor
string, not a foreign key to `players`: in the DISABLE_AUTH demo the
principal has no player row at all, and an announcement must stay
attributable either way.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Index, String
from db.database import Base

ANNOUNCEMENT_KINDS = ("announcement", "achievement", "new_content")
ANNOUNCEMENT_AUDIENCES = ("all", "learner", "trainer")


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Announcement(Base):
    __tablename__ = "announcements"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('announcement', 'achievement', 'new_content')",
            name="ck_announcements_kind",
        ),
        CheckConstraint(
            "audience IN ('all', 'learner', 'trainer')",
            name="ck_announcements_audience",
        ),
        Index("ix_announcements_published", "is_published", "published_at"),
    )

    announcement_id = Column(String, primary_key=True, default=generate_uuid)
    title = Column(String(200), nullable=False)
    body = Column(String(4000), nullable=False)
    kind = Column(String, nullable=False, default="announcement")
    audience = Column(String, nullable=False, default="all")
    created_by = Column(String, nullable=False)
    is_published = Column(Boolean, nullable=False, default=False)
    published_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

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
