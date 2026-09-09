"""Competency quiz routes -- serves real, source-cited questions grouped into
five topics with genuinely available content, then grades a submission.

Every question comes from services.hand_authored_questions (source-attributed,
zero live-fetch dependency at request time -- see that module's own
docstring for why some entries exist for text-extractable corpus documents
too, not just the two scanned UPSC papers). This route deliberately does
NOT call services.competency_docs.quiz_from_document() live: that path
depends on a network fetch per request plus non-deterministic (Gemini) or
per-call extractive generation, neither of which is acceptable for a quiz
whose correct answers must be graded consistently against exactly what was
served to the learner a few minutes earlier.

Topics are a fixed, curated set -- not "every competency" -- because they
only exist where draft question content actually does. Items remain visibly
DRAFT/PROVISIONAL until an authorized subject-matter reviewer approves them;
a corpus document id and locator are provenance, not approval.
Growing this set means adding more entries to
data/hand_authored_questions.json first, the same way these were added.
"""
from __future__ import annotations

import json
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db.database import get_db
from models.governance import EvidenceRecord
from routes.learning_common import player_or_404
from security.audit import record_audit_event
from services.curricula import CURRICULA
from services.hand_authored_questions import normalize_fill_in_blank_answer, questions_for_competency

router = APIRouter(prefix="/learning/competency-quiz", tags=["Competency Quiz"])

TOPICS: dict[str, dict] = {
    "statistical_foundations": {
        "label": "Statistical Foundations & Sampling Design",
        "competency_ids": ["os_statistical_foundations", "os_sampling_design"],
        "curriculum_slug": "official-statistics",
    },
    "data_quality": {
        "label": "Quality Control & Data Quality",
        "competency_ids": ["os_data_quality"],
        "curriculum_slug": "official-statistics",
    },
    "price_statistics": {
        "label": "Price Statistics & CPI",
        "competency_ids": ["os_price_statistics"],
        "curriculum_slug": "official-statistics",
    },
    "data_privacy": {
        "label": "Digital Governance: Data Privacy",
        "competency_ids": ["dl_data_privacy"],
        "curriculum_slug": "digital-literacy",
    },
    "ai_policy": {
        "label": "AI Policy & Literacy",
        "competency_ids": ["os_ml", "dl_ai_literacy"],
        "curriculum_slug": "digital-literacy",
    },
    # DSA -- GATE-sourced (see data/hand_authored_questions.json); no topic
    # for binary_search, which has zero verified questions so far.
    "linear_structures": {
        "label": "Arrays, Linked Lists & Stacks/Queues",
        "competency_ids": ["arrays", "linked_lists", "stacks_queues"],
        "curriculum_slug": "dsa-fundamentals",
    },
    "recursion_and_sorting": {
        "label": "Recursion & Sorting Algorithms",
        "competency_ids": ["recursion", "sorting_algorithms"],
        "curriculum_slug": "dsa-fundamentals",
    },
    "trees_and_heaps": {
        "label": "Trees, Binary Search Trees & Heaps",
        "competency_ids": ["trees", "binary_search_tree", "heaps"],
        "curriculum_slug": "dsa-fundamentals",
    },
    "graphs_and_dp": {
        "label": "Graphs & Dynamic Programming",
        "competency_ids": ["graphs", "dynamic_programming"],
        "curriculum_slug": "dsa-fundamentals",
    },
    # Official Statistics -- expanded coverage
    "data_collection_and_surveys": {
        "label": "Data Collection & Official Statistics",
        "competency_ids": ["os_data_collection", "os_official_statistics"],
        "curriculum_slug": "official-statistics",
    },
    "data_technology": {
        "label": "Visualization, GIS, Big Data & Statistical Programming",
        "competency_ids": ["os_visualization", "os_gis", "os_big_data", "os_statistical_programming", "os_data_management_sql"],
        "curriculum_slug": "official-statistics",
    },
    "national_accounts_and_sectoral": {
        "label": "National Accounts, Labour, Industrial & Agricultural Statistics",
        "competency_ids": [
            "os_national_accounts", "os_labour_statistics", "os_industrial_statistics",
            "os_agricultural_statistics",
        ],
        "curriculum_slug": "official-statistics",
    },
    "open_data_and_standards": {
        "label": "SDG Indicators, Metadata & Open Data Standards",
        "competency_ids": ["os_sdg_indicators", "os_metadata_standards", "os_apis_interoperability", "os_open_data"],
        "curriculum_slug": "official-statistics",
    },
    # Public Policy -- all new coverage
    "governance_and_policy": {
        "label": "Governance Foundations & Policy Design",
        "competency_ids": ["pa_governance_foundations", "pa_policy_design"],
        "curriculum_slug": "public-policy",
    },
    "public_finance": {
        "label": "Public Finance",
        "competency_ids": ["pa_public_finance"],
        "curriculum_slug": "public-policy",
    },
    "program_delivery": {
        "label": "Program Management, Monitoring & Impact Evaluation",
        "competency_ids": ["pa_program_management", "pa_monitoring_evaluation", "pa_impact_evaluation"],
        "curriculum_slug": "public-policy",
    },
    "ethics_and_conduct": {
        "label": "Ethics & Decision-Making",
        "competency_ids": ["pa_ethics", "pa_decision_making"],
        "curriculum_slug": "public-policy",
    },
    "leadership_and_change": {
        "label": "Leadership, Change Management & Communication",
        "competency_ids": ["pa_leadership", "pa_change_management", "pa_communication", "pa_data_storytelling"],
        "curriculum_slug": "public-policy",
    },
    # Digital Literacy -- expanded coverage
    "cyber_hygiene_and_signatures": {
        "label": "Cyber Hygiene & Digital Signatures",
        "competency_ids": ["dl_cyber_hygiene", "dl_digital_signatures"],
        "curriculum_slug": "digital-literacy",
    },
    "responsible_ai_and_dpi": {
        "label": "Responsible AI & Digital Public Infrastructure",
        "competency_ids": ["dl_responsible_ai", "dl_digital_public_infrastructure"],
        "curriculum_slug": "digital-literacy",
    },
    "digital_office_skills": {
        "label": "Digital Foundations, Collaboration & Spreadsheets",
        "competency_ids": ["dl_digital_foundations", "dl_collaboration", "dl_spreadsheets", "dl_data_literacy"],
        "curriculum_slug": "digital-literacy",
    },
    "government_cloud": {
        "label": "Government Cloud (GI Cloud / MeghRaj)",
        "competency_ids": ["dl_government_cloud"],
        "curriculum_slug": "digital-literacy",
    },
}

_DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "hard": 2}

# Reference time-to-answer per difficulty, in seconds -- a rough, openly
# approximate baseline (not derived from any measured population of test
# takers), used only to turn a client-reported elapsed time into a small,
# bounded nudge on top of accuracy. This is intentionally a secondary signal:
# accuracy alone still determines whether an answer counts as correct: timing
# only adjusts *how confidently* a correct-answer streak is reported, within
# a +-15% band, so a fast wrong answer is never scored better than a slow
# right one, and a slow correct answer never drops out of its accuracy tier.
_EXPECTED_SECONDS = {"easy": 20, "medium": 40, "hard": 75}
_TIME_FACTOR_MIN = 0.85
_TIME_FACTOR_MAX = 1.10


def _time_factor(difficulty: str, time_taken_ms: int | None) -> float:
    """1.0 (neutral) if no timing was reported; otherwise a bounded ratio of
    expected-to-actual time, so answering faster than the reference nudges
    the factor above 1.0 and answering slower nudges it below."""
    if not time_taken_ms or time_taken_ms <= 0:
        return 1.0
    expected_ms = _EXPECTED_SECONDS[difficulty] * 1000
    ratio = expected_ms / time_taken_ms
    return max(_TIME_FACTOR_MIN, min(_TIME_FACTOR_MAX, ratio))


def _pace_label(time_factor: float) -> str:
    if time_factor >= 1.03:
        return "faster"
    if time_factor <= 0.92:
        return "slower"
    return "typical"
MAX_QUESTIONS_PER_TOPIC = 10
ATTEMPT_TTL_SECONDS = 30 * 60
MAX_ACTIVE_ATTEMPTS = 1_000

# Demo-scoped, process-local attempt registry. This makes grading consume the
# exact items the API issued and prevents answer-key replay in the running
# demo. It is intentionally not described as a distributed production quiz
# session store: a restart expires attempts, and a multi-worker deployment
# would replace this with shared persistence.
_active_attempts: dict[str, dict] = {}

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


def _select_topic_questions(topic_id: str, count: int) -> list[dict]:
    """Select a stable, difficulty-progressive and competency-balanced set.

    Difficulty labels are curated prototype metadata, not a psychometrically
    calibrated item-response scale. Within that honest boundary, learners see
    easier items before harder ones and, where a topic spans competencies, one
    competency cannot consume the whole requested set merely because its
    items happen to appear first in the JSON file.
    """

    topic = TOPICS[topic_id]
    by_competency = {
        competency_id: sorted(
            questions_for_competency(competency_id),
            key=lambda item: (_DIFFICULTY_ORDER[item["difficulty"]], item["item_id"]),
        )
        for competency_id in topic["competency_ids"]
    }
    selected: list[dict] = []
    for difficulty in ("easy", "medium", "hard"):
        queues = {
            competency_id: [
                item
                for item in by_competency[competency_id]
                if item["difficulty"] == difficulty
            ]
            for competency_id in topic["competency_ids"]
        }
        while len(selected) < count and any(queues.values()):
            for competency_id in topic["competency_ids"]:
                if queues[competency_id] and len(selected) < count:
                    selected.append(queues[competency_id].pop(0))
    return selected


def _issue_attempt(topic_id: str, selected: list[dict]) -> str:
    now = time.monotonic()
    expired = [
        attempt_id
        for attempt_id, attempt in _active_attempts.items()
        if now - attempt["issued_at"] > ATTEMPT_TTL_SECONDS
    ]
    for attempt_id in expired:
        _active_attempts.pop(attempt_id, None)
    while len(_active_attempts) >= MAX_ACTIVE_ATTEMPTS:
        oldest = min(_active_attempts, key=lambda key: _active_attempts[key]["issued_at"])
        _active_attempts.pop(oldest, None)

    attempt_id = str(uuid.uuid4())
    _active_attempts[attempt_id] = {
        "topic_id": topic_id,
        "item_ids": tuple(item["item_id"] for item in selected),
        "issued_at": now,
    }
    return attempt_id


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
    """Never includes answer_index/accepted_answers/explanation/
    source_excerpt -- those only reach the client after /submit, once they
    can no longer change an answer based on seeing them.

    `options` is populated only for question_type="mcq"; a "fill_in_blank"
    item's `question` text itself contains the "_____" blank marker and the
    client renders a text input instead of an option list."""

    item_id: str
    question: str
    question_type: str = "mcq"
    options: list[str] | None = None
    competency_id: str
    competency_label: str
    difficulty: str
    doc_id: str
    locator: str
    item_status: str = "DRAFT"


class QuizQuestionsResponse(BaseModel):
    attempt_id: str
    topic_id: str
    label: str
    assessment_status: str = "PROVISIONAL"
    difficulty_note: str = (
        "Curated easy/medium/hard ordering; not a psychometrically calibrated scale."
    )
    questions: list[QuizQuestionOut]


@router.get("/questions", response_model=QuizQuestionsResponse)
async def get_quiz_questions(
    topic_id: str,
    count: int = Query(5, ge=1, le=MAX_QUESTIONS_PER_TOPIC),
) -> QuizQuestionsResponse:
    topic = TOPICS.get(topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail=f"Unknown topic: {topic_id!r}")
    pool = _topic_questions(topic_id)
    if not pool:
        raise HTTPException(status_code=503, detail=f"No questions available yet for topic {topic_id!r}")

    selected = _select_topic_questions(topic_id, count)
    questions = [
        QuizQuestionOut(
            item_id=item["item_id"],
            question=item["question"],
            question_type=item.get("question_type", "mcq"),
            options=item.get("options"),
            competency_id=item["competency_id"],
            competency_label=_COMPETENCY_LABELS.get(item["competency_id"], item["competency_id"]),
            difficulty=item["difficulty"],
            doc_id=item["doc_id"],
            locator=item["locator"],
        )
        for item in selected
    ]
    return QuizQuestionsResponse(
        attempt_id=_issue_attempt(topic_id, selected),
        topic_id=topic_id,
        label=topic["label"],
        questions=questions,
    )


class AnswerIn(BaseModel):
    """Exactly one of selected_index (mcq) / answer_text (fill_in_blank)
    must be set, matching the item's question_type -- checked in
    submit_quiz() against the item actually issued, not trusted from the
    client alone."""

    item_id: str
    selected_index: int | None = Field(default=None, ge=0, le=3)
    answer_text: str | None = Field(default=None, max_length=500)
    # Client-measured wall-clock time between this question being shown and
    # answered, in milliseconds. Optional (older/misbehaving clients simply
    # omit it) -- see _time_factor() for how a missing value is handled.
    time_taken_ms: int | None = Field(default=None, ge=0, le=30 * 60 * 1000)


class SubmitRequest(BaseModel):
    attempt_id: str = Field(min_length=1, max_length=120)
    topic_id: str
    answers: list[AnswerIn] = Field(min_length=1, max_length=MAX_QUESTIONS_PER_TOPIC)
    player_id: str | None = Field(default=None, min_length=1, max_length=120)


class GradedAnswer(BaseModel):
    item_id: str
    competency_id: str
    question_type: str = "mcq"
    correct: bool
    selected_index: int | None = None
    correct_index: int | None = None
    submitted_text: str | None = None
    correct_answer_display: str | None = None
    explanation: str
    source_excerpt: str
    doc_id: str
    locator: str
    time_taken_ms: int | None = None
    pace: str | None = None  # "faster" | "typical" | "slower" | None (no timing data)


class CompetencyScore(BaseModel):
    competency_id: str
    competency_label: str
    correct: int
    total: int
    accuracy: float
    provisional_level: float
    evidence_count: int
    confidence: str
    rank: int
    avg_time_factor: float = 1.0


class SubmitResponse(BaseModel):
    topic_id: str
    label: str
    total: int
    correct: int
    score_percentage: int
    graded_answers: list[GradedAnswer]
    competency_scores: list[CompetencyScore]
    assessment_status: str = "PROVISIONAL"
    ranking_basis: str = "Accuracy descending, then evidence count; not psychometrically calibrated."
    diagnostic_scores: dict[str, float]
    persisted_as_diagnostic_evidence: bool
    evidence_record_ids: list[str]


@router.post("/submit", response_model=SubmitResponse)
async def submit_quiz(
    body: SubmitRequest,
    db: Session = Depends(get_db),
) -> SubmitResponse:
    topic = TOPICS.get(body.topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail=f"Unknown topic: {body.topic_id!r}")

    attempt = _active_attempts.get(body.attempt_id)
    if attempt is None or time.monotonic() - attempt["issued_at"] > ATTEMPT_TTL_SECONDS:
        _active_attempts.pop(body.attempt_id, None)
        raise HTTPException(status_code=409, detail="Quiz attempt expired or already submitted")
    if attempt["topic_id"] != body.topic_id:
        raise HTTPException(status_code=422, detail="Quiz attempt does not match the submitted topic")

    lookup = {item["item_id"]: item for item in _topic_questions(body.topic_id)}
    submitted_ids = [answer.item_id for answer in body.answers]
    if len(submitted_ids) != len(set(submitted_ids)):
        raise HTTPException(status_code=422, detail="Each quiz item may be answered only once")
    if set(submitted_ids) != set(attempt["item_ids"]):
        raise HTTPException(status_code=422, detail="Submit exactly the questions issued for this attempt")
    # No await occurs between lookup/validation and pop, so one process can
    # consume an attempt only once even under concurrent async requests.
    _active_attempts.pop(body.attempt_id, None)
    graded: list[GradedAnswer] = []
    by_competency: dict[str, list[bool]] = {}
    time_factors_by_competency: dict[str, list[float]] = {}

    for answer in body.answers:
        item = lookup.get(answer.item_id)
        if item is None:
            raise HTTPException(
                status_code=422,
                detail=f"Item {answer.item_id!r} does not belong to topic {body.topic_id!r}",
            )
        question_type = item.get("question_type", "mcq")
        time_factor = _time_factor(item["difficulty"], answer.time_taken_ms)
        pace = _pace_label(time_factor) if answer.time_taken_ms else None
        if question_type == "mcq":
            if answer.selected_index is None:
                raise HTTPException(status_code=422, detail=f"Item {item['item_id']!r} requires selected_index")
            is_correct = answer.selected_index == item["answer_index"]
            graded.append(
                GradedAnswer(
                    item_id=item["item_id"],
                    competency_id=item["competency_id"],
                    question_type=question_type,
                    correct=is_correct,
                    selected_index=answer.selected_index,
                    correct_index=item["answer_index"],
                    explanation=item["explanation"],
                    source_excerpt=item["source_excerpt"],
                    doc_id=item["doc_id"],
                    locator=item["locator"],
                    time_taken_ms=answer.time_taken_ms,
                    pace=pace,
                )
            )
        else:
            if not answer.answer_text or not answer.answer_text.strip():
                raise HTTPException(status_code=422, detail=f"Item {item['item_id']!r} requires answer_text")
            submitted_normalized = normalize_fill_in_blank_answer(answer.answer_text)
            accepted_normalized = {normalize_fill_in_blank_answer(a) for a in item["accepted_answers"]}
            is_correct = submitted_normalized in accepted_normalized
            graded.append(
                GradedAnswer(
                    item_id=item["item_id"],
                    competency_id=item["competency_id"],
                    question_type=question_type,
                    correct=is_correct,
                    submitted_text=answer.answer_text,
                    correct_answer_display=item["accepted_answers"][0],
                    explanation=item["explanation"],
                    source_excerpt=item["source_excerpt"],
                    doc_id=item["doc_id"],
                    locator=item["locator"],
                    time_taken_ms=answer.time_taken_ms,
                    pace=pace,
                )
            )
        by_competency.setdefault(item["competency_id"], []).append(is_correct)
        # Only correct answers' pace feeds the confidence nudge below -- a
        # fast wrong answer must never look better than a slow right one.
        if is_correct:
            time_factors_by_competency.setdefault(item["competency_id"], []).append(time_factor)

    total = len(graded)
    correct = sum(1 for g in graded if g.correct)

    score_rows: list[dict] = []
    diagnostic_scores: dict[str, float] = {}
    for competency_id, results in by_competency.items():
        c = sum(results)
        t = len(results)
        accuracy = c / t if t else 0.0
        competency_time_factors = time_factors_by_competency.get(competency_id, [])
        avg_time_factor = sum(competency_time_factors) / len(competency_time_factors) if competency_time_factors else 1.0
        level = round(min(5.0, accuracy * 5 * avg_time_factor), 1)
        confidence = "high" if t >= 3 and avg_time_factor >= 1.0 else "moderate" if t >= 3 else "low"
        score_rows.append(
            {
                "competency_id": competency_id,
                "competency_label": _COMPETENCY_LABELS.get(competency_id, competency_id),
                "correct": c,
                "total": t,
                "accuracy": round(accuracy, 2),
                "provisional_level": level,
                "evidence_count": t,
                "confidence": confidence,
                "avg_time_factor": round(avg_time_factor, 3),
            }
        )
        diagnostic_scores[competency_id] = level

    score_rows.sort(key=lambda score: (-score["accuracy"], -score["evidence_count"], score["competency_id"]))
    competency_scores = [
        CompetencyScore(**score, rank=index)
        for index, score in enumerate(score_rows, start=1)
    ]

    evidence_record_ids: list[str] = []
    if body.player_id:
        player_or_404(db, body.player_id)
        for score in competency_scores:
            record = EvidenceRecord(
                player_id=body.player_id,
                competency_id=score.competency_id,
                # Was "diagnostic" (UNSCORED_EVIDENCE_TYPES in learning_engine.py)
                # until this quiz was made the sole source of competency
                # evidence: no scoring source ever wrote "observed_practice"
                # (the only other SCORING_EVIDENCE_TYPES entry, besides
                # "self_report", which this app no longer collects from any
                # UI), so a diagnostic-tagged record here never moved a
                # learner's observed_level at all. Real answered questions
                # are exactly the "observed practice" this evidence type is
                # for -- see docs/contracts/data-authorization.md 4.1's note
                # that weighting these types is Lane 3's versioned policy.
                evidence_type="observed_practice",
                value=round(score.provisional_level),
                detail=json.dumps(
                    {
                        "instrument": "curated-demo-quiz-v1",
                        "topic_id": body.topic_id,
                        "correct": score.correct,
                        "total": score.total,
                        "item_ids": [
                            answer.item_id
                            for answer in graded
                            if answer.competency_id == score.competency_id
                        ],
                        "avg_time_factor": score.avg_time_factor,
                        "provisional": True,
                    },
                    separators=(",", ":"),
                    sort_keys=True,
                ),
            )
            db.add(record)
            db.flush()
            evidence_record_ids.append(record.evidence_id)
        record_audit_event(
            db,
            actor=body.player_id,
            action="competency_quiz.submit",
            entity_type="player",
            entity_id=body.player_id,
            details={
                "topic_id": body.topic_id,
                "question_count": total,
                "evidence_record_ids": evidence_record_ids,
                "instrument": "curated-demo-quiz-v1",
            },
            commit=False,
        )
        db.commit()

    return SubmitResponse(
        topic_id=body.topic_id,
        label=topic["label"],
        total=total,
        correct=correct,
        score_percentage=round((correct / total) * 100) if total else 0,
        graded_answers=graded,
        competency_scores=competency_scores,
        diagnostic_scores=diagnostic_scores,
        persisted_as_diagnostic_evidence=bool(body.player_id),
        evidence_record_ids=evidence_record_ids,
    )
