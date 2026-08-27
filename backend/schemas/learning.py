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


class QuizResponse(BaseModel):
    """Response for POST /learning/quiz/generate."""

    quiz_id: str
    material_id: str
    title: str
    difficulty: str
    language: str
    generation_mode: str
    questions: list[QuizQuestion]
