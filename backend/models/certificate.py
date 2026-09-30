"""A real, verifiable completion certificate (SIH26075 CC-02/CC-11).

Issued automatically when a trainee completes an internal, trainer-authored
course (see routes/course_enrollment.py's `complete()`), never fabricated
or backdated -- `issued_at` is set at the moment of issuance, not copied
from the enrollment's completion time, so the two can never silently
diverge. `title` and `course_id` are both stored as a snapshot at issuance
time (not a live join to `courses`): a certificate must remain valid and
readable exactly as issued even if the source course is later renamed,
unpublished, or deleted -- exactly the same "immutable evidence record"
principle this codebase already applies to `CompetencyAssessment`.

`verification_code` is deliberately a separate, shorter, unguessable
public identifier from `certificate_id` -- the whole point of a
certificate verification page is that anyone holding this code (not
necessarily the certificate's own owner, and not necessarily
authenticated at all) can confirm it is real, so it must not double as
an internal row id an attacker could enumerate or infer application
details from.
"""
from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String
from db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


def generate_verification_code() -> str:
    # 16 hex chars (64 bits of entropy) -- short enough to type/read aloud
    # for manual verification, long enough that guessing a valid code is
    # not a realistic attack.
    return secrets.token_hex(8)


class Certificate(Base):
    __tablename__ = "certificates"

    certificate_id = Column(String, primary_key=True, default=generate_uuid)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)
    course_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    verification_code = Column(String, nullable=False, unique=True, index=True, default=generate_verification_code)
    issued_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    revoked = Column(Boolean, nullable=False, default=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revoked_reason = Column(String, nullable=True)
