"""
Accuracy history Pydantic schemas.
"""
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class AccuracyHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    topic: str
    attempts: int
    correct: int
    recent_accuracy: float
    last_5_results: List[bool] = Field(default_factory=list)
