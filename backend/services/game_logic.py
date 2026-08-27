"""
Game logic service — XP, levels, damage, streaks, room progression.
"""
import math
from datetime import datetime, timezone, timedelta


def calculate_xp(difficulty: str, verdict: str, response_time_ms: int = 0) -> int:
    """Calculate XP earned from an answer."""
    base_xp = {"easy": 10, "medium": 20, "hard": 40}.get(difficulty, 10)

    if verdict == "correct":
        xp = base_xp
    elif verdict == "partial":
        xp = base_xp // 2
    else:  # incorrect
        return 0

    # Speed bonus: under 10 seconds
    if response_time_ms > 0 and response_time_ms < 10000:
        xp += 5

    return xp


def calculate_level(total_xp: int) -> int:
    """Level = floor(total_xp / 100) + 1."""
    return math.floor(total_xp / 100) + 1


def calculate_damage(max_damage: int, score: float) -> int:
    """Damage dealt to the boss: the question's ceiling (max_damage, reached
    only at a perfect NLP score of 1.0) scaled down by however close the
    actual score came to that. A hard question's max_damage is higher than
    an easy one's, so the same score deals more damage on a harder question
    -- deliberately, per the actual design intent (reward tackling harder
    material), not an accident of a flat per-level damage formula."""
    return round(max_damage * max(0.0, min(1.0, score)))


def check_room_clear(correct_in_room: int, enemy_count: int) -> bool:
    """Room is cleared when correct answers >= enemy count."""
    return correct_in_room >= enemy_count


def update_streak(last_active: datetime, current_streak: int) -> tuple[int, datetime]:
    """
    Update streak based on last_active date.
    Returns (new_streak_days, new_last_active).
    """
    now = datetime.now(timezone.utc)
    today = now.date()

    if last_active is None:
        return 1, now

    last_date = last_active.date()

    if last_date == today:
        # Already active today, no change
        return current_streak, now
    elif last_date == today - timedelta(days=1):
        # Yesterday — extend streak
        return current_streak + 1, now
    else:
        # Missed a day — reset
        return 1, now


BOSS_XP_BONUS = 100
DUNGEON_COMPLETE_BONUS = 50


def calculate_streak_bonus(streak_days: int) -> int:
    """Streak bonus: streak_days × 2 bonus XP per answer."""
    return streak_days * 2


def check_dungeon_complete(rooms: list) -> bool:
    """Dungeon is complete when ALL rooms (including boss) are cleared.
    Expects a list of (correct_count, enemy_count) tuples."""
    return all(correct >= enemies for correct, enemies in rooms)


def update_accuracy_history(last_5: list, verdict: str, attempts: int, correct: int):
    """
    Update accuracy tracking fields.
    Returns (new_last_5, new_attempts, new_correct, new_recent_accuracy).
    """
    is_correct = verdict == "correct"

    new_last_5 = list(last_5) if last_5 else []
    new_last_5.append(is_correct)
    if len(new_last_5) > 5:
        new_last_5 = new_last_5[-5:]

    new_attempts = attempts + 1
    new_correct = correct + (1 if is_correct else 0)
    new_recent_accuracy = sum(new_last_5) / len(new_last_5) if new_last_5 else 0.0

    return new_last_5, new_attempts, new_correct, new_recent_accuracy
