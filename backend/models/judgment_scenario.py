"""Branching "Judgment Simulation" scenarios -- a decision-tree content type
that tests officer judgment (weighing trade-offs, picking a defensible
course of action under realistic constraints) in a way a multiple-choice
quiz item cannot: there is no single fact to recall, only a choice among
plausible actions, each with an honest consequence.

Two tables, matching models/course_enrollment.py's split between authored
content and a learner's real interaction with it:

- `JudgmentScenario` is the authored content (a decision tree): read-only to
  learners, shared across every player, analogous to
  models/question_bank.py's QuestionBankItem. `nodes` is a JSON dict of
  `node_id -> {"prompt", "choices": [...]}`; a node whose `choices` is empty,
  or whose every choice has `next_node_id: null`, is a terminal/ending node.
  Never serialize `nodes` wholesale to a learner (routes/judgment_scenarios.py
  hands out one node, and only the fields safe to see before a choice is
  made) -- that would hand over the entire tree (including which choice is
  `is_recommended`) before the learner has committed to anything.

- `JudgmentScenarioAttempt` is a learner's real, completed run: the ordered
  path they actually took plus the server-recomputed recommended/total
  choice counts (routes/judgment_scenarios.py re-walks `nodes` from
  `start_node_id` rather than trusting the client's own counts or its claim
  to have reached a genuine ending -- see that route's `/complete` handler).
  A completed attempt is what turns into a real EvidenceRecord
  (evidence_type="observed_practice") and an AccuracyHistory update for the
  scenario's competency_id, exactly like labs/sampling_lab.py's submission
  flow, so a judgment simulation feeds Prerequisite Pathways the same as
  every other real practice signal in this app -- not just UI without a
  backing evidence trail.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String
from db.database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class JudgmentScenario(Base):
    """One authored branching scenario. Shared, curated content -- not
    player-specific -- so there is exactly one row per scenario regardless
    of how many learners play it."""

    __tablename__ = "judgment_scenarios"

    scenario_id = Column(String, primary_key=True, default=generate_uuid)
    competency_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    situation_brief = Column(String, nullable=False)
    # {"node_id": {"prompt": str, "choices": [{"choice_id", "text",
    #   "next_node_id", "feedback", "is_recommended"}]}}. A node with an empty
    # `choices` list, or whose every choice has `next_node_id: None`, is a
    # terminal/ending node -- there is no separate `is_ending` flag stored,
    # it is derived the same way everywhere (see routes/judgment_scenarios.py
    # `_is_terminal_node`).
    nodes = Column(JSON, nullable=False)
    start_node_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class JudgmentScenarioAttempt(Base):
    """One learner's completed run through a scenario. A learner may retry a
    scenario for more practice -- unlike course_enrollment.py's enroll/
    complete lifecycle, there is no uniqueness constraint here and no
    idempotency requirement; each completion is its own row and its own
    practice signal."""

    __tablename__ = "judgment_scenario_attempts"

    attempt_id = Column(String, primary_key=True, default=generate_uuid)
    player_id = Column(String, ForeignKey("players.player_id"), nullable=False, index=True)
    scenario_id = Column(String, ForeignKey("judgment_scenarios.scenario_id"), nullable=False, index=True)
    # Ordered list of {"node_id": str, "choice_id": str} exactly as walked
    # from start_node_id to a terminal node -- server-validated, never the
    # client's own claim (routes/judgment_scenarios.py `/complete`).
    path_taken = Column(JSON, nullable=False)
    recommended_choice_count = Column(Integer, nullable=False)
    total_choice_count = Column(Integer, nullable=False)
    completed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
