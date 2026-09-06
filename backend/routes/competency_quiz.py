"""Competency quiz routes -- serves real, source-cited questions grouped into
five topics with genuinely available content, then grades a submission.

Every question comes from services.hand_authored_questions (real, cited,
zero live-fetch dependency at request time -- see that module's own
docstring for why some entries exist for text-extractable corpus documents
too, not just the two scanned UPSC papers). This route deliberately does
NOT call services.competency_docs.quiz_from_document() live: that path
depends on a network fetch per request plus non-deterministic (Gemini) or
per-call extractive generation, neither of which is acceptable for a quiz
whose correct answers must be graded consistently against exactly what was
served to the learner a few minutes earlier.

Topics are a fixed, curated set -- not "every competency" -- because they
only exist where real, hand-verified question content actually does.
Growing this set means adding more entries to
data/hand_authored_questions.json first, the same way these were added.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services.curricula import CURRICULA
from services.hand_authored_questions import questions_for_competency

router = APIRouter(prefix="/learning/competency-quiz", tags=["Competency Quiz"])

TOPICS: dict[str, dict] = {
    "statistical_foundations": {
        "label": "Statistical Foundations & Sampling Design",
        "competency_ids": ["os_statistical_foundations", "os_sampling_design"],
        "curriculum_slug": "official-statistics",
    },
    "data_quality": {
        "label": "Data Quality & Metadata Standards",
        "competency_ids": ["os_data_quality", "os_metadata_standards"],
        "curriculum_slug": "official-statistics",
    },
    "national_accounts": {
        "label": "National Accounts & Price Statistics",
        "competency_ids": ["os_national_accounts", "os_price_statistics"],
        "curriculum_slug": "official-statistics",
    },
    "digital_governance": {
        "label": "Digital Governance & Data Privacy",
        "competency_ids": ["dl_data_privacy", "dl_digital_signatures"],
        "curriculum_slug": "digital-literacy",
    },
    "ai_technology": {
        "label": "AI & Responsible Technology",
        "competency_ids": ["os_ml", "dl_ai_literacy", "dl_responsible_ai"],
        "curriculum_slug": "digital-literacy",
    },
}

_COMPETENCY_LABELS = {
    competency["id"]: competency["label"]
    for curriculum in CURRICULA.values()
    for competency in curriculum["competencies"]
}


def _topic_questions(topic_id: str) -> list[dict]:
    topic = TOPICS.get(topic_id)
    if not topic:
        return []
    items: list[dict] = []
    for competency_id in topic["competency_ids"]:
        items.extend(questions_for_competency(competency_id))
    return items


def _all_items_by_id() -> dict[str, dict]:
    items: dict[str, dict] = {}
    for topic in TOPICS.values():
        for competency_id in topic["competency_ids"]:
            for item in questions_for_competency(competency_id):
                items[item["item_id"]] = item
    return items


class TopicSummary(BaseModel):
    topic_id: str
    label: str
    competency_ids: list[str]
    curriculum_slug: str
    question_count: int


@router.get("/topics", response_model=list[TopicSummary])
async def list_topics() -> list[TopicSummary]:
    return [
        TopicSummary(
            topic_id=topic_id,
            label=topic["label"],
            competency_ids=topic["competency_ids"],
            curriculum_slug=topic["curriculum_slug"],
            question_count=len(_topic_questions(topic_id)),
        )
        for topic_id, topic in TOPICS.items()
    ]


class QuizQuestionOut(BaseModel):
    """Never includes answer_index/explanation/source_excerpt -- those only
    reach the client after /submit, once they can no longer change an answer
    based on seeing them."""

    item_id: str
    question: str
    options: list[str]
    competency_id: str
    competency_label: str
    difficulty: str
    doc_id: str
    locator: str


class QuizQuestionsResponse(BaseModel):
    topic_id: str
    label: str
    questions: list[QuizQuestionOut]


@router.get("/questions", response_model=QuizQuestionsResponse)
async def get_quiz_questions(topic_id: str, count: int = 5) -> QuizQuestionsResponse:
    topic = TOPICS.get(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail=f"Unknown topic: {topic_id!r}")
    pool = _topic_questions(topic_id)
    if not pool:
        raise HTTPException(status_code=503, detail=f"No questions available yet for topic {topic_id!r}")

    selected = pool[: max(1, count)]
    questions = [
        QuizQuestionOut(
            item_id=item["item_id"],
            question=item["question"],
            options=item["options"],
            competency_id=item["competency_id"],
            competency_label=_COMPETENCY_LABELS.get(item["competency_id"], item["competency_id"]),
            difficulty=item["difficulty"],
            doc_id=item["doc_id"],
            locator=item["locator"],
        )
        for item in selected
    ]
    return QuizQuestionsResponse(topic_id=topic_id, label=topic["label"], questions=questions)


class AnswerIn(BaseModel):
    item_id: str
    selected_index: int = Field(ge=0, le=3)


class SubmitRequest(BaseModel):
    topic_id: str
    answers: list[AnswerIn] = Field(min_length=1)


class GradedAnswer(BaseModel):
    item_id: str
    competency_id: str
    correct: bool
    selected_index: int
    correct_index: int
    explanation: str
    source_excerpt: str
    doc_id: str
    locator: str


class CompetencyScore(BaseModel):
    competency_id: str
    competency_label: str
    correct: int
    total: int
    accuracy: float
    level: float  # 0-5 scale, matching the self_ratings/measured_scores convention elsewhere


class SubmitResponse(BaseModel):
    topic_id: str
    label: str
    total: int
    correct: int
    score_percentage: int
    graded_answers: list[GradedAnswer]
    competency_scores: list[CompetencyScore]
    # Ready to hand straight to POST /learning/assessment/{player_id} as
    # self_ratings (see routes/learning_competency.py). Framed honestly as an
    # approximation, not a rename: this measures demonstrated quiz
    # performance, which is a different thing from a learner's own
    # self-report, but self_ratings is the assessment engine's only input
    # channel for a fresh signal like this today -- there is no separate
    # "quiz-demonstrated" channel it blends in yet.
    self_ratings: dict[str, float]


@router.post("/submit", response_model=SubmitResponse)
async def submit_quiz(body: SubmitRequest) -> SubmitResponse:
    topic = TOPICS.get(body.topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail=f"Unknown topic: {body.topic_id!r}")

    lookup = _all_items_by_id()
    graded: list[GradedAnswer] = []
    by_competency: dict[str, list[bool]] = {}

    for answer in body.answers:
        item = lookup.get(answer.item_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"Unknown item_id: {answer.item_id!r}")
        is_correct = answer.selected_index == item["answer_index"]
        graded.append(
            GradedAnswer(
                item_id=item["item_id"],
                competency_id=item["competency_id"],
                correct=is_correct,
                selected_index=answer.selected_index,
                correct_index=item["answer_index"],
                explanation=item["explanation"],
                source_excerpt=item["source_excerpt"],
                doc_id=item["doc_id"],
                locator=item["locator"],
            )
        )
        by_competency.setdefault(item["competency_id"], []).append(is_correct)

    total = len(graded)
    correct = sum(1 for g in graded if g.correct)

    competency_scores: list[CompetencyScore] = []
    self_ratings: dict[str, float] = {}
    for competency_id, results in by_competency.items():
        c = sum(results)
        t = len(results)
        accuracy = c / t if t else 0.0
        level = round(accuracy * 5, 1)
        competency_scores.append(
            CompetencyScore(
                competency_id=competency_id,
                competency_label=_COMPETENCY_LABELS.get(competency_id, competency_id),
                correct=c,
                total=t,
                accuracy=round(accuracy, 2),
                level=level,
            )
        )
        self_ratings[competency_id] = level

    return SubmitResponse(
        topic_id=body.topic_id,
        label=topic["label"],
        total=total,
        correct=correct,
        score_percentage=round((correct / total) * 100) if total else 0,
        graded_answers=graded,
        competency_scores=competency_scores,
        self_ratings=self_ratings,
    )
