"""Real trainee feedback on a course (SIH26075 CC-05), one row per
(player, course) -- the "one submission per trainee/content" policy
SIH26075_MASTER_CHECKLIST.md's PS75-06 calls for, enforced at the database
level via the unique constraint below, not just in application code.

A second submission for the same course is an update, not a new row --
routes/course_feedback.py's upsert handler is what implements the "edit
rules" half of that same requirement.

`course_id` is a real foreign key to `courses.course_id` (unlike
`course_enrollment.py`'s loose `"<provider>::<value>"` string, which also
has to represent external igot/nssta catalogue entries that have no local
row to reference). Feedback only ever exists for a real, internal,
trainer-authored course, so there is nothing to lose from the stronger
constraint and real referential integrity to gain.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class CourseFeedback(Base):
    __tablename__ = "course_feedback"
    __table_args__ = (
        UniqueConstraint("player_id", "course_id", name="uq_course_feedback_player_course"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_course_feedback_rating_range"),
    )

    feedback_id = Column(String, primary_key=True, default=generate_uuid)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)
    course_id = Column(String, ForeignKey("courses.course_id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)
    comment = Column(String, nullable=False, default="")

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
