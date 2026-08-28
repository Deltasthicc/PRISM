"""
LLM Question Engine (README section 4.1).

NO BACKEND DEPENDENCY. topic/difficulty/domain are supplied directly by the
caller (eventually the main backend's POST /game/room/enter handler, but
fully testable solo by passing these three strings ourselves).
"""

import asyncio
import json
import random
import re
import uuid

from google import genai
from google.genai import types

import config

MIN_EXPECTED_ANSWER_LENGTH = 30
MAX_ATTEMPTS = 3

# Damage this question deals if answered perfectly (NLP score of 1.0).
# Randomized within a per-difficulty band rather than a fixed value per tier,
# so two "hard" questions aren't interchangeable -- a harder question always
# has a *higher ceiling* than an easier one, but exactly how much is still
# some variety within that.
DAMAGE_RANGE_BY_DIFFICULTY = {
    "easy": (40, 70),
    "medium": (70, 110),
    "hard": (110, 160),
}

_client = None


def _get_client():
    global _client
    if not config.GEMINI_API_KEY:
        raise QuestionGenerationError(
            "GEMINI_API_KEY is not set; configure services/.env before using question generation"
        )
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client

PROMPT_TEMPLATE = """You are {monster_name}, a dungeon monster in an educational RPG.
Topic: {topic}
Difficulty: {difficulty}
Subject domain: {domain}

Generate a single exam-quality question for a student fighting you. Stay in
character as {monster_name} throughout the question text -- do not invent,
name, or reference any other monster or creature.
"expected_answer" is compared against the student's free-text answer by a
semantic similarity judge, so it must be a full explanatory answer (at least
2-3 sentences) that states the fact AND explains the reasoning behind it --
never a bare word, number, or one-line fact on its own (e.g. not just "O(1)"
or "0"; explain *why* it is O(1) or *why* the index is 0).
Respond in JSON only, no preamble:
{{
  "question": "...",
  "expected_answer": "...",
  "hint": "..."
}}"""


class QuestionGenerationError(Exception):
    """Raised when the LLM fails to produce a valid question after MAX_ATTEMPTS retries."""


def _extract_json(raw_text: str) -> dict:
    """
    Pulls a JSON object out of the LLM's raw text response.

    Gemini is instructed to respond JSON-only, but models sometimes wrap
    output in markdown code fences anyway -- strip those before parsing.
    Raises json.JSONDecodeError / ValueError on malformed input, which the
    caller's retry loop catches.
    """
    text = raw_text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    return json.loads(text)


async def generate_question(topic: str, difficulty: str, domain: str, monster_name: str = None) -> dict:
    """
    Generate a single unique question for a fight.

    Inputs:
        topic: str -- exact topic name (e.g. "binary_search"). Must match
            one of the 11 README topic names, but this function does not
            validate that itself; routes/ai.py is responsible for that.
        difficulty: str -- "easy" | "medium" | "hard".
        domain: str -- subject domain, e.g. "Data Structures & Algorithms".
        monster_name: str -- the topic's actual villain name (see
            services/monsters.py in the main backend), so every question for
            a topic is voiced consistently by the one monster the player sees
            on screen instead of a different invented persona each time.
            Falls back to a generic phrase if not supplied.

    Output:
        dict matching the POST /ai/question/generate response contract:
        { question_id, question, expected_answer, hint, max_damage }

    Backend dependency: NONE. All inputs are supplied directly by the caller.
    Fully testable solo (see tests/test_llm_engine.py).

    Raises:
        QuestionGenerationError if the LLM fails to return valid JSON with
        a sufficiently detailed expected_answer after MAX_ATTEMPTS retries.
    """
    prompt = PROMPT_TEMPLATE.format(
        topic=topic, difficulty=difficulty, domain=domain,
        monster_name=monster_name or "the dungeon's guardian",
    )
    client = _get_client()

    last_error: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = await client.aio.models.generate_content(
                model=config.LLM_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=1024,
                    temperature=0.9,
                    # Without this, a stuck/slow call hangs well past what a
                    # player will wait for a question to generate, and blocks
                    # this attempt from ever reaching the retry-with-backoff
                    # logic below.
                    http_options=types.HttpOptions(timeout=15000),  # ms
                ),
            )
            raw_text = response.text
            if not raw_text or not raw_text.strip():
                # Gemini returns text=None/"" instead of raising when a response
                # is blocked by safety filters or hits a non-STOP finish_reason
                # (observed empirically: empty string, not just None).
                finish_reason = response.candidates[0].finish_reason if response.candidates else None
                raise ValueError(f"Gemini returned no text (finish_reason={finish_reason!r})")
            parsed = _extract_json(raw_text)

            question = parsed["question"]
            expected_answer = parsed["expected_answer"]
            hint = parsed["hint"]

            if len(expected_answer) < MIN_EXPECTED_ANSWER_LENGTH:
                raise ValueError(
                    f"expected_answer too short ({len(expected_answer)} chars); "
                    f"NLP judge needs >= {MIN_EXPECTED_ANSWER_LENGTH} chars to score against"
                )

            damage_low, damage_high = DAMAGE_RANGE_BY_DIFFICULTY.get(difficulty, (70, 110))
            return {
                "question_id": str(uuid.uuid4()),
                "question": question,
                "expected_answer": expected_answer,
                "hint": hint,
                "max_damage": random.randint(damage_low, damage_high),
            }
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            last_error = exc
            continue
        except Exception as exc:
            # Gemini itself throwing (rate limit, transient 503 "high demand",
            # etc.) looks the same as any other retryable failure to this
            # loop -- without this, a single transient blip skips retrying
            # entirely and fails the whole request.
            last_error = exc
            error_str = str(exc)
            # A per-day quota (the free tier's usual cap) cannot recover within
            # a retry loop lasting a few seconds -- fail immediately instead of
            # burning ~(2+4)s of backoff sleep on retries that cannot succeed.
            is_daily_quota = "PerDay" in error_str
            is_transient = not is_daily_quota and any(
                marker in error_str for marker in ("429", "503", "UNAVAILABLE", "ResourceExhausted")
            )
            if is_transient and attempt < MAX_ATTEMPTS:
                await asyncio.sleep(attempt * 2)
                continue
            raise QuestionGenerationError(
                f"Failed to generate a valid question for topic={topic!r} "
                f"difficulty={difficulty!r} after {attempt} attempt(s): {exc}"
            ) from exc

    raise QuestionGenerationError(
        f"Failed to generate a valid question for topic={topic!r} "
        f"difficulty={difficulty!r} after {MAX_ATTEMPTS} attempts: {last_error}"
    )
