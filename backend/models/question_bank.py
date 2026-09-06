"""Preloaded, hardcoded question bank -- a curated alternative to uploading
your own material for POST /learning/quiz/generate. Every row is grounded in
a real, cited public document (UPSC exam papers, MoSPI/CSO/NSSO manuals,
DoPT/MeitY/NITI Aayog policy documents), never AI-generated or invented, and
carries that source's name/URL/excerpt alongside the question so a learner
(and a reviewer) can always see exactly what it's grounded in -- the same
never-fabricate standard as ai/quiz_engine.py's live-generated path, just
authored by a human once instead of an LLM per request.

Answering a bank item writes into the exact same AccuracyHistory rows the
Quest combat system uses (see routes/learning_question_bank.py), which is
also what routes/learning_common.py's measured_scores() reads from -- so a
bank attempt counts toward the same competency gap-analysis as everything
else, with no parallel scoring path.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class QuestionBankItem(Base):
    """One hardcoded, source-grounded MCQ. Not player-specific -- this is the
    shared, curated catalog every learner on a given curriculum_slug draws
    from, analogous to services/curricula.py's own module-level CURRICULA
    dict but persisted (so it can be queried/filtered/paged like any other
    table) rather than an in-process constant."""

    __tablename__ = "question_bank_items"

    item_id = Column(String, primary_key=True, default=generate_uuid)
    curriculum_slug = Column(String, nullable=False, index=True)
    # Matches an id in services.curricula.CURRICULA[curriculum_slug]["competencies"]
    # -- deliberately not a foreign key (the catalog is a Python module, not a
    # table), same relationship CompetencyAssessment.curriculum_slug already
    # has to it.
    competency_id = Column(String, nullable=False, index=True)
    difficulty = Column(String, nullable=False)  # easy | medium | hard

    question = Column(String, nullable=False)
    options = Column(JSON, nullable=False)  # list[str], always length 4
    answer_index = Column(Integer, nullable=False)
    explanation = Column(String, nullable=False)
    bloom_level = Column(String, default="apply")

    # Grounding -- mirrors QuizQuestion's source_excerpt contract (schemas/learning.py):
    # source_excerpt must be a literal substring of a real document, verified
    # once by whoever authored this row, not re-derived at request time.
    source_name = Column(String, nullable=False)
    source_excerpt = Column(String, nullable=False)
    source_url = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class QuestionBankAttempt(Base):
    """Records one player's answer to one bank item -- immutable, one row per
    (player_id, item_id) so an item can't be re-scored by resubmitting it,
    the same replay guard AnswerSubmission gives the Quest combat path."""

    __tablename__ = "question_bank_attempts"
    __table_args__ = (
        UniqueConstraint("player_id", "item_id", name="uq_question_bank_attempt_player_item"),
    )

    attempt_id = Column(String, primary_key=True, default=generate_uuid)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)
    item_id = Column(String, ForeignKey("question_bank_items.item_id"), nullable=False, index=True)

    selected_index = Column(Integer, nullable=False)
    correct = Column(Integer, nullable=False)  # 0 or 1 -- SQLite/Postgres-portable boolean-as-int

    answered_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
