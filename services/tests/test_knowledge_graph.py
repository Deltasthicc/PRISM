"""
Tests for services/knowledge_graph.py.

# NO BACKEND DEPENDENCY - fully solo testable

Fully offline -- no API calls, no DB. accuracy_history comes straight from
mocks/mock_data.py, standing in for what the main backend will eventually
send in the POST /ai/graph/next-topic request body.
"""

from mocks.mock_data import (
    MOCK_ACCURACY_HISTORY_ADVANCED,
    MOCK_ACCURACY_HISTORY_BEGINNER,
    MOCK_ACCURACY_HISTORY_EMPTY,
    MOCK_ACCURACY_HISTORY_INTERMEDIATE,
    MOCK_PLAYER_ID,
)
from services.knowledge_graph import get_next_topic


def _print_state(label: str, result: dict) -> None:
    print(f"\n[{label}]")
    print(f"  next_topic:       {result['next_topic']}")
    print(f"  weak_topics:      {result['weak_topics']}")
    print(f"  unlocked_topics:  {result['_unlocked_topics']}")
    print(f"  locked_topics:    {result['_locked_topics']}")


def test_empty_history_routes_to_arrays():
    result = get_next_topic(MOCK_PLAYER_ID, MOCK_ACCURACY_HISTORY_EMPTY)
    _print_state("empty", result)
    assert result["next_topic"] == "arrays"


def test_beginner_only_arrays_unlocked():
    result = get_next_topic(MOCK_PLAYER_ID, MOCK_ACCURACY_HISTORY_BEGINNER)
    _print_state("beginner", result)
    assert "arrays" in result["_unlocked_topics"]
    for locked in ("linked_lists", "binary_search", "recursion", "stacks_queues"):
        assert locked in result["_locked_topics"], f"{locked} should still be locked"


def test_intermediate_unlocks_arrays_children_but_not_trees():
    result = get_next_topic(MOCK_PLAYER_ID, MOCK_ACCURACY_HISTORY_INTERMEDIATE)
    _print_state("intermediate", result)
    for unlocked in ("linked_lists", "binary_search", "recursion", "stacks_queues"):
        assert unlocked in result["_unlocked_topics"], f"{unlocked} should be unlocked"
    assert "trees" in result["_locked_topics"], "trees needs linked_lists AND recursion both > 0.65"


def test_advanced_unlocks_dynamic_programming_and_routes_to_weakest():
    result = get_next_topic(MOCK_PLAYER_ID, MOCK_ACCURACY_HISTORY_ADVANCED)
    _print_state("advanced", result)
    assert "dynamic_programming" in result["_unlocked_topics"]
    assert "graphs" in result["weak_topics"]
    assert "dynamic_programming" in result["weak_topics"]
    assert result["next_topic"] == "dynamic_programming"
