"""A trainer's self-declared teaching expertise for one competency
(SIH26075 PS75-07 / PS75-14).

This is the *declared* half of trainer-to-subject matching. Every field is
the trainer's own unverified claim: `declared_level` is self-declared teaching
proficiency (1-5), `basis`/`basis_detail` say what the claim rests on (e.g. a
degree or certification name) and `years_teaching` is how long they say they
have taught it. Nothing here is checked against a credential issuer, and the
matching service (services/trainer_matching.py) never treats it as verified --
it only combines it with real platform activity (published courses, learner
completions, ratings) and labels the evidence level honestly.

One row per (trainer, competency): the unique constraint is the real guard
for concurrent upserts (routes/trainer_expertise.py handles the resulting
IntegrityError), not an application-level check-then-insert.
`competency_id` is a free-form string validated at write time against the
curricula catalog, matching `models/course.py`'s existing choice (no
`competencies` table exists to reference).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from db.database import Base

EXPERTISE_BASES = ("degree", "certification", "experience", "other")


def generate_uuid() -> str:
    return str(uuid.uuid4())


class TrainerExpertise(Base):
    __tablename__ = "trainer_expertise"
    __table_args__ = (
        UniqueConstraint("trainer_id", "competency_id", name="uq_trainer_expertise_trainer_competency"),
        CheckConstraint(
            "declared_level >= 1 AND declared_level <= 5",
            name="ck_trainer_expertise_declared_level_range",
        ),
        CheckConstraint(
            "basis IN ('degree', 'certification', 'experience', 'other')",
            name="ck_trainer_expertise_basis_values",
        ),
        CheckConstraint("years_teaching >= 0", name="ck_trainer_expertise_years_nonnegative"),
    )

    expertise_id = Column(String, primary_key=True, default=generate_uuid)
    trainer_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)
    competency_id = Column(String, nullable=False, index=True)
    declared_level = Column(Integer, nullable=False)
    basis = Column(String, nullable=False)
    basis_detail = Column(String, nullable=False, default="")
    years_teaching = Column(Integer, nullable=False, default=0)

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
