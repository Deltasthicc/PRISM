"""Skill intelligence, recommendations, content ingestion, and admin APIs."""

import hashlib
from collections import Counter

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from db.database import get_db
from models.accuracy_history import AccuracyHistory
from models.learning import CompetencyAssessment, GeneratedQuiz, LearnerProfile, LearningMaterial
from models.player import Player
from schemas.learning import CompetencyAssessmentRequest, LearnerProfileUpsert, QuizResponse
from services.content_ingestion import ContentExtractionError, MAX_UPLOAD_BYTES, extract_text
from services.curricula import get_curriculum, public_curricula
from services.learning_catalog import integration_status
from services.learning_engine import analyse_competencies
from services.quiz_generator import generate_quiz


router = APIRouter(prefix="/learning", tags=["Learning Platform"])


def _player_or_404(db: Session, player_id: str) -> Player:
    player = db.query(Player).filter(Player.player_id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


def _serialize_profile(profile: LearnerProfile) -> dict:
    return {
        "profile_id": profile.profile_id,
        "player_id": profile.player_id,
        "designation": profile.designation,
        "department": profile.department,
        "job_role": profile.job_role,
        "current_assignment": profile.current_assignment,
        "educational_qualifications": profile.educational_qualifications,
        "years_experience": profile.years_experience or 0,
        "previous_trainings": profile.previous_trainings or [],
        "career_goal": profile.career_goal,
        "preferred_language": profile.preferred_language or "English",
        "experience_level": profile.experience_level or "beginner",
        "target_domains": profile.target_domains or [],
        "updated_at": profile.updated_at.isoformat() if profile.updated_at else None,
    }


def _measured_scores(db: Session, player_id: str) -> dict[str, float]:
    histories = db.query(AccuracyHistory).filter(AccuracyHistory.player_id == player_id).all()
    return {
        history.topic: round(max(0.0, min(1.0, history.recent_accuracy or 0.0)) * 5, 2)
        for history in histories
        if (history.attempts or 0) > 0
    }


@router.get("/curricula")
async def list_curricula():
    return {"curricula": public_curricula(), "proficiency_scale": {"minimum": 0, "maximum": 5}}


@router.get("/integrations/status")
async def get_integration_status():
    return integration_status()


@router.get("/profile/{player_id}")
async def get_profile(player_id: str, db: Session = Depends(get_db)):
    _player_or_404(db, player_id)
    profile = db.query(LearnerProfile).filter(LearnerProfile.player_id == player_id).first()
    return {"profile": _serialize_profile(profile) if profile else None}


@router.put("/profile/{player_id}")
async def upsert_profile(
    player_id: str,
    body: LearnerProfileUpsert,
    db: Session = Depends(get_db),
):
    _player_or_404(db, player_id)
    unknown_domains = [slug for slug in body.target_domains if not get_curriculum(slug)]
    if unknown_domains:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown target domain(s): {', '.join(sorted(unknown_domains))}",
        )

    profile = db.query(LearnerProfile).filter(LearnerProfile.player_id == player_id).first()
    if not profile:
        profile = LearnerProfile(player_id=player_id)
        db.add(profile)
    for field, value in body.model_dump().items():
        setattr(profile, field, value)
    db.commit()
    db.refresh(profile)
    return {"profile": _serialize_profile(profile)}


@router.post("/assessment/{player_id}")
async def assess_competencies(
    player_id: str,
    body: CompetencyAssessmentRequest,
    db: Session = Depends(get_db),
):
    _player_or_404(db, player_id)
    if not get_curriculum(body.curriculum_slug):
        raise HTTPException(status_code=404, detail="Curriculum not found")
    profile = db.query(LearnerProfile).filter(LearnerProfile.player_id == player_id).first()
    measured = _measured_scores(db, player_id)
    try:
        result = analyse_competencies(
            body.curriculum_slug,
            body.self_ratings,
            measured,
            profile.experience_level if profile else "beginner",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    assessment = CompetencyAssessment(
        player_id=player_id,
        curriculum_slug=body.curriculum_slug,
        self_ratings=body.self_ratings,
        measured_scores=measured,
        skill_gaps=result["skill_gaps"],
        recommended_course_ids=[course["course_id"] for course in result["courses"]],
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return {"assessment_id": assessment.assessment_id, **result}


@router.get("/pathway/{player_id}")
async def get_pathway(
    player_id: str,
    curriculum_slug: str = Query(..., min_length=2, max_length=120),
    db: Session = Depends(get_db),
):
    _player_or_404(db, player_id)
    profile = db.query(LearnerProfile).filter(LearnerProfile.player_id == player_id).first()
    latest = (
        db.query(CompetencyAssessment)
        .filter(
            CompetencyAssessment.player_id == player_id,
            CompetencyAssessment.curriculum_slug == curriculum_slug,
        )
        .order_by(CompetencyAssessment.created_at.desc())
        .first()
    )
    try:
        return analyse_competencies(
            curriculum_slug,
            latest.self_ratings if latest else {},
            _measured_scores(db, player_id),
            profile.experience_level if profile else "beginner",
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/quiz/generate", response_model=QuizResponse)
async def create_quiz(
    player_id: str = Form(...),
    title: str = Form(..., min_length=2, max_length=180),
    difficulty: str = Form("mixed", pattern="^(foundation|intermediate|advanced|mixed)$"),
    language: str = Form("English", min_length=2, max_length=60),
    question_count: int = Form(5, ge=3, le=10),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    _player_or_404(db, player_id)
    # Bound the read itself, not only the parser. UploadFile may spool to disk,
    # but an unrestricted read would still allocate an attacker-controlled
    # payload in process memory before extract_text could reject it.
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        text = extract_text(file.filename or "upload", content)
        questions, generation_mode = await generate_quiz(
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
):
    _player_or_404(db, player_id)
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


@router.get("/admin/overview")
async def admin_overview(db: Session = Depends(get_db)):
    """Aggregate-only demo dashboard; no learner PII is returned."""
    assessments = db.query(CompetencyAssessment).all()
    gap_counter = Counter()
    priority_counter = Counter()
    for assessment in assessments:
        for gap in assessment.skill_gaps or []:
            gap_counter[gap.get("label") or gap.get("competency_id", "Unknown")] += 1
            priority_counter[gap.get("priority", "unknown")] += 1
    return {
        "learners": db.query(Player).count(),
        "profiles_completed": db.query(LearnerProfile).count(),
        "assessments_completed": len(assessments),
        "quizzes_generated": db.query(GeneratedQuiz).count(),
        "top_skill_gaps": [
            {"competency": competency, "learner_count": count}
            for competency, count in gap_counter.most_common(8)
        ],
        "gap_priorities": dict(priority_counter),
        "integration_status": integration_status(),
        "privacy_note": "This endpoint intentionally exposes aggregates only. Production access still requires RBAC.",
    }
