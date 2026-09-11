"""Tracks a learner's real interaction with a recommended course --
`services/learning_catalog.py::recommend_courses()` was computed correctly
(real gap-ranked, provider-tagged) but never actually surfaced to a learner
and had no lifecycle beyond a link. This table is what makes "enroll" and
"complete" real, persisted events instead of just a click that goes nowhere.

course_id here is exactly the synthetic id recommend_courses() already
generates (e.g. "igot::os_sampling_design") -- the competency_id it targets
is embedded in that string and re-derived at write time
(routes/course_enrollment.py), not stored redundantly here beyond what's
needed to query a player's own enrollments.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, UniqueConstraint
from db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class CourseEnrollment(Base):
    """One player's enrollment in one recommended course. `provider` is
    "igot" | "nssta" (services.learning_catalog's provider_type vocabulary);
    internal-practice recommendations are plain in-app links and never get a
    row here -- there is nothing to "enroll" in beyond visiting the page."""

    __tablename__ = "course_enrollments"
    __table_args__ = (
        UniqueConstraint("player_id", "course_id", name="uq_course_enrollment_player_course"),
    )

    enrollment_id = Column(String, primary_key=True, default=generate_uuid)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)
    course_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False)  # "igot" | "nssta"
    competency_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)

    status = Column(String, nullable=False, default="enrolled")  # enrolled | completed
    enrolled_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime(timezone=True), nullable=True)
