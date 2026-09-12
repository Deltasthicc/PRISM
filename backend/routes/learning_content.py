"""Content and quiz routes."""

import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from db.database import get_db
from models.learning import GeneratedQuiz, GeneratedQuizAttempt, LearningMaterial
from routes.authorization import require_own_player, require_own_player_dependency, require_permission_dependency
from routes.learning_common import player_or_404
from schemas.learning import (
    DifficultyBreakdown,
    QuizAnswerResult,
    QuizResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
)
from security.rbac import BoundPrincipal, Permission
from services.content_ingestion import (
    MAX_AUDIO_VIDEO_UPLOAD_BYTES,
    MAX_UPLOAD_BYTES,
    ContentExtractionError,
    extract_text,
)
from services.quiz_generator import generate_quiz as _service_generate_quiz
from services.quiz_scoring import DIFFICULTY_WEIGHT, pace_label, time_factor

router = APIRouter(prefix="/learning", tags=["Learning Content"])


async def _generate_quiz(text, question_count, difficulty, language):
    """Resolve the quiz generator through the compatibility route module.

    Legacy dependency-security tests monkeypatch ``routes.learning.generate_quiz``
    to isolate multipart parsing. Looking up that seam at call time preserves
    those tests while keeping quiz behavior owned by this content module.
    """
    from routes import learning as compatibility_routes

    generator = getattr(compatibility_routes, "generate_quiz", _service_generate_quiz)
    return await generator(text, question_count, difficulty, language)


@router.post("/quiz/generate", response_model=QuizResponse)
async def create_quiz(
    player_id: str = Form(...),
    title: str = Form(..., min_length=2, max_length=180),
    difficulty: str = Form("mixed", pattern="^(foundation|intermediate|advanced|mixed)$"),
    language: str = Form("English", min_length=2, max_length=60),
    question_count: int = Form(5, ge=3, le=10),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.CONTENT_DRAFT_CREATE)
    ),
):
    # require_own_player_dependency doesn't apply here: player_id arrives as
    # a multipart Form field, not a path parameter. Was a bare
    # scoped_to_own_player(...) call with no demo-mode bypass -- since this
    # app's only login flow relies on DISABLE_AUTH's demo mode (see
    # require_own_player's docstring), this endpoint 403'd unconditionally.
    require_own_player(principal, player_id)
    player_or_404(db, player_id)
    # Read up to the larger of the two caps -- ai.ingestion.ingest_document()
    # applies the real, extension-aware limit (a small text document still
    # gets MAX_UPLOAD_BYTES; only audio/video gets the larger
    # MAX_AUDIO_VIDEO_UPLOAD_BYTES headroom) and rejects anything past it.
    read_limit = max(MAX_UPLOAD_BYTES, MAX_AUDIO_VIDEO_UPLOAD_BYTES)
    content = await file.read(read_limit + 1)
    try:
        text = extract_text(file.filename or "upload", content)
        questions, generation_mode = await _generate_quiz(
            text, question_count, difficulty, language
        )
    except (ContentExtractionError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    material = LearningMaterial(
        player_id=player_id,
        filename=(file.filename or "upload")[:255],
        content_type=(file.content_type or "application/octet-stream")[:120],
        sha256=hashlib.sha256(content).hexdigest(),
        character_count=len(text),
        text_excerpt=text[:1000],
    )
    db.add(material)
    db.flush()
    quiz = GeneratedQuiz(
        material_id=material.material_id,
        player_id=player_id,
        title=title,
        difficulty=difficulty,
        language=language,
        questions=questions,
        generation_mode=generation_mode,
    )
    db.add(quiz)
    db.commit()
    db.refresh(quiz)
    return QuizResponse(
        quiz_id=quiz.quiz_id,
        material_id=material.material_id,
        title=quiz.title,
        difficulty=quiz.difficulty,
        language=quiz.language,
        generation_mode=quiz.generation_mode,
        questions=quiz.questions,
    )


@router.get("/quiz/detail/{quiz_id}", response_model=QuizResponse)
async def get_quiz(
    quiz_id: str,
    player_id: str = Query(...),
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_own_player_dependency(Permission.PROFILE_SELF_READ)
    ),
):
    """Fetch one previously generated quiz's full content -- used by the
    frontend to re-open a quiz from history and take/retake it, since the
    list endpoint below only returns lightweight metadata. Also reachable
    for a quiz that isn't the caller's own, as long as it has been published
    through the real trainer review workflow (routes/quiz_review.py) --
    that's the entire point of a shared quiz library."""
    player_or_404(db, player_id)
    quiz = db.query(GeneratedQuiz).filter(GeneratedQuiz.quiz_id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    if quiz.player_id != player_id and quiz.review_status != "published":
        raise HTTPException(status_code=403, detail="This quiz belongs to a different player")
    return QuizResponse(
        quiz_id=quiz.quiz_id,
        material_id=quiz.material_id,
        title=quiz.title,
        difficulty=quiz.difficulty,
        language=quiz.language,
        generation_mode=quiz.generation_mode,
        questions=quiz.questions,
    )


@router.post("/quiz/{quiz_id}/submit", response_model=QuizSubmitResponse)
async def submit_quiz(
    quiz_id: str,
    body: QuizSubmitRequest,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.PRACTICE_SELF_WRITE)
    ),
):
    """Grade a real attempt at a previously generated quiz and return a
    time+difficulty-weighted score -- see services/quiz_scoring.py and
    schemas.learning.QuizSubmitResponse's docstring for why this
    deliberately does NOT touch AccuracyHistory/the real competency vector:
    a generated quiz's per-question `competency` is free text (from the
    model or the extractive fallback), not a real curriculum competency_id,
    so treating it as curriculum evidence would be exactly the kind of
    fabrication this project has repeatedly had to fix elsewhere.

    A published quiz (routes/quiz_review.py) can be taken by any learner,
    not just its creator. Every attempt, by anyone, is recorded as a real
    GeneratedQuizAttempt row; best_score/last_attempted_at below only ever
    reflect the creator's OWN attempts, so someone else taking a published
    copy can never overwrite the creator's recorded best."""
    require_own_player(principal, body.player_id)
    player_or_404(db, body.player_id)

    quiz = db.query(GeneratedQuiz).filter(GeneratedQuiz.quiz_id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    is_owner = quiz.player_id == body.player_id
    if not is_owner and quiz.review_status != "published":
        raise HTTPException(status_code=403, detail="This quiz belongs to a different player")

    questions = quiz.questions or []
    seen_indices = set()
    results: list[QuizAnswerResult] = []
    totals_by_difficulty: dict[str, dict] = {}
    weighted_earned = 0.0
    weighted_possible = 0.0

    for answer in body.answers:
        if answer.question_index in seen_indices or not 0 <= answer.question_index < len(questions):
            continue
        seen_indices.add(answer.question_index)
        question = questions[answer.question_index]
        difficulty = str(question.get("difficulty", "medium"))
        if difficulty not in DIFFICULTY_WEIGHT:
            difficulty = "medium"
        correct = answer.selected_index is not None and answer.selected_index == question.get("answer_index")
        factor = time_factor(difficulty, answer.time_taken_ms)
        weight = DIFFICULTY_WEIGHT[difficulty]
        weighted_possible += weight
        if correct:
            weighted_earned += weight * factor

        bucket = totals_by_difficulty.setdefault(
            difficulty, {"count": 0, "correct": 0, "time_factors": []}
        )
        bucket["count"] += 1
        bucket["correct"] += 1 if correct else 0
        bucket["time_factors"].append(factor)

        results.append(
            QuizAnswerResult(
                question_index=answer.question_index,
                correct=correct,
                correct_index=question.get("answer_index", -1),
                selected_index=answer.selected_index,
                difficulty=difficulty,
                time_factor=round(factor, 3),
                pace=pace_label(factor) if answer.time_taken_ms else None,
            )
        )

    if not results:
        raise HTTPException(status_code=422, detail="No valid answers were submitted for this quiz")

    results.sort(key=lambda item: item.question_index)
    correct_count = sum(1 for item in results if item.correct)
    accuracy = correct_count / len(results)
    weighted_score = round((weighted_earned / weighted_possible) * 100, 1) if weighted_possible else 0.0

    by_difficulty = {
        difficulty: DifficultyBreakdown(
            count=bucket["count"],
            correct=bucket["correct"],
            accuracy=round(bucket["correct"] / bucket["count"], 3) if bucket["count"] else 0.0,
            avg_time_factor=round(sum(bucket["time_factors"]) / len(bucket["time_factors"]), 3)
            if bucket["time_factors"]
            else 1.0,
        )
        for difficulty, bucket in totals_by_difficulty.items()
    }

    if is_owner:
        if quiz.best_score is None or weighted_score > quiz.best_score:
            quiz.best_score = weighted_score
        quiz.last_attempted_at = datetime.now(timezone.utc)

    db.add(
        GeneratedQuizAttempt(
            quiz_id=quiz.quiz_id,
            player_id=body.player_id,
            correct_count=correct_count,
            total_questions=len(results),
            weighted_score=weighted_score,
        )
    )
    db.commit()

    return QuizSubmitResponse(
        quiz_id=quiz.quiz_id,
        total_questions=len(results),
        correct_count=correct_count,
        accuracy=round(accuracy, 3),
        weighted_score=weighted_score,
        by_difficulty=by_difficulty,
        results=results,
    )


@router.get("/quiz/{player_id}")
async def list_quizzes(
    player_id: str,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_own_player_dependency(Permission.PROFILE_SELF_READ)
    ),
):
    player_or_404(db, player_id)
    quizzes = (
        db.query(GeneratedQuiz)
        .filter(GeneratedQuiz.player_id == player_id)
        .order_by(GeneratedQuiz.created_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "quizzes": [
            {
                "quiz_id": quiz.quiz_id,
                "title": quiz.title,
                "difficulty": quiz.difficulty,
                "language": quiz.language,
                "question_count": len(quiz.questions or []),
                "generation_mode": quiz.generation_mode,
                "created_at": quiz.created_at.isoformat() if quiz.created_at else None,
                "best_score": quiz.best_score,
                "last_attempted_at": quiz.last_attempted_at.isoformat() if quiz.last_attempted_at else None,
                "review_status": quiz.review_status,
                "reviewer_notes": quiz.reviewer_notes,
            }
            for quiz in quizzes
        ]
    }