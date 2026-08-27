"""
AI client — calls the Gemini-backed /ai/ endpoints (routes/ai_real.py).
"""
import os
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
