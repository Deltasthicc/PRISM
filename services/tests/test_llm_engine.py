"""
Tests for services/llm_engine.py.

# NO BACKEND DEPENDENCY - fully solo testable

These tests call the REAL Gemini API (intentional -- we need to catch
prompt failures, JSON-parsing edge cases, and short-expected-answer retries
before this code is ever wired into the main backend). They are skipped
automatically if GEMINI_API_KEY is still the placeholder from .env.example,
so the suite doesn't hard-fail for anyone who hasn't configured a real key
yet.
"""

import uuid

import pytest

import config
from services.llm_engine import generate_question

pytestmark = pytest.mark.skipif(
    config.GEMINI_API_KEY in (None, "", "AIza..."),
    reason="GEMINI_API_KEY is not a real key -- set it in services/.env to run live LLM tests",
)

REQUIRED_FIELDS = {"question_id", "question", "expected_answer", "hint"}


def _assert_valid_question(result: dict) -> None:
    assert REQUIRED_FIELDS.issubset(result.keys())
    uuid.UUID(result["question_id"])  # raises ValueError if not a valid UUID
    assert len(result["expected_answer"]) >= 30
    assert len(result["hint"]) > 0
    assert len(result["question"]) > 0


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
async def test_generate_question_per_difficulty(difficulty):
    result = await generate_question(
        topic="arrays", difficulty=difficulty, domain=config.DEFAULT_DOMAIN
    )
    _assert_valid_question(result)
    print(f"\n[{difficulty}] arrays -> {result['question']}")
    print(f"  expected_answer: {result['expected_answer']}")
    print(f"  hint: {result['hint']}")


@pytest.mark.asyncio(loop_scope="module")
@pytest.mark.parametrize("topic", ["arrays", "binary_search", "dynamic_programming"])
async def test_generate_question_per_topic(topic):
    result = await generate_question(
        topic=topic, difficulty="medium", domain=config.DEFAULT_DOMAIN
    )
    _assert_valid_question(result)
    print(f"\n[medium] {topic} -> {result['question']}")
    print(f"  expected_answer: {result['expected_answer']}")
    print(f"  hint: {result['hint']}")
