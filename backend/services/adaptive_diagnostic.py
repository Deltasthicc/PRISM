"""Two-stage adaptive diagnostic: a broad stage-1 quiz across a curriculum,
then -- only when a real misconception signal exists -- a stage-2 quiz
targeted at whichever specific misconception the learner's wrong answers
most pointed to.

Reuses the exact same source-cited item pools routes/competency_quiz.py
already serves (services.hand_authored_questions +
services.ai_authored_questions), so this is a second lens over real,
already-vetted content, not a new content pipeline. The one new piece of
data is data/misconception_tags.json: a curated, additive layer that tags a
subset of existing item_id values with the single real misconception their
wrong options represent (see that file's own note for how it was built).

Honesty boundary this module holds throughout: if a learner's wrong answers
in stage 1 don't carry a misconception tag (either because they got
everything right, or because the items they missed simply aren't in the
tagged subset), there is no real signal to target -- stage 2 is reported as
unavailable rather than serving an arbitrary follow-up quiz dressed up as
"targeted." Likewise, if a targeted misconception has no untouched real
item left to serve, that is reported plainly rather than padded with
unrelated content.
"""
from __future__ import annotations

import json
import random
import time
import uuid
from collections import Counter
from pathlib import Path

from services.ai_authored_questions import questions_for_competency as _ai_questions_for_competency
from services.curricula import CURRICULA
from services.hand_authored_questions import questions_for_competency as _hand_questions_for_competency

MISCONCEPTION_TAGS_PATH = Path(__file__).resolve().parent.parent / "data" / "misconception_tags.json"

STAGE1_ITEM_COUNT = 12
STAGE2_ITEM_COUNT = 5
# Mirrors routes/competency_quiz.py's own _active_attempts pattern exactly:
# a process-local, TTL-bounded session registry. Explicitly not described as
# durable cross-restart storage -- see that module's identical comment.
SESSION_TTL_SECONDS = 60 * 60
MAX_ACTIVE_SESSIONS = 1_000

_active_sessions: dict[str, dict] = {}
_misconception_tags_cache: dict | None = None


def _load_misconception_tags() -> dict[str, dict]:
    global _misconception_tags_cache
    if _misconception_tags_cache is None:
        with MISCONCEPTION_TAGS_PATH.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        _misconception_tags_cache = payload["tags"]
    return _misconception_tags_cache


def misconception_label(misconception: str) -> str | None:
    """The human-readable label for a misconception tag, or None if it's
    somehow unknown (should not happen for a tag this module itself just
    derived from _load_misconception_tags(), but callers outside this
    module shouldn't reach into the private tag cache directly)."""
    for entry in _load_misconception_tags().values():
        if entry["misconception"] == misconception:
            return entry["label"]
    return None


def _items_by_misconception() -> dict[str, list[str]]:
    """Reverse index: misconception -> every tagged item_id carrying it."""
    reverse: dict[str, list[str]] = {}
    for item_id, entry in _load_misconception_tags().items():
        reverse.setdefault(entry["misconception"], []).append(item_id)
    return reverse


def _curriculum_competency_ids(curriculum_slug: str) -> list[str]:
    curriculum = CURRICULA.get(curriculum_slug)
    if not curriculum:
        return []
    return [c["id"] for c in curriculum["competencies"]]


def _mcq_items_for_competency(competency_id: str) -> list[dict]:
    """Only real multiple-choice items (a genuine wrong-option set to derive
    a misconception signal from) -- fill-in-blank items have no distractor
    to tag and are excluded here, unlike competency_quiz.py which serves
    both types."""
    pool = _hand_questions_for_competency(competency_id) + _ai_questions_for_competency(competency_id)
    return [item for item in pool if item.get("options")]


def curriculum_item_pool(curriculum_slug: str) -> dict[str, dict]:
    """item_id -> item, across every competency in this curriculum."""
    by_id: dict[str, dict] = {}
    for competency_id in _curriculum_competency_ids(curriculum_slug):
        for item in _mcq_items_for_competency(competency_id):
            by_id[item["item_id"]] = item
    return by_id


def _select_balanced(pool: dict[str, dict], count: int, exclude: set[str] | None = None) -> list[dict]:
    """A random, competency-balanced sample -- the same round-robin-by-
    competency shape competency_quiz.py's own _select_questions() uses, so a
    single competency with a large bank can't quietly dominate the set."""
    exclude = exclude or set()
    by_competency: dict[str, list[dict]] = {}
    for item in pool.values():
        if item["item_id"] in exclude:
            continue
        by_competency.setdefault(item["competency_id"], []).append(item)
    for queue in by_competency.values():
        random.shuffle(queue)

    selected: list[dict] = []
    competency_ids = list(by_competency.keys())
    while len(selected) < count and any(by_competency.values()):
        for competency_id in competency_ids:
            queue = by_competency[competency_id]
            if queue and len(selected) < count:
                selected.append(queue.pop(0))
    return selected


def _prune_expired_sessions() -> None:
    now = time.monotonic()
    expired = [sid for sid, s in _active_sessions.items() if now - s["issued_at"] > SESSION_TTL_SECONDS]
    for sid in expired:
        _active_sessions.pop(sid, None)
    while len(_active_sessions) >= MAX_ACTIVE_SESSIONS:
        oldest = min(_active_sessions, key=lambda key: _active_sessions[key]["issued_at"])
        _active_sessions.pop(oldest, None)


def start_stage1(curriculum_slug: str, player_id: str) -> tuple[str, list[dict]] | None:
    """Returns (session_id, items) or None if this curriculum has no real
    MCQ content to diagnose at all."""
    pool = curriculum_item_pool(curriculum_slug)
    if not pool:
        return None
    selected = _select_balanced(pool, STAGE1_ITEM_COUNT)
    if not selected:
        return None

    _prune_expired_sessions()
    session_id = str(uuid.uuid4())
    _active_sessions[session_id] = {
        "player_id": player_id,
        "curriculum_slug": curriculum_slug,
        "stage1_item_ids": [item["item_id"] for item in selected],
        "stage1_submitted": False,
        "stage1_results": None,
        "target_misconception": None,
        "stage2_item_ids": None,
        "stage2_submitted": False,
        "stage2_results": None,
        "issued_at": time.monotonic(),
    }
    return session_id, selected


def get_session(session_id: str) -> dict | None:
    return _active_sessions.get(session_id)


def grade_stage(session: dict, stage: int, answers: list[dict], all_items_by_id: dict[str, dict]) -> dict:
    """Grades a list of {item_id, selected_index} against real answer_index
    values -- never the client's own claim of correctness. Returns a dict
    with `graded` (per-item results), `correct`/`total`, and -- for stage 1
    only -- the misconception tally used to decide stage 2 eligibility."""
    tags = _load_misconception_tags()
    graded: list[dict] = []
    misconception_counter: Counter = Counter()

    for answer in answers:
        item = all_items_by_id.get(answer["item_id"])
        if item is None:
            raise ValueError(f"Item {answer['item_id']!r} was not part of this diagnostic stage")
        is_correct = answer["selected_index"] == item["answer_index"]
        entry = {
            "item_id": item["item_id"],
            "competency_id": item["competency_id"],
            "correct": is_correct,
            "selected_index": answer["selected_index"],
            "correct_index": item["answer_index"],
            "explanation": item["explanation"],
            "source_excerpt": item["source_excerpt"],
        }
        if not is_correct:
            tag_entry = tags.get(item["item_id"])
            if tag_entry:
                misconception_counter[tag_entry["misconception"]] += 1
                entry["misconception"] = tag_entry["misconception"]
                entry["misconception_label"] = tag_entry["label"]
        graded.append(entry)

    return {
        "graded": graded,
        "correct": sum(1 for g in graded if g["correct"]),
        "total": len(graded),
        "misconception_counter": misconception_counter,
    }


def determine_target_misconception(misconception_counter: Counter) -> str | None:
    if not misconception_counter:
        return None
    top_count = max(misconception_counter.values())
    # Ties are real and possible with a small stage-1 set -- pick the one
    # that comes first alphabetically for determinism rather than randomly,
    # so re-reading a session's own record is reproducible.
    candidates = sorted(tag for tag, count in misconception_counter.items() if count == top_count)
    return candidates[0]


def stage2_candidate_items(
    curriculum_slug: str, target_misconception: str, already_shown: set[str]
) -> list[dict]:
    pool = curriculum_item_pool(curriculum_slug)
    tagged_ids = set(_items_by_misconception().get(target_misconception, []))
    candidates = [
        item for item_id, item in pool.items()
        if item_id in tagged_ids and item_id not in already_shown
    ]
    random.shuffle(candidates)
    return candidates[:STAGE2_ITEM_COUNT]
