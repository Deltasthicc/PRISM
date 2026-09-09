"""DSA sandbox Pydantic schemas."""
from typing import Optional

from pydantic import BaseModel, Field


class DsaProblemOut(BaseModel):
    id: str
    competency_id: str
    topic_label: str
    difficulty: str
    title: str
    prompt: str
    starter_code: str
    test_case_count: int
    sample_input: list


class DsaProblemsResponse(BaseModel):
    problems: list[DsaProblemOut]


class DsaSubmitRequest(BaseModel):
    player_id: str
    problem_id: str
    code: str = Field(..., min_length=1, max_length=20000)


class DsaTestFailure(BaseModel):
    test_index: int
    args: list
    expected_output: str
    actual_output: Optional[str] = None
    stderr: Optional[str] = None
    compile_output: Optional[str] = None


class DsaSubmitResponse(BaseModel):
    submission_id: str
    status: str
    passed_count: int
    total_count: int
    first_failure: Optional[DsaTestFailure] = None
    accuracy_history_updated: bool
