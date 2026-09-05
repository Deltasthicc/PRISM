"""Content and quiz routes."""

import hashlib

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from db.database import get_db
from models.learning import GeneratedQuiz, LearningMaterial
from routes.authorization import require_own_player_dependency, require_permission_dependency
from routes.learning_common import player_or_404
from schemas.learning import QuizResponse
from security.rbac import BoundPrincipal, Permission, scoped_to_own_player
from services.content_ingestion import ContentExtractionError, MAX_UPLOAD_BYTES, extract_text
from services.quiz_generator import generate_quiz as _service_generate_quiz

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
    try:
        scoped_to_own_player(principal, player_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail="Access denied") from exc
    player_or_404(db, player_id)
    content = await file.read(MAX_UPLOAD_BYTES + 1)
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
            }
            for quiz in quizzes
        ]
    }