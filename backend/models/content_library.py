"""Trainer content library (SIH26075 PS75-10).

A `ContentItem` is the metadata row for one file a trainer uploaded
(recorded lecture, presentation or study material). The bytes live on local
disk under `services/content_storage.py`'s storage directory, never in the
database, and are addressed only by `stored_name` -- a server-generated
random name that is never derived from anything the uploader sent.

`original_filename` is display-only (sanitized) and must never be used to
build a filesystem path. `media_type` is decided by the server from an
allowlist, never copied from the client's Content-Type header.

An item is created unpublished. A trainee can only ever see it once it is
published, and (when `course_id` is set) only if that trainee is enrolled in
that trainer's internal course -- see `routes/content_library.py`.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, DateTime, ForeignKey, String
from db.database import Base

CONTENT_KINDS = ("recorded_lecture", "presentation", "study_material")


def generate_uuid() -> str:
    return str(uuid.uuid4())


class ContentItem(Base):
    __tablename__ = "content_items"
    __table_args__ = (
        CheckConstraint(
            "kind IN ('recorded_lecture', 'presentation', 'study_material')",
            name="ck_content_items_kind",
        ),
    )

    content_id = Column(String, primary_key=True, default=generate_uuid)
    trainer_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    description = Column(String(2000), nullable=False, default="")
    kind = Column(String, nullable=False)
    # Optional link to one of THIS trainer's own courses (validated in the
    # route). Items linked to a course are visible only to enrolled trainees.
    course_id = Column(String, ForeignKey("courses.course_id"), nullable=True, index=True)

    original_filename = Column(String, nullable=False)  # display only, sanitized
    stored_name = Column(String, nullable=False, unique=True)  # server-generated
    media_type = Column(String, nullable=False)  # from the server-side allowlist
    size_bytes = Column(BigInteger, nullable=False)
    sha256 = Column(String(64), nullable=False)

    is_published = Column(Boolean, nullable=False, default=False, index=True)

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
