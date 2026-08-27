"""
Question Pydantic schemas.
"""
from typing import Optional

from pydantic import BaseModel, ConfigDict


class QuestionGenerateRequest(BaseModel):
    player_id: str
    topic: str
    difficulty: str = "medium"  # easy | medium | hard
    domain: str = "Data Structures & Algorithms"


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    question_id: str
    question: str
    hint: Optional[str] = None
    topic: str
    difficulty: str
    # NOTE: expected_answer is intentionally NOT sent to the client


class QuestionFullResponse(BaseModel):
    """Internal use — includes expected_answer for AI judge."""

    model_config = ConfigDict(from_attributes=True)

    question_id: str
    question: str
    expected_answer: str
    hint: Optional[str] = None
    topic: str
    difficulty: str
