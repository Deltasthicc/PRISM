"""
Tests for services/nlp_judge.py.

# NO BACKEND DEPENDENCY - fully solo testable

No API calls except for whichever case happens to land in the borderline
score range (config.JUDGE_FALLBACK_RANGE_LOW..HIGH) -- that case alone will
fire the secondary Gemini adjudication call. All inputs are hardcoded
DSA-relevant string pairs; nothing here depends on the main backend.
"""

import pytest

from services.nlp_judge import judge_answer


@pytest.mark.asyncio(loop_scope="module")
async def test_correct_paraphrase():
    result = await judge_answer(
        player_answer="It splits the array in half each time and checks the middle value to find the target",
        expected_answer="Binary search works by repeatedly dividing the search interval in half and comparing the middle element",
        question="Explain how binary search works.",
    )
    print(f"\n[correct_paraphrase] score={result['score']} verdict={result['verdict']} feedback={result['feedback']}")
    assert result["verdict"] == "correct"


@pytest.mark.asyncio(loop_scope="module")
async def test_completely_wrong():
    result = await judge_answer(
        player_answer="A linked list stores elements in nodes with pointers",
        expected_answer="Binary search works by repeatedly dividing the search interval in half and comparing the middle element",
        question="Explain how binary search works.",
    )
    print(f"\n[completely_wrong] score={result['score']} verdict={result['verdict']} feedback={result['feedback']}")
    assert result["verdict"] == "incorrect"


@pytest.mark.asyncio(loop_scope="module")
async def test_partial_wrong_complexity():
    result = await judge_answer(
        player_answer="Binary search is faster than linear search, around O(n) I think",
        expected_answer="Binary search has O(log n) time complexity",
        question="What is the time complexity of binary search?",
    )
    print(f"\n[partial_wrong_complexity] score={result['score']} verdict={result['verdict']} feedback={result['feedback']}")
    assert result["verdict"] == "partial"


@pytest.mark.asyncio(loop_scope="module")
async def test_semantically_identical_different_words():
    """Key test: keyword matching would fail this; embeddings should not."""
    result = await judge_answer(
        player_answer="The most recently added item is always removed first in a stack",
        expected_answer="A stack follows Last In First Out order",
        question="Describe the ordering behavior of a stack.",
    )
    print(f"\n[semantically_identical] score={result['score']} verdict={result['verdict']} feedback={result['feedback']}")
    assert result["verdict"] == "correct"


@pytest.mark.asyncio(loop_scope="module")
async def test_one_word_answer():
    result = await judge_answer(
        player_answer="logarithmic",
        expected_answer="Binary search has O(log n) time complexity",
        question="What is the time complexity of binary search?",
    )
    print(f"\n[one_word] score={result['score']} verdict={result['verdict']} feedback={result['feedback']}")
    assert result["verdict"] in ("partial", "incorrect")


@pytest.mark.asyncio(loop_scope="module")
async def test_empty_answer():
    result = await judge_answer(
        player_answer="",
        expected_answer="Binary search has O(log n) time complexity",
        question="What is the time complexity of binary search?",
    )
    print(f"\n[empty] score={result['score']} verdict={result['verdict']} feedback={result['feedback']}")
    assert result["verdict"] == "incorrect"
    assert result["score"] == 0.0
