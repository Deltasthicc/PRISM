"""
Real AI endpoints — powered by Gemini for question generation and answer judging,
plus Lane 4 RAG retrieval, Learner Assistant, quiz review, and evaluation benchmarks.
Authenticated and authorized via Lane 2 RBAC dependencies.
"""
import asyncio
import json
import os
import random
import re
import uuid
from typing import Any

import google.generativeai as genai
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ai.assistant import default_assistant
from ai.evaluation import run_gold_set_evaluation
from ai.ingestion import ingest_document
from ai.provenance import AccessContext, ItemReviewState, QuizQuestionItem, SourceLocator
from ai.quiz_engine import QuizReviewWorkflow
from ai.retrieval import create_citations_from_retrieved_chunks, default_chunk_store
from db.database import get_db
from models.accuracy_history import AccuracyHistory
from models.player import Player
from models.question import Question
from models.submission import AnswerSubmission
from routes.authorization import (
    require_deployment_tenant_dependency,
    require_own_player_dependency,
    require_permission_dependency,
    require_principal,
)
from security.rbac import (
    AuthorizationError,
    BoundPrincipal,
    Permission,
    permissions_for,
    scoped_to_own_player,
)
from services.knowledge_graph import TOPIC_GRAPH, get_next_topic, get_weak_topics

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
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        text = match.group(1)
    return json.loads(text.strip())


async def _call_gemini_with_retry(prompt: str, max_retries: int = 3) -> str:
    """Call Gemini with exponential backoff on rate-limit (429) errors."""
    for attempt in range(max_retries):
        try:
            response = await asyncio.to_thread(model.generate_content, prompt)
            return response.text
        except Exception as e:
            error_str = str(e)
            is_daily_quota = "PerDay" in error_str
            is_rate_limit = not is_daily_quota and ("429" in error_str or "ResourceExhausted" in error_str)
            if is_rate_limit and attempt < max_retries - 1:
                wait_time = (attempt + 1) * 15
                await asyncio.sleep(wait_time)
            else:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2)
                else:
                    raise


@router.post("/question/generate")
async def generate_question(
    body: dict,
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.PRACTICE_SELF_WRITE)
    ),
):
    """Generate a unique question using Gemini."""
    player_id = body.get("player_id")
    if player_id:
        try:
            scoped_to_own_player(principal, player_id)
        except AuthorizationError as exc:
            raise HTTPException(status_code=403, detail="Access denied") from exc

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
async def judge_answer(
    body: dict,
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.PRACTICE_SELF_WRITE)
    ),
):
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
async def next_difficulty(
    body: dict,
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.PRACTICE_SELF_WRITE)
    ),
):
    """Determine next difficulty using RL epsilon-greedy bandit."""
    player_id = body.get("player_id")
    if player_id:
        try:
            scoped_to_own_player(principal, player_id)
        except AuthorizationError as exc:
            raise HTTPException(status_code=403, detail="Access denied") from exc

    accuracy_history = body.get("accuracy_history", {})
    topic = body.get("topic", "")

    epsilon = float(os.getenv("RL_EPSILON", "0.1"))
    hard_threshold = float(os.getenv("RL_HARD_THRESHOLD", "0.80"))
    medium_threshold = float(os.getenv("RL_MEDIUM_THRESHOLD", "0.50"))

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
async def next_topic(
    body: dict,
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.PRACTICE_SELF_WRITE)
    ),
):
    """Route to weakest unlocked topic using knowledge graph."""
    player_id = body.get("player_id")
    if player_id:
        try:
            scoped_to_own_player(principal, player_id)
        except AuthorizationError as exc:
            raise HTTPException(status_code=403, detail="Access denied") from exc

    accuracy_history = body.get("accuracy_history", {})
    next_t = get_next_topic(accuracy_history)
    weak = get_weak_topics(accuracy_history)

    return {"next_topic": next_t, "weak_topics": weak}


@router.get("/dashboard/{player_id}")
async def dashboard(
    player_id: str,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_own_player_dependency(Permission.PROFILE_SELF_READ)
    ),
):
    """Return ML dashboard data for a player."""
    player = db.query(Player).filter(Player.player_id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    histories = db.query(AccuracyHistory).filter(
        AccuracyHistory.player_id == player_id
    ).all()

    topic_accuracies = {h.topic: h.recent_accuracy for h in histories}

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

    difficulty_history = [
        {"topic": q.topic, "difficulty": q.difficulty}
        for s, q in submissions
    ]

    graph_state = {}
    for topic, prereqs in TOPIC_GRAPH.items():
        acc = topic_accuracies.get(topic, 0)
        if acc >= 0.9:
            graph_state[topic] = "mastered"
        elif not prereqs:
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


# ─── Lane 4 Authenticated RAG, Assistant, Review, and Evaluation ─────────────

@router.post("/assistant/query")
async def assistant_query(
    body: dict,
    principal: BoundPrincipal = Depends(require_principal),
):
    """Answer a learner query using access-filtered, cited retrieval."""
    query = body.get("query", "")
    if not query:
        raise HTTPException(status_code=422, detail="Query string is required.")

    # CRITICAL: Derive tenant_id, user_id, and roles from authenticated principal
    tenant_id = principal.tenant_scope
    user_id = principal.player_id or principal.subject.subject_id
    roles = tuple(principal.roles)
    source_id = body.get("source_id")
    top_k = int(body.get("top_k", 3))

    ctx = AccessContext(tenant_id=tenant_id, user_id=user_id, roles=roles)
    resp = await default_assistant.answer_query(
        query=query,
        access_context=ctx,
        source_id=source_id,
        top_k=top_k,
    )
    return resp.to_dict()


@router.post("/retrieval/search")
async def retrieval_search(
    body: dict,
    principal: BoundPrincipal = Depends(require_principal),
):
    """Execute access-filtered chunk retrieval with relevance scoring."""
    query = body.get("query", "")
    if not query:
        raise HTTPException(status_code=422, detail="Query string is required.")

    # CRITICAL: Derive tenant_id, user_id, and roles from authenticated principal
    tenant_id = principal.tenant_scope
    user_id = principal.player_id or principal.subject.subject_id
    roles = tuple(principal.roles)
    source_id = body.get("source_id")
    top_k = int(body.get("top_k", 3))
    threshold = float(body.get("threshold", 0.20))

    ctx = AccessContext(tenant_id=tenant_id, user_id=user_id, roles=roles)
    retrieved_chunks, is_insufficient = default_chunk_store.search(
        query=query,
        access_context=ctx,
        source_id=source_id,
        top_k=top_k,
        threshold=threshold,
    )
    citations = create_citations_from_retrieved_chunks(retrieved_chunks)

    return {
        "query": query,
        "retrieved_count": len(retrieved_chunks),
        "is_insufficient_evidence": is_insufficient,
        "results": [rc.to_dict() for rc in retrieved_chunks],
        "citations": [c.to_dict() for c in citations],
    }


@router.post("/retrieval/index")
async def retrieval_index(
    body: dict,
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.CONTENT_DRAFT_CREATE)
    ),
):
    """Ingest and index a document payload into the in-memory retrieval store."""
    filename = body.get("filename", "document.txt")
    raw_text = body.get("text", "")
    if not raw_text:
        raise HTTPException(status_code=422, detail="Document text is required.")

    source_id = body.get("source_id")
    # CRITICAL: Derive tenant_id from authenticated principal
    tenant_id = principal.tenant_scope
    allowed_roles = body.get("allowed_roles") or ["learner", "trainer", "admin"]

    source_ver, chunks, _ = ingest_document(
        filename=filename,
        content=raw_text.encode("utf-8"),
        source_id=source_id,
        tenant_id=tenant_id,
        allowed_roles=allowed_roles,
    )
    added_count = default_chunk_store.add_chunks(chunks)

    return {
        "source_id": source_ver.source_id,
        "source_version": source_ver.version,
        "sha256": source_ver.sha256,
        "filename": source_ver.filename,
        "chunks_indexed": added_count,
        "character_count": source_ver.character_count,
    }


@router.post("/quiz/review")
async def quiz_review_item(
    body: dict,
    principal: BoundPrincipal = Depends(require_principal),
):
    """Transition an assessment item through the review lifecycle state machine."""
    item_dict = body.get("item")
    if not item_dict:
        raise HTTPException(status_code=422, detail="Item payload is required.")

    target_state_str = body.get("target_state")
    try:
        target_state = ItemReviewState(target_state_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid target review state: '{target_state_str}'. Must be one of: {[s.value for s in ItemReviewState]}",
        )

    # Permission check based on target lifecycle state
    user_perms = permissions_for(principal)
    if target_state in {
        ItemReviewState.APPROVED,
        ItemReviewState.EXPERT_REVIEW,
        ItemReviewState.PILOT,
        ItemReviewState.PUBLISHED,
        ItemReviewState.RETIRED,
    }:
        if (
            Permission.CONTENT_REVIEW not in user_perms
            and Permission.CONTENT_APPROVE not in user_perms
        ):
            raise HTTPException(status_code=403, detail="Access denied")
    elif target_state in {ItemReviewState.AUTO_CHECKED, ItemReviewState.DRAFT}:
        if (
            Permission.CONTENT_DRAFT_CREATE not in user_perms
            and Permission.CONTENT_REVIEW not in user_perms
        ):
            raise HTTPException(status_code=403, detail="Access denied")

    # CRITICAL: Derive reviewer identity from authenticated principal
    reviewer_id = principal.audit_actor
    notes = body.get("notes")

    # Reconstruct item object
    locators = [
        SourceLocator(
            locator_type=loc.get("locator_type", "section"),
            index=loc.get("index", 1),
            label=loc.get("label", "General"),
            start_char=loc.get("start_char", 0),
            end_char=loc.get("end_char", 0),
        )
        for loc in item_dict.get("source_locators", [])
    ]

    item = QuizQuestionItem(
        question_id=item_dict.get("question_id", str(uuid.uuid4())),
        source_id=item_dict.get("source_id", "unknown"),
        source_version=item_dict.get("source_version", 1),
        chunk_ids=item_dict.get("chunk_ids", []),
        source_locators=locators,
        question=item_dict.get("question", ""),
        options=item_dict.get("options", []),
        answer_index=item_dict.get("answer_index", 0),
        explanation=item_dict.get("explanation", ""),
        source_excerpt=item_dict.get("source_excerpt", ""),
        competency=item_dict.get("competency", "Source comprehension"),
        bloom_level=item_dict.get("bloom_level", "understand"),
        review_state=ItemReviewState(item_dict.get("review_state", "draft")),
        validation_notes=item_dict.get("validation_notes", []),
    )

    try:
        updated_item = QuizReviewWorkflow.transition_state(
            item=item,
            target_state=target_state,
            reviewer_id=reviewer_id,
            notes=notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"item": updated_item.to_dict()}


@router.get("/evaluation/report")
async def evaluation_report(
    principal: BoundPrincipal = Depends(require_principal),
):
    """Run deterministic gold-set benchmark evaluation and return report."""
    user_perms = permissions_for(principal)
    allowed_perms = {
        Permission.ORGANIZATION_ANALYTICS_READ,
        Permission.AUDIT_READ,
        Permission.CONTENT_REVIEW,
    }
    if not (user_perms & allowed_perms):
        raise HTTPException(status_code=403, detail="Access denied")

    report = await run_gold_set_evaluation()
    return report.to_dict()
