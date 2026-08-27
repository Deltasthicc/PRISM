"""
Real AI endpoints — powered by Gemini for question generation and answer judging.
"""
import os
import uuid
import json
import random
import re
import asyncio
from fastapi import APIRouter
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# Configure Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel(os.getenv("LLM_MODEL", "gemini-flash-lite-latest"))

router = APIRouter(prefix="/ai", tags=["AI (Gemini)"])

DEFAULT_DOMAIN = os.getenv("DEFAULT_DOMAIN", "Data Structures & Algorithms")

# Mirrors services/services/llm_engine.py's DAMAGE_RANGE_BY_DIFFICULTY --
# keep both in sync if you change one. This route is a self-contained
# fallback (used only if AI_SERVICE_URL points back at this same server
# instead of the standalone services/ process); the live path is services/.
DAMAGE_RANGE_BY_DIFFICULTY = {
    "easy": (40, 70),
    "medium": (70, 110),
    "hard": (110, 160),
}


def _parse_json_from_response(text: str) -> dict:
    """Extract JSON from Gemini response, handling markdown fences."""
    # Try to find JSON in code fences
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        text = match.group(1)
    # Try direct parse
    return json.loads(text.strip())


async def _call_gemini_with_retry(prompt: str, max_retries: int = 3) -> str:
    """Call Gemini with exponential backoff on rate-limit (429) errors.

    The Gemini SDK call itself is synchronous/blocking; running it directly
    inside an async route handler would freeze the whole event loop (every
    other in-flight request) for the duration of the call and any retry
    backoff. `asyncio.to_thread` runs it on a worker thread instead.
    """
    for attempt in range(max_retries):
        try:
            response = await asyncio.to_thread(model.generate_content, prompt)
            return response.text
        except Exception as e:
            error_str = str(e)
            # A per-day quota (the free tier's usual cap) cannot recover
            # within a 15-45s retry loop -- fail immediately instead of
            # burning that time on retries that cannot succeed.
            is_daily_quota = "PerDay" in error_str
            is_rate_limit = not is_daily_quota and ("429" in error_str or "ResourceExhausted" in error_str)
            if is_rate_limit and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 15  # 15s, 30s backoff
                print(f"[AI] Rate limited (attempt {attempt + 1}), waiting {wait_time}s...")
                await asyncio.sleep(wait_time)
            else:
                print(f"[AI] Gemini call failed (attempt {attempt + 1}): {type(e).__name__}: {error_str[:200]}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                else:
                    raise


@router.post("/question/generate")
async def generate_question(body: dict):
    """Generate a unique question using Gemini."""
    topic = body.get("topic", "arrays")
    difficulty = body.get("difficulty", "medium")
    domain = body.get("domain", DEFAULT_DOMAIN)
    monster_name = body.get("monster_name") or "the dungeon's guardian"
    damage_low, damage_high = DAMAGE_RANGE_BY_DIFFICULTY.get(difficulty, (70, 110))
    max_damage = random.randint(damage_low, damage_high)

    prompt = f"""You are {monster_name}, a dungeon monster in an educational RPG.
Topic: {topic}
Difficulty: {difficulty}  # easy = recall, medium = application, hard = analysis/synthesis
Subject domain: {domain}

Generate a single exam-quality question for a student fighting you. Stay in
character as {monster_name} throughout the question text -- do not invent,
name, or reference any other monster or creature.
The question must be unique and different each time.
For easy: test basic recall and definitions.
For medium: test application and problem-solving.
For hard: test analysis, synthesis, and edge cases.

Respond in JSON only, no preamble:
{{
  "question": "...",
  "expected_answer": "...",
  "hint": "..."
}}"""

    try:
        text = await _call_gemini_with_retry(prompt)
        data = _parse_json_from_response(text)

        if "question" not in data or "expected_answer" not in data:
            raise ValueError("Missing required fields in Gemini response")

        question_id = str(uuid.uuid4())
        return {
            "question_id": question_id,
            "question": data["question"],
            "expected_answer": data["expected_answer"],
            "hint": data.get("hint", "Think carefully about this topic."),
            "topic": topic,
            "difficulty": difficulty,
            "max_damage": max_damage,
        }
    except Exception as e:
        print(f"[AI] Question generation failed completely: {e}")

    # Fallback if all retries fail
    question_id = str(uuid.uuid4())
    return {
        "question_id": question_id,
        "question": f"Explain the concept of {topic.replace('_', ' ')} in {domain}.",
        "expected_answer": f"A comprehensive explanation of {topic.replace('_', ' ')}.",
        "hint": "Think about the fundamentals.",
        "topic": topic,
        "difficulty": difficulty,
        "max_damage": max_damage,
    }


@router.post("/answer/judge")
async def judge_answer(body: dict):
    """Judge a player's answer using Gemini for semantic evaluation."""
    player_answer = body.get("player_answer", "").strip()
    expected_answer = body.get("expected_answer", "").strip()

    if not player_answer:
        return {
            "score": 0.0,
            "damage_multiplier": 0.0,
            "verdict": "incorrect",
            "feedback": "No answer provided.",
        }

    prompt = f"""You are a strict but fair exam grader in an educational RPG dungeon.

Expected answer: {expected_answer}
Student's answer: {player_answer}

Evaluate how correct the student's answer is.
Consider semantic meaning, not just exact wording.

Respond in JSON only:
{{
  "verdict": "correct" or "partial" or "incorrect",
  "score": 0.0 to 1.0,
  "feedback": "brief encouraging feedback explaining what was right/wrong"
}}"""

    try:
        text = await _call_gemini_with_retry(prompt)
        data = _parse_json_from_response(text)

        verdict = data.get("verdict", "incorrect")
        score = float(data.get("score", 0.0))
        feedback = data.get("feedback", "")

        # Map verdict to damage multiplier
        damage_map = {"correct": 2.0, "partial": 1.0, "incorrect": 0.0}
        damage_multiplier = damage_map.get(verdict, 0.0)

        return {
            "score": round(score, 2),
            "damage_multiplier": damage_multiplier,
            "verdict": verdict,
            "feedback": feedback,
        }
    except Exception:
        # Fallback to simple word overlap
        player_words = set(player_answer.lower().split())
        expected_words = set(expected_answer.lower().split())
        overlap = len(player_words & expected_words) / max(len(expected_words), 1)

        correct_threshold = float(os.getenv("JUDGE_CORRECT_THRESHOLD", "0.65"))
        partial_threshold = float(os.getenv("JUDGE_PARTIAL_THRESHOLD", "0.30"))

        if overlap >= correct_threshold:
            return {"score": round(overlap, 2), "damage_multiplier": 2.0,
                    "verdict": "correct", "feedback": "Good answer!"}
        elif overlap >= partial_threshold:
            return {"score": round(overlap, 2), "damage_multiplier": 1.0,
                    "verdict": "partial", "feedback": "Partially correct."}
        else:
            return {"score": round(overlap, 2), "damage_multiplier": 0.0,
                    "verdict": "incorrect", "feedback": "Not quite right."}


@router.post("/difficulty/next")
async def next_difficulty(body: dict):
    """Determine next difficulty using RL epsilon-greedy bandit."""
    import random
    accuracy_history = body.get("accuracy_history", {})
    topic = body.get("topic", "")

    epsilon = float(os.getenv("RL_EPSILON", "0.1"))
    hard_threshold = float(os.getenv("RL_HARD_THRESHOLD", "0.80"))
    medium_threshold = float(os.getenv("RL_MEDIUM_THRESHOLD", "0.50"))

    # Epsilon-greedy exploration
    if random.random() < epsilon:
        difficulty = random.choice(["easy", "medium", "hard"])
    else:
        topic_accuracy = accuracy_history.get(topic, 0.5)
        if topic_accuracy > hard_threshold:
            difficulty = "hard"
        elif topic_accuracy > medium_threshold:
            difficulty = "medium"
        else:
            difficulty = "easy"

    return {"difficulty": difficulty}


@router.post("/graph/next-topic")
async def next_topic(body: dict):
    """Route to weakest unlocked topic using knowledge graph."""
    from services.knowledge_graph import get_next_topic, get_weak_topics

    accuracy_history = body.get("accuracy_history", {})
    next_t = get_next_topic(accuracy_history)
    weak = get_weak_topics(accuracy_history)

    return {"next_topic": next_t, "weak_topics": weak}


@router.get("/dashboard/{player_id}")
async def dashboard(player_id: str):
    """Return ML dashboard data for a player."""
    from db.database import SessionLocal
    from models.accuracy_history import AccuracyHistory
    from models.submission import AnswerSubmission
    from models.question import Question
    from services.knowledge_graph import TOPIC_GRAPH

    db = SessionLocal()
    try:
        histories = db.query(AccuracyHistory).filter(
            AccuracyHistory.player_id == player_id
        ).all()

        topic_accuracies = {h.topic: h.recent_accuracy for h in histories}

        # Last 20 submissions with topic names
        submissions = db.query(AnswerSubmission, Question).join(
            Question, AnswerSubmission.question_id == Question.question_id
        ).filter(
            AnswerSubmission.player_id == player_id
        ).order_by(AnswerSubmission.submitted_at.desc()).limit(20).all()

        score_history = [
            {"score": s.score, "verdict": s.verdict, "topic": q.topic,
             "difficulty": q.difficulty, "response_time_ms": s.response_time_ms,
             "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
             "question": q.question_text, "player_answer": s.player_answer}
            for s, q in submissions
        ]

        # Difficulty history — recent difficulties served
        difficulty_history = [
            {"topic": q.topic, "difficulty": q.difficulty}
            for s, q in submissions
        ]

        # Graph state — locked/unlocked/mastered per topic
        graph_state = {}
        for topic, prereqs in TOPIC_GRAPH.items():
            acc = topic_accuracies.get(topic, 0)
            if acc >= 0.9:
                graph_state[topic] = "mastered"
            elif not prereqs:
                # Root topics are always unlocked
                graph_state[topic] = "unlocked"
            elif all(topic_accuracies.get(p, 0) > 0.65 for p in prereqs):
                graph_state[topic] = "unlocked"
            else:
                graph_state[topic] = "locked"

        return {
            "player_id": player_id,
            "topic_accuracies": topic_accuracies,
            "score_history": score_history,
            "difficulty_history": difficulty_history,
            "graph_state": graph_state,
        }
    finally:
        db.close()
