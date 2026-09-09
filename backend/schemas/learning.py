"""
Pydantic request/response shapes for /learning/* routes. Mirrors
models/learning.py the same way schemas/player.py mirrors models/player.py.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class LearnerProfileUpsert(BaseModel):
    """Body for PUT /learning/profile/{player_id}.

    Field set must exactly match the settable columns on
    models.learning.LearnerProfile -- routes/learning.py's upsert_profile()
    does `for field, value in body.model_dump().items(): setattr(profile, field, value)`.
    """

    full_name: str = Field("", max_length=200)
    designation: str = ""
    department: str = ""
    job_role: str = ""
    current_assignment: str = ""
    educational_qualifications: str = ""
    years_experience: int = Field(0, ge=0, le=60)
    previous_trainings: list[str] = Field(default_factory=list)
    career_goal: str = ""
    preferred_language: str = "English"
    experience_level: str = Field("beginner", pattern="^(beginner|intermediate|advanced|expert)$")
    target_domains: list[str] = Field(default_factory=list)

    @field_validator("previous_trainings", "target_domains")
    @classmethod
    def _bounded_list(cls, value: list[str]) -> list[str]:
        if len(value) > 40:
            raise ValueError("List has too many entries (max 40).")
        return [str(item).strip() for item in value if str(item).strip()]


class CompetencyAssessmentRequest(BaseModel):
    """Body for POST /learning/assessment/{player_id}."""

    curriculum_slug: str = Field(..., min_length=2, max_length=120)
    self_ratings: dict[str, float] = Field(default_factory=dict)

    @field_validator("self_ratings")
    @classmethod
    def _bounded_ratings(cls, value: dict[str, float]) -> dict[str, float]:
        if len(value) > 100:
            raise ValueError("Too many self-ratings in one request (max 100).")
        for score in value.values():
            if not 0 <= score <= 5:
                raise ValueError("Self-ratings must be between 0 and 5.")
        return value


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    answer_index: int
    explanation: str
    source_excerpt: str
    competency: str
    bloom_level: str
    difficulty: str = "medium"


class QuizResponse(BaseModel):
    """Response for POST /learning/quiz/generate."""

    quiz_id: str
    material_id: str
    title: str
    difficulty: str
    language: str
    generation_mode: str
    questions: list[QuizQuestion]


class QuizAnswerIn(BaseModel):
    """One answer in a POST /learning/quiz/{quiz_id}/submit body.

    `time_taken_ms` is optional client-measured wall-clock time, the same
    convention routes/competency_quiz.py's AnswerIn already uses -- see
    services/quiz_scoring.py for how a missing value is handled (neutral,
    no penalty or bonus)."""

    question_index: int = Field(..., ge=0)
    selected_index: int | None = Field(default=None, ge=0, le=3)
    time_taken_ms: int | None = Field(default=None, ge=0, le=30 * 60 * 1000)


class QuizSubmitRequest(BaseModel):
    player_id: str
    answers: list[QuizAnswerIn] = Field(..., min_length=1, max_length=50)


class QuizAnswerResult(BaseModel):
    question_index: int
    correct: bool
    correct_index: int
    selected_index: int | None
    difficulty: str
    time_factor: float
    pace: str | None = None


class DifficultyBreakdown(BaseModel):
    count: int
    correct: int
    accuracy: float
    avg_time_factor: float


class QuizSubmitResponse(BaseModel):
    """Response for POST /learning/quiz/{quiz_id}/submit.

    `weighted_score` factors both which difficulty bucket each question
    belongs to (harder questions worth more) and how long each answer took
    (see services/quiz_scoring.py) -- deliberately a standalone per-quiz
    score, not written into AccuracyHistory/the real competency vector,
    since `competency` on a generated question is free text, not a real
    curriculum competency_id.
    """

    quiz_id: str
    total_questions: int
    correct_count: int
    accuracy: float
    weighted_score: float
    scoring_note: str = (
        "Per-quiz score only -- harder questions are weighted more, and faster/"
        "slower-than-expected answers nudge the score within a bounded band. "
        "Not written into your curriculum competency vector."
    )
    by_difficulty: dict[str, DifficultyBreakdown]
    results: list[QuizAnswerResult]
