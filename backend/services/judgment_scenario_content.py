"""Loader for the hand-authored branching Judgment Simulation content
(data/judgment_scenarios.json). Three real, hand-written scenarios for the
public-policy curriculum's governance/decision-making competencies -- see
models/judgment_scenario.py for why this is a persisted, shared-content
table rather than served straight out of the JSON file at request time (it
needs real primary keys other tables can foreign-key against, e.g.
JudgmentScenarioAttempt.scenario_id).

Kept as its own module (mirroring services/hand_authored_questions.py's
split from db/seed.py) so the content can be validated independently of the
database: tests/test_judgment_scenario_content.py checks every
next_node_id referenced actually exists as a node key (or is null) and that
every node is reachable from start_node_id, without needing a DB at all.
"""
from __future__ import annotations

import json
from pathlib import Path

SCENARIOS_PATH = Path(__file__).resolve().parent.parent / "data" / "judgment_scenarios.json"

_scenarios_cache: list[dict] | None = None


def load_scenarios() -> list[dict]:
    """Every hand-authored scenario, as plain dicts shaped exactly like
    models.judgment_scenario.JudgmentScenario's columns."""
    global _scenarios_cache
    if _scenarios_cache is None:
        with SCENARIOS_PATH.open(encoding="utf-8") as handle:
            _scenarios_cache = json.load(handle)
    return _scenarios_cache


def is_terminal_node(node: dict) -> bool:
    """A node is an ending if it has no choices, or every choice is a
    dead end (next_node_id is null) -- the same test
    routes/judgment_scenarios.py uses to decide `is_ending`."""
    choices = node.get("choices") or []
    return not choices or all(choice.get("next_node_id") is None for choice in choices)


def validate_scenario_graph(scenario: dict) -> None:
    """Raise AssertionError with a clear message if `nodes` is not a valid,
    fully-reachable graph. Used by the content test, and safe to call at
    import/seed time too -- cheap, and it is exactly the invariant a
    hand-authored scenario must never violate."""
    nodes = scenario["nodes"]
    start_node_id = scenario["start_node_id"]
    scenario_id = scenario["scenario_id"]

    assert start_node_id in nodes, f"{scenario_id}: start_node_id {start_node_id!r} is not a node"

    for node_id, node in nodes.items():
        for choice in node.get("choices") or []:
            next_id = choice.get("next_node_id")
            assert next_id is None or next_id in nodes, (
                f"{scenario_id}: node {node_id!r} choice {choice.get('choice_id')!r} "
                f"points to missing node {next_id!r}"
            )

    # Reachability from start_node_id via BFS over next_node_id edges.
    seen = {start_node_id}
    frontier = [start_node_id]
    while frontier:
        node_id = frontier.pop()
        for choice in nodes[node_id].get("choices") or []:
            next_id = choice.get("next_node_id")
            if next_id and next_id not in seen:
                seen.add(next_id)
                frontier.append(next_id)

    unreachable = set(nodes) - seen
    assert not unreachable, f"{scenario_id}: unreachable node(s) from start: {sorted(unreachable)}"
