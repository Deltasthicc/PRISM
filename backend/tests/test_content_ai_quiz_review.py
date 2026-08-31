"""Lane 4 Tests — Quiz Validation, Review Lifecycle State Machine & Grading."""
import pytest

from ai.grading import grade_student_answer
from ai.ingestion import ingest_document
from ai.provenance import (
    ItemReviewState,
    QuizQuestionItem,
    SourceLocator,
)
from ai.quiz_engine import (
    QuizReviewWorkflow,
    generate_extractive_fallback_items,
    validate_question_item,
)


@pytest.fixture
def sample_curriculum_text():
    return (
        "# Statistical Methods: Regression and Hypothesis Testing\n"
        "Ordinary Least Squares (OLS) regression minimizes the sum of squared residuals.\n"
        "Heteroscedasticity occurs when the variance of the error terms is not constant across observations.\n"
        "The Gauss-Markov theorem proves that OLS estimators are Best Linear Unbiased Estimators (BLUE) under standard assumptions.\n"
        "Multicollinearity increases standard errors of regression coefficients without biasing point estimates.\n"
    )


def test_question_item_validation_catches_invalid_distractors(sample_curriculum_text):
    # Valid item
    valid_item = {
        "question": "Which theorem establishes that OLS estimators are BLUE?",
        "options": ["Gauss-Markov theorem", "Central Limit theorem", "Bayes theorem", "Chebyshev inequality"],
        "answer_index": 0,
        "source_excerpt": "The Gauss-Markov theorem proves that OLS estimators are Best Linear Unbiased Estimators",
        "bloom_level": "understand",
    }
    is_valid, errors = validate_question_item(valid_item, sample_curriculum_text)
    assert is_valid is True
    assert len(errors) == 0

    # Invalid item with duplicate options
    invalid_item = {
        "question": "Which theorem establishes that OLS estimators are BLUE?",
        "options": ["Gauss-Markov theorem", "Gauss-Markov theorem", "Bayes theorem", "Chebyshev inequality"],
        "answer_index": 0,
        "source_excerpt": "The Gauss-Markov theorem proves that OLS estimators are Best Linear Unbiased Estimators",
        "bloom_level": "understand",
    }
    is_valid, errors = validate_question_item(invalid_item, sample_curriculum_text)
    assert is_valid is False
    assert any("distinctly unique" in e for e in errors)


def test_extractive_fallback_item_generation_with_locators(sample_curriculum_text):
    source_ver, chunks, _ = ingest_document(
        filename="regression.md",
        content=sample_curriculum_text.encode("utf-8"),
        source_id="src-reg-001",
    )
    items = generate_extractive_fallback_items(source_ver, chunks, count=2)
    assert len(items) == 2
    for item in items:
        assert item.source_id == "src-reg-001"
        assert item.review_state == ItemReviewState.AUTO_CHECKED
        assert len(item.options) == 4
        assert 0 <= item.answer_index <= 3
        assert len(item.source_locators) >= 1


def test_review_lifecycle_state_transitions():
    item = QuizQuestionItem(
        question_id="q-test-1",
        source_id="src-1",
        source_version=1,
        chunk_ids=["chunk-1"],
        source_locators=[SourceLocator(locator_type="section", index=1, label="Section 1")],
        question="What does OLS minimize?",
        options=["Sum of squared residuals", "Variance", "Mean", "Median"],
        answer_index=0,
        explanation="OLS minimizes the sum of squared residuals.",
        source_excerpt="Ordinary Least Squares (OLS) regression minimizes the sum of squared residuals.",
        review_state=ItemReviewState.DRAFT,
    )

    # Valid step 1: draft -> auto_checked
    QuizReviewWorkflow.transition_state(item, ItemReviewState.AUTO_CHECKED, notes="Automated checks passed.")
    assert item.review_state == ItemReviewState.AUTO_CHECKED

    # Valid step 2: auto_checked -> approved
    QuizReviewWorkflow.transition_state(
        item, ItemReviewState.APPROVED, reviewer_id="expert-statistician-42", notes="Reviewed and confirmed accuracy."
    )
    assert item.review_state == ItemReviewState.APPROVED
    assert item.reviewer_id == "expert-statistician-42"
    assert item.reviewed_at is not None

    # Invalid step: approved cannot jump directly to draft
    with pytest.raises(ValueError) as exc_info:
        QuizReviewWorkflow.transition_state(item, ItemReviewState.DRAFT)
    assert "Cannot transition" in str(exc_info.value)


@pytest.mark.asyncio
async def test_answer_grading_produces_structured_verdict_and_evidence():
    result_correct = await grade_student_answer(
        learner_answer="It minimizes the sum of squared residuals.",
        expected_answer="Sum of squared residuals",
        question_text="What does Ordinary Least Squares regression minimize?",
    )
    assert result_correct.score >= 0.5
    assert result_correct.verdict in {"correct", "partial"}
    assert result_correct.damage_multiplier > 0.0

    result_incorrect = await grade_student_answer(
        learner_answer="It computes quantum entanglement eigenvalues.",
        expected_answer="Sum of squared residuals",
        question_text="What does Ordinary Least Squares regression minimize?",
    )
    assert result_incorrect.score < 0.3
    assert result_incorrect.verdict == "incorrect"
    assert result_incorrect.damage_multiplier == 0.0
