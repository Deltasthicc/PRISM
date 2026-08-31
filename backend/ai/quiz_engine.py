"""Lane 4 (Content AI, RAG & Evaluation) — Quiz Generation & Review Lifecycle.

Manages grounded MCQ generation, automated validation checks, and the
item lifecycle state machine:
draft -> auto_checked -> expert_review -> approved -> published -> retired
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import re
from datetime import datetime, timezone
from typing import Any

import google.generativeai as genai

from ai.provenance import (
    Chunk,
    ItemReviewState,
    QuizQuestionItem,
    SourceLocator,
    SourceVersion,
    generate_uuid,
)
from ai.security import sanitize_untrusted_text

VALID_BLOOM_LEVELS = {"remember", "understand", "apply", "analyse", "evaluate"}
WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z-]{3,}\b")


def validate_question_item(item: dict[str, Any], source_text: str) -> tuple[bool, list[str]]:
    """Strict deterministic validation of a generated MCQ item.

    Returns:
        (is_valid, validation_errors)
    """
    errors: list[str] = []

    # 1. Question text check
    question = str(item.get("question", "")).strip()
    if len(question) < 10:
        errors.append("Question text is missing or too short.")

    # 2. Options check
    options = item.get("options")
    if not isinstance(options, list) or len(options) != 4:
        errors.append("Must provide exactly four options.")
    else:
        cleaned_options = [str(opt).strip() for opt in options]
        if any(not opt for opt in cleaned_options):
            errors.append("Option text cannot be empty.")
        if len({opt.lower() for opt in cleaned_options}) != 4:
            errors.append("All four options must be distinctly unique.")

    # 3. Answer index check
    try:
        ans_idx = int(item.get("answer_index", -1))
        if not 0 <= ans_idx <= 3:
            errors.append("answer_index must be an integer between 0 and 3.")
    except (TypeError, ValueError):
        errors.append("answer_index is not a valid integer.")

    # 4. Source grounding verification
    excerpt = " ".join(str(item.get("source_excerpt", "")).split())
    if len(excerpt) < 15:
        errors.append("source_excerpt is missing or too short.")
    else:
        compact_source = " ".join(source_text.split()).lower()
        if excerpt.lower() not in compact_source:
            errors.append("source_excerpt could not be verified in the source text.")

    # 5. Bloom level validation
    bloom = str(item.get("bloom_level", "")).lower()
    if bloom not in VALID_BLOOM_LEVELS:
        errors.append(f"Invalid Bloom taxonomy level: '{bloom}'.")

    return len(errors) == 0, errors


def generate_extractive_fallback_items(
    source_ver: SourceVersion,
    chunks: list[Chunk],
    count: int = 5,
) -> list[QuizQuestionItem]:
    """Deterministic, extractive fallback MCQ generation preserving chunk locators."""
    if not chunks:
        raise ValueError("Cannot generate quiz items without source chunks.")

    items: list[QuizQuestionItem] = []
    used_answers: set[str] = set()

    # Collect distinct terms across all chunks
    all_terms: list[str] = []
    seen_terms: set[str] = set()
    for chunk in chunks:
        for word in WORD_RE.findall(chunk.text):
            lowered = word.lower()
            if lowered not in seen_terms and len(word) >= 4:
                all_terms.append(word)
                seen_terms.add(lowered)

    if len(all_terms) < 4:
        raise ValueError("Source material does not contain enough distinct terms for MCQ distractors.")

    for chunk in chunks:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", chunk.text) if len(s.strip()) >= 40]
        for sentence in sentences:
            candidates = [
                word for word in WORD_RE.findall(sentence)
                if word.lower() not in used_answers and len(word) >= 4
            ]
            if not candidates:
                continue

            answer = max(candidates, key=len)
            distractors = [t for t in all_terms if t.lower() != answer.lower()]
            if len(distractors) < 3:
                continue

            local_rng = random.Random(sum(ord(c) for c in sentence))
            options = [answer, *local_rng.sample(distractors, 3)]
            local_rng.shuffle(options)

            blanked = re.sub(rf"\b{re.escape(answer)}\b", "_____", sentence, count=1, flags=re.IGNORECASE)
            question_text = f"Which term best completes this statement from the source? \"{blanked}\""

            item = QuizQuestionItem(
                question_id=generate_uuid(),
                source_id=source_ver.source_id,
                source_version=source_ver.version,
                chunk_ids=[chunk.chunk_id],
                source_locators=chunk.locators,
                question=question_text,
                options=options,
                answer_index=options.index(answer),
                explanation=f"According to the source ({'; '.join(l.label for l in chunk.locators)}): \"{sentence}\"",
                source_excerpt=sentence,
                competency="Source comprehension",
                bloom_level="understand",
                review_state=ItemReviewState.AUTO_CHECKED,
                validation_notes=["Generated via verified extractive fallback."],
            )
            items.append(item)
            used_answers.add(answer.lower())

            if len(items) == count:
                return items

    if len(items) < count and items:
        return items

    raise ValueError("Not enough varied content in source material for the requested quiz count.")


class QuizReviewWorkflow:
    """Manages lifecycle state transitions for assessment items."""

    @staticmethod
    def transition_state(
        item: QuizQuestionItem,
        target_state: ItemReviewState,
        reviewer_id: str | None = None,
        notes: str | None = None,
    ) -> QuizQuestionItem:
        valid_transitions = {
            ItemReviewState.DRAFT: {ItemReviewState.AUTO_CHECKED, ItemReviewState.RETIRED},
            ItemReviewState.AUTO_CHECKED: {ItemReviewState.EXPERT_REVIEW, ItemReviewState.APPROVED, ItemReviewState.RETIRED},
            ItemReviewState.EXPERT_REVIEW: {ItemReviewState.APPROVED, ItemReviewState.RETIRED},
            ItemReviewState.APPROVED: {ItemReviewState.PILOT, ItemReviewState.PUBLISHED, ItemReviewState.RETIRED},
            ItemReviewState.PILOT: {ItemReviewState.PUBLISHED, ItemReviewState.RETIRED},
            ItemReviewState.PUBLISHED: {ItemReviewState.RETIRED},
            ItemReviewState.RETIRED: set(),
        }

        if target_state not in valid_transitions.get(item.review_state, set()):
            raise ValueError(
                f"Cannot transition item from state '{item.review_state.value}' to '{target_state.value}'."
            )

        item.review_state = target_state
        if reviewer_id:
            item.reviewer_id = reviewer_id
            item.reviewed_at = datetime.now(timezone.utc).isoformat()
        if notes:
            item.validation_notes.append(notes)
        return item
