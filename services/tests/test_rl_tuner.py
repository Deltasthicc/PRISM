"""
Tests for services/rl_tuner.py.

# NO BACKEND DEPENDENCY - accuracy_history mocked locally

Fully offline -- no API calls, no DB. accuracy_history comes straight from
mocks/mock_data.py, standing in for what the main backend will eventually
send in the POST /ai/difficulty/next request body.
"""

import random
from unittest.mock import patch

from mocks.mock_data import (
    MOCK_ACCURACY_HISTORY_ADVANCED,
    MOCK_ACCURACY_HISTORY_BEGINNER,
    MOCK_ACCURACY_HISTORY_EMPTY,
    MOCK_ACCURACY_HISTORY_INTERMEDIATE,
    MOCK_PLAYER_ID,
)
from services.rl_tuner import get_next_difficulty

# Forces the greedy (non-exploring) branch deterministically: random.random()
# returning 1.0 is never < RL_EPSILON, so these single-case tests aren't
# flaky despite the bandit's built-in randomness.
GREEDY_ONLY = patch("services.rl_tuner.random.random", return_value=1.0)


@GREEDY_ONLY
def test_advanced_arrays_is_hard(_mock_random):
    result = get_next_difficulty(MOCK_PLAYER_ID, "arrays", MOCK_ACCURACY_HISTORY_ADVANCED)
    assert result["difficulty"] == "hard"
    assert "_reason" in result


@GREEDY_ONLY
def test_beginner_arrays_is_easy(_mock_random):
    result = get_next_difficulty(MOCK_PLAYER_ID, "arrays", MOCK_ACCURACY_HISTORY_BEGINNER)
    assert result["difficulty"] == "easy"
    assert "_reason" in result


@GREEDY_ONLY
def test_intermediate_linked_lists_is_medium(_mock_random):
    result = get_next_difficulty(MOCK_PLAYER_ID, "linked_lists", MOCK_ACCURACY_HISTORY_INTERMEDIATE)
    assert result["difficulty"] == "medium"
    assert "_reason" in result


@GREEDY_ONLY
def test_empty_history_any_topic_is_easy(_mock_random):
    result = get_next_difficulty(MOCK_PLAYER_ID, "graphs", MOCK_ACCURACY_HISTORY_EMPTY)
    assert result["difficulty"] == "easy"
    assert "_reason" in result


def test_epsilon_exploration_rate():
    """
    With recent_accuracy=1.0 ("arrays" in ADVANCED), the greedy choice is
    always "hard". Over many calls, ~RL_EPSILON of them should explore into
    a (possibly still "hard", but usually different) random difficulty --
    we assert the non-"hard" fraction lands in a sane band around the
    configured epsilon, not exactly at it.
    """
    random.seed(42)  # reproducible across runs
    results = [
        get_next_difficulty(MOCK_PLAYER_ID, "arrays", MOCK_ACCURACY_HISTORY_ADVANCED)["difficulty"]
        for _ in range(100)
    ]
    non_hard_count = sum(1 for d in results if d != "hard")
    assert 5 <= non_hard_count <= 15, f"expected 5-15 non-hard picks out of 100, got {non_hard_count}"
