"""Shared time+difficulty-weighted scoring helpers.

Originally lived only in routes/competency_quiz.py; factored out so the
Source Quiz Generator's scored "take it" flow (routes/learning_content.py)
uses the exact same algorithm instead of a second, independently drifting
copy. See routes/competency_quiz.py's own comment for the full rationale:
timing is a secondary signal that nudges a bounded +-15% band on top of
accuracy, never enough to make a wrong answer outscore a right one.
"""

EXPECTED_SECONDS = {"easy": 20, "medium": 40, "hard": 75}
TIME_FACTOR_MIN = 0.85
TIME_FACTOR_MAX = 1.10

# Relative credit per difficulty when combining questions of different
# difficulties into one weighted score -- a harder question is worth more,
# the same convention a curated exam gives more marks to a harder item. This
# is a documented design choice, not a psychometrically calibrated weight.
DIFFICULTY_WEIGHT = {"easy": 1.0, "medium": 1.5, "hard": 2.0}


def time_factor(difficulty: str, time_taken_ms: int | None) -> float:
    """1.0 (neutral) if no timing was reported; otherwise a bounded ratio of
    expected-to-actual time, so answering faster than the reference nudges
    the factor above 1.0 and answering slower nudges it below."""
    if not time_taken_ms or time_taken_ms <= 0:
        return 1.0
    expected_ms = EXPECTED_SECONDS.get(difficulty, EXPECTED_SECONDS["medium"]) * 1000
    ratio = expected_ms / time_taken_ms
    return max(TIME_FACTOR_MIN, min(TIME_FACTOR_MAX, ratio))


def pace_label(factor: float) -> str:
    if factor >= 1.03:
        return "faster"
    if factor <= 0.92:
        return "slower"
    return "typical"
