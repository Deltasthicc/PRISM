"""
AI client — calls the Gemini-backed /ai/ endpoints (routes/ai_real.py).
"""
import os
from typing import Any
import httpx
from dotenv import load_dotenv

load_dotenv()

AI_SERVICE_URL = os.getenv("AI_SERVICE_URL", "http://localhost:8000").rstrip("/")
DEFAULT_DOMAIN = os.getenv("DEFAULT_DOMAIN", "Data Structures & Algorithms")

# One shared, connection-pooled client for the process lifetime instead of a
# fresh httpx.AsyncClient() (new TCP connection + TLS-negotiation-equivalent
# setup) per call -- every single room-enter and answer-submit used to pay
# that setup cost from scratch, several times per request.
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=60.0)
    return _client


async def call_generate_question(
    player_id: str, topic: str, difficulty: str = "medium", domain: str = None, monster_name: str = None,
) -> dict:
    """Call the question generation endpoint (mock or real)."""
    resp = await _get_client().post(f"{AI_SERVICE_URL}/ai/question/generate", json={
        "player_id": player_id, "topic": topic,
        "difficulty": difficulty, "domain": domain or DEFAULT_DOMAIN,
        "monster_name": monster_name,
    }, timeout=60.0)  # must exceed ai_real.py's worst-case ~45s Gemini retry backoff
    resp.raise_for_status()
    return resp.json()


async def call_judge_answer(question_id: str, player_answer: str, expected_answer: str) -> dict:
    """Call the answer judge endpoint."""
    resp = await _get_client().post(f"{AI_SERVICE_URL}/ai/answer/judge", json={
        "question_id": question_id, "player_answer": player_answer,
        "expected_answer": expected_answer,
    }, timeout=60.0)  # must exceed ai_real.py's worst-case ~45s Gemini retry backoff
    resp.raise_for_status()
    return resp.json()


async def call_next_difficulty(player_id: str, topic: str, accuracy_history: dict = None) -> dict:
    """Call the difficulty tuner endpoint with accuracy data for RL bandit."""
    resp = await _get_client().post(f"{AI_SERVICE_URL}/ai/difficulty/next", json={
        "player_id": player_id, "topic": topic,
        "accuracy_history": accuracy_history or {},
    }, timeout=10.0)
    resp.raise_for_status()
    return resp.json()


async def call_next_topic(player_id: str, accuracy_history: dict) -> dict:
    """Call the knowledge graph routing endpoint."""
    resp = await _get_client().post(f"{AI_SERVICE_URL}/ai/graph/next-topic", json={
        "player_id": player_id, "accuracy_history": accuracy_history,
    }, timeout=10.0)
    resp.raise_for_status()
    return resp.json()


# ─── Lane 4 New Assistant, Retrieval, Review & Evaluation Client Calls ───────

async def call_assistant_query(
    query: str,
    tenant_id: str = "default",
    user_id: str = "anonymous",
    roles: list[str] | None = None,
    source_id: str | None = None,
    top_k: int = 3,
) -> dict[str, Any]:
    """Call the Learner Assistant endpoint."""
    resp = await _get_client().post(
        f"{AI_SERVICE_URL}/ai/assistant/query",
        json={
            "query": query,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "roles": roles or ["learner"],
            "source_id": source_id,
            "top_k": top_k,
        },
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


async def call_retrieval_search(
    query: str,
    tenant_id: str = "default",
    user_id: str = "anonymous",
    roles: list[str] | None = None,
    source_id: str | None = None,
    top_k: int = 3,
    threshold: float = 0.20,
) -> dict[str, Any]:
    """Call the access-filtered retrieval search endpoint."""
    resp = await _get_client().post(
        f"{AI_SERVICE_URL}/ai/retrieval/search",
        json={
            "query": query,
            "tenant_id": tenant_id,
            "user_id": user_id,
            "roles": roles or ["learner"],
            "source_id": source_id,
            "top_k": top_k,
            "threshold": threshold,
        },
        timeout=15.0,
    )
    resp.raise_for_status()
    return resp.json()


async def call_retrieval_index(
    filename: str,
    text: str,
    source_id: str | None = None,
    tenant_id: str = "default",
    allowed_roles: list[str] | None = None,
) -> dict[str, Any]:
    """Call the document indexing endpoint."""
    resp = await _get_client().post(
        f"{AI_SERVICE_URL}/ai/retrieval/index",
        json={
            "filename": filename,
            "text": text,
            "source_id": source_id,
            "tenant_id": tenant_id,
            "allowed_roles": allowed_roles or ["learner", "trainer", "admin"],
        },
        timeout=20.0,
    )
    resp.raise_for_status()
    return resp.json()


async def call_quiz_review(
    item: dict[str, Any],
    target_state: str,
    reviewer_id: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Call the item review transition endpoint."""
    resp = await _get_client().post(
        f"{AI_SERVICE_URL}/ai/quiz/review",
        json={
            "item": item,
            "target_state": target_state,
            "reviewer_id": reviewer_id,
            "notes": notes,
        },
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()


async def call_evaluation_report() -> dict[str, Any]:
    """Call the gold-set evaluation report endpoint."""
    resp = await _get_client().get(
        f"{AI_SERVICE_URL}/ai/evaluation/report",
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()
