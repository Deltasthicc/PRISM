"""A real, persisted, trainer-authored course (SIH26075 CC-03/CC-06/CC-09).

Distinct from `models.course_enrollment.CourseEnrollment`'s pre-existing
"igot"/"nssta" provider rows, which track a learner's interaction with an
external catalogue recommendation computed by
`services/learning_catalog.py::recommend_courses()` -- those stay exactly as
they are (see that module's own docstring for why). A `Course` row here is
the opposite: it is not imported from anywhere, it is authored on this
platform by a real `trainer`-permissioned player, and its `course_id` is a
genuine primary key a `CourseEnrollment` row can point to (via the
`"internal::<course_id>"` provider prefix `routes/course_enrollment.py`
recognizes), not a synthetic string.

`is_published` gates visibility deliberately at this layer rather than a
draft/publish status string: a trainee-facing browse/enroll query only ever
needs "is this live", and keeping it a boolean keeps that filter a plain
index instead of a string comparison against a value set that would need
its own CHECK constraint to stay honest (matching this codebase's own
established preference for a boolean over a string enum wherever there
genuinely are only two states -- see `models/identity.py`'s `active`
column for the identical precedent).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Course(Base):
    __tablename__ = "courses"

    course_id = Column(String, primary_key=True, default=generate_uuid)
    trainer_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False, default="")
    # Links into the same competency taxonomy every other evidence/pathway
    # table already keys on (see models/governance.py's EvidenceRecord,
    # models/course_enrollment.py) -- deliberately a free-form string, not a
    # foreign key to a `competencies` table, because no such table exists
    # yet; every other model in this codebase makes the same choice for the
    # same reason.
    competency_id = Column(String, nullable=False, index=True)
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
