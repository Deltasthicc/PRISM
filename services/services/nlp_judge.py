"""
NLP Answer Judge (README section 4.2).

NO BACKEND DEPENDENCY for the core scoring path. Both player_answer and
expected_answer arrive directly in the request body -- this module never
needs to look anything up itself.
"""

import asyncio
import re

import numpy as np
from google import genai
from google.genai import types
from sentence_transformers import SentenceTransformer

import config

_model = None
_client = None


def _get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def _load_and_warm_model():
    model = _get_model()
    # Constructing SentenceTransformer only loads the weights -- the first
    # real .encode() call still separately pays PyTorch/tokenizer JIT-style
    # initialization cost. Run one throwaway encode here too so *that* cost
    # also lands at startup, not on a player's first answer.
    model.encode(["warm up"])
    return model


async def warm_up():
    """
    Fully warm the embedding path (model load + first-inference init) off the
    event loop thread now, instead of paying for it on the request path.

    Without this, the first real /ai/answer/judge call can take tens of
    seconds -- the very first player of a session would see judging hang.
    Call this once from main.py's startup lifespan instead.
    """
    await asyncio.to_thread(_load_and_warm_model)


def _get_client():
    global _client
    if not config.GEMINI_API_KEY:
        return None
    if _client is None:
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client

FALLBACK_PROMPT_TEMPLATE = """Given question: {question}
Expected answer: {expected_answer}
Student answered: {player_answer}
Is the student's answer essentially correct? Reply only: yes / partial / no"""

# DECISION (locked with user): the LLM fallback is a *clean override*. When
# it fires, score and damage_multiplier are snapped to the verdict's
# canonical values below, rather than blended with the original cosine score.
_CLEAN_OVERRIDE = {
    "correct": (1.0, 2.0),
    "partial": (0.5, 1.0),
    "incorrect": (0.0, 0.0),
}
_MULTIPLIER_BY_VERDICT = {"correct": 2.0, "partial": 1.0, "incorrect": 0.0}

_FEEDBACK_BY_VERDICT = {
    "correct": "Correct! Your answer captures the key idea this question was testing.",
    "partial": "Partially correct — you're on the right track, but your answer is missing some important detail.",
    "incorrect": "Incorrect — your answer doesn't match what this question was testing for.",
}


def _cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    similarity = float(np.dot(vec_a, vec_b) / (np.linalg.norm(vec_a) * np.linalg.norm(vec_b)))
    return max(0.0, min(1.0, similarity))  # clamp float drift outside [0, 1]


def _verdict_from_score(score: float) -> str:
    if score >= config.JUDGE_CORRECT_THRESHOLD:
        return "correct"
    elif score >= config.JUDGE_PARTIAL_THRESHOLD:
        return "partial"
    return "incorrect"


def _complexity_terms(text: str) -> set[str]:
    return {
        re.sub(r"\s+", "", term.lower())
        for term in re.findall(r"\bO\s*\(([^)]+)\)", text, flags=re.IGNORECASE)
    }


def _local_fallback_verdict(
    score: float, player_answer: str, expected_answer: str
) -> str:
    player_complexities = _complexity_terms(player_answer)
    expected_complexities = _complexity_terms(expected_answer)
    if (
        player_complexities
        and expected_complexities
        and player_complexities.isdisjoint(expected_complexities)
    ):
        return "partial" if score >= config.JUDGE_PARTIAL_THRESHOLD else "incorrect"
    if score >= config.JUDGE_LOCAL_CORRECT_THRESHOLD:
        return "correct"
    return _verdict_from_score(score)


async def _llm_fallback_verdict(
    question: str, expected_answer: str, player_answer: str, fallback_score: float
) -> str:
    """Secondary Gemini call for scores landing in the borderline range."""
    prompt = FALLBACK_PROMPT_TEMPLATE.format(
        question=question, expected_answer=expected_answer, player_answer=player_answer
    )
    client = _get_client()
    if client is None:
        return _local_fallback_verdict(
            fallback_score, player_answer, expected_answer
        )
    try:
        response = await client.aio.models.generate_content(
            model=config.LLM_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                max_output_tokens=10,
                temperature=0.0,
                # Without an explicit timeout this call can hang far longer
                # than a player will wait for "the judge to consider" --
                # there's already a solid local fallback right below, so
                # failing fast into it beats hanging on a slow/stuck request.
                http_options=types.HttpOptions(timeout=8000),  # ms
            ),
        )
    except Exception:
        return _local_fallback_verdict(
            fallback_score, player_answer, expected_answer
        )
    reply = (response.text or "").strip().lower()
    if "yes" in reply:
        return "correct"
    if "partial" in reply:
        return "partial"
    if "no" in reply:
        return "incorrect"
    # Fallback call returned something unparseable -- fall back to the
    # threshold-based verdict rather than crashing the answer-submit flow.
    return _local_fallback_verdict(fallback_score, player_answer, expected_answer)


# INTEGRATION NOTE: In production, expected_answer comes from the Question
# record that the main backend stored when POST /game/room/enter was called.
# It retrieves it by question_id and passes it here. For solo testing, we
# pass expected_answer directly in the request body (see tests/test_nlp_judge.py).
async def judge_answer(player_answer: str, expected_answer: str, question: str) -> dict:
    """
    Score a player's free-text answer against the expected answer.

    Inputs:
        player_answer: str -- raw text the player typed in combat.
        expected_answer: str -- from the Question record (see integration
            note above).
        question: str -- only used if the LLM fallback fires, to give the
            adjudicator full context.

    Output:
        dict matching the POST /ai/answer/judge response contract:
        { score, damage_multiplier, verdict, feedback }

    Backend dependency: NONE for this function's inputs (both strings are
    supplied by the caller). Fully testable solo.
    """
    if not player_answer or not player_answer.strip():
        return {
            "score": 0.0,
            "damage_multiplier": 0.0,
            "verdict": "incorrect",
            "feedback": "No answer was submitted, so no credit can be given for this question.",
        }

    # SentenceTransformer.encode() is synchronous and CPU-bound; running it
    # directly here would block the event loop (and every other in-flight
    # request) for the duration of the embedding call.
    embeddings = await asyncio.to_thread(_get_model().encode, [player_answer, expected_answer])
    score = _cosine_similarity(embeddings[0], embeddings[1])

    if config.JUDGE_FALLBACK_RANGE_LOW <= score <= config.JUDGE_FALLBACK_RANGE_HIGH:
        verdict = await _llm_fallback_verdict(
            question, expected_answer, player_answer, score
        )
        final_score, damage_multiplier = _CLEAN_OVERRIDE[verdict]
    else:
        verdict = _verdict_from_score(score)
        final_score = score
        damage_multiplier = _MULTIPLIER_BY_VERDICT[verdict]

    return {
        "score": final_score,
        "damage_multiplier": damage_multiplier,
        "verdict": verdict,
        "feedback": _FEEDBACK_BY_VERDICT[verdict],
    }
