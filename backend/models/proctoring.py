"""Real, persisted exam-integrity signals for a competency-quiz attempt.

Nothing here performs the actual face/phone detection -- that runs
client-side (frontend/components/ProctoringMonitor.jsx, via real in-browser
ML models: blazeface for face count, coco-ssd for phone detection) so no
video frame or image ever leaves the learner's device. This table only
records the *events* the client already decided are violations (plus the
non-camera tab-switch/fullscreen-exit signals), which is the same
privacy boundary the rest of this project holds: log what happened, never
the raw biometric input that produced the judgment.

attempt_id here is the same opaque string routes/competency_quiz.py hands
out per quiz attempt (see _issue_attempt) -- attempts themselves are
in-memory and not persisted, so this is a plain indexed string, not a
foreign key to anything.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String
from db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


# Kept as a plain tuple (not a DB-level CHECK constraint) so adding a new
# signal later is a one-line change here plus in the Pydantic schema,
# consistent with this codebase's EVIDENCE_TYPES-style enums.
VIOLATION_TYPES = (
    "no_face_detected",
    "multiple_faces_detected",
    "phone_detected",
    "tab_switch",
    "fullscreen_exit",
)


class ProctoringEvent(Base):
    """One exam-integrity signal raised during one quiz attempt."""

    __tablename__ = "proctoring_events"

    event_id = Column(String, primary_key=True, default=generate_uuid)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)
    attempt_id = Column(String, nullable=False, index=True)
    violation_type = Column(String, nullable=False)
    detail = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
