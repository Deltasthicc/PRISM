"""Lane 4 (Content AI, RAG & Evaluation) — Explicit, Testable Answer Grading.

Evaluates student free-text answers against expected answers and source evidence,
producing structured grading verdicts, scores, feedback, and grader versioning.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import google.generativeai as genai

from ai.security import sanitize_untrusted_text


@dataclass
class GradingResult:
    """Explicit evaluation record for an answer submission."""
    learner_answer: str
    expected_answer: str
    score: float  # 0.0 to 1.0
    verdict: str  # correct | partial | incorrect
    damage_multiplier: float  # 2.0 (correct), 1.0 (partial), 0.0 (incorrect)
    feedback: str
    evidence_quote: str | None = None
    grader_version: str = "gemini-flash-lite-latest"
    evaluated_at: str = ""

    def __post_init__(self) -> None:
        if not self.evaluated_at:
            self.evaluated_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return {
            "learner_answer": self.learner_answer,
            "expected_answer": self.expected_answer,
            "score": round(self.score, 2),
            "verdict": self.verdict,
            "damage_multiplier": self.damage_multiplier,
            "feedback": self.feedback,
            "evidence_quote": self.evidence_quote,
            "grader_version": self.grader_version,
            "evaluated_at": self.evaluated_at,
        }


def _word_overlap_grade(learner_answer: str, expected_answer: str) -> tuple[float, str, str]:
    """Deterministic token overlap fallback grader."""
    learner_words = set(re.findall(r"\b\w+\b", learner_answer.lower()))
    expected_words = set(re.findall(r"\b\w+\b", expected_answer.lower()))

    if not expected_words:
        return 0.0, "incorrect", "No expected answer was specified."

    overlap = len(learner_words & expected_words) / max(len(expected_words), 1)
    score = round(min(1.0, overlap), 2)

    if score >= 0.65:
        verdict = "correct"
        feedback = "Correct! Your answer accurately matches the key concepts."
    elif score >= 0.30:
        verdict = "partial"
        feedback = "Partially correct. You captured some concepts but missed key details."
    else:
        verdict = "incorrect"
        feedback = "Incorrect. Your answer does not demonstrate understanding of the required concept."

    return score, verdict, feedback


async def grade_student_answer(
    learner_answer: str,
    expected_answer: str,
    question_text: str = "",
    evidence_quote: str | None = None,
    correct_threshold: float = 0.65,
    partial_threshold: float = 0.30,
) -> GradingResult:
    """Evaluate a learner's free-text answer against ground truth."""
    clean_learner = sanitize_untrusted_text(learner_answer, max_chars=2000)
    clean_expected = sanitize_untrusted_text(expected_answer, max_chars=2000)

    if not clean_learner:
        return GradingResult(
            learner_answer="",
            expected_answer=clean_expected,
            score=0.0,
            verdict="incorrect",
            damage_multiplier=0.0,
            feedback="No answer was provided.",
            evidence_quote=evidence_quote,
            grader_version="deterministic-empty-v1",
        )

    # Check exact match first
    if clean_learner.lower() == clean_expected.lower():
        return GradingResult(
            learner_answer=clean_learner,
            expected_answer=clean_expected,
            score=1.0,
            verdict="correct",
            damage_multiplier=2.0,
            feedback="Perfect! Your answer matches the expected answer exactly.",
            evidence_quote=evidence_quote,
            grader_version="deterministic-exact-v1",
        )

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key.startswith("your_"):
        score, verdict, feedback = _word_overlap_grade(clean_learner, clean_expected)
        damage_map = {"correct": 2.0, "partial": 1.0, "incorrect": 0.0}
        return GradingResult(
            learner_answer=clean_learner,
            expected_answer=clean_expected,
            score=score,
            verdict=verdict,
            damage_multiplier=damage_map[verdict],
            feedback=feedback,
            evidence_quote=evidence_quote,
            grader_version="deterministic-overlap-v1",
        )

    # Semantic grading via Gemini
    genai.configure(api_key=api_key)
    model_name = os.getenv("LLM_MODEL", "gemini-flash-lite-latest")
    model = genai.GenerativeModel(model_name)

    prompt = f"""You are a strict, fair, and objective educational grader evaluating student free-text responses.
Evaluate semantic meaning, conceptual accuracy, and completeness, not just exact wording.

Question: {question_text or "General concept check"}
Expected Answer: {clean_expected}
Student Answer: {clean_learner}
Reference Evidence: {evidence_quote or "N/A"}

Respond in valid JSON only with this schema:
{{
  "score": 0.0 to 1.0,
  "verdict": "correct" | "partial" | "incorrect",
  "feedback": "Concise, constructive feedback explaining why the answer was scored this way"
}}"""

    # 1. Call Gemini Provider
    try:
        response = await asyncio.wait_for(
            asyncio.to_thread(model.generate_content, prompt), timeout=20.0
        )
        raw_text = response.text or ""
    except Exception as exc:
        score, verdict, feedback = _word_overlap_grade(clean_learner, clean_expected)
        damage_map = {"correct": 2.0, "partial": 1.0, "incorrect": 0.0}
        return GradingResult(
            learner_answer=clean_learner,
            expected_answer=clean_expected,
            score=score,
            verdict=verdict,
            damage_multiplier=damage_map[verdict],
            feedback=f"{feedback} (Graded via fallback due to provider failure: {type(exc).__name__})",
            evidence_quote=evidence_quote,
            grader_version=f"fallback-provider-error:{type(exc).__name__}",
        )

    # 2. Parse Model JSON Response
    try:
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", raw_text, re.DOTALL)
        json_str = match.group(1) if match else raw_text
        data = json.loads(json_str.strip())

        score = float(data.get("score", 0.0))
        verdict = str(data.get("verdict", "incorrect")).lower()
        if verdict not in {"correct", "partial", "incorrect"}:
            verdict = "correct" if score >= correct_threshold else "partial" if score >= partial_threshold else "incorrect"

        damage_map = {"correct": 2.0, "partial": 1.0, "incorrect": 0.0}
        return GradingResult(
            learner_answer=clean_learner,
            expected_answer=clean_expected,
            score=min(1.0, max(0.0, score)),
            verdict=verdict,
            damage_multiplier=damage_map[verdict],
            feedback=data.get("feedback", "Evaluated via semantic model."),
            evidence_quote=evidence_quote,
            grader_version=model_name,
        )
    except Exception as exc:
        score, verdict, feedback = _word_overlap_grade(clean_learner, clean_expected)
        damage_map = {"correct": 2.0, "partial": 1.0, "incorrect": 0.0}
        return GradingResult(
            learner_answer=clean_learner,
            expected_answer=clean_expected,
            score=score,
            verdict=verdict,
            damage_multiplier=damage_map[verdict],
            feedback=f"{feedback} (Graded via fallback due to invalid model response: {type(exc).__name__})",
            evidence_quote=evidence_quote,
            grader_version=f"fallback-invalid-model-response:{type(exc).__name__}",
        )
