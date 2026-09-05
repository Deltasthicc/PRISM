"""Curriculum, assessment and pathway routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from db.database import get_db
from db.repositories import get_latest_assessment
from models.learning import CompetencyAssessment, LearnerProfile
from routes.authorization import require_own_player_dependency
from routes.learning_common import measured_scores, player_or_404, serialize_assessment
from schemas.learning import CompetencyAssessmentRequest
from security.rbac import BoundPrincipal, Permission
from services.curricula import get_curriculum, public_curricula
from services.evidence_resolver import resolve_evidence
from services.learning_engine import analyse_competencies
from services.role_target_resolver import resolve_role_targets

router = APIRouter(prefix="/learning", tags=["Learning Competency"])


def _resolve_competency_context(
    db: Session,
    player_id: str,
    curriculum_slug: str,
    curriculum: dict,
    profile,
):
    competency_ids = [item["id"] for item in curriculum["competencies"]]
    evidence = resolve_evidence(db, player_id, competency_ids)
    role_targets = resolve_role_targets(
        db,
        curriculum_slug,
        job_role=profile.job_role if profile else "",
        designation=profile.designation if profile else "",
        current_assignment=profile.current_assignment if profile else "",
        department=profile.department if profile else "",
    )
    return evidence, role_targets


@router.get("/curricula")
async def list_curricula():
    return {"curricula": public_curricula(), "proficiency_scale": {"minimum": 0, "maximum": 5}}


@router.post("/assessment/{player_id}")
async def assess_competencies(
    player_id: str,
    body: CompetencyAssessmentRequest,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_own_player_dependency(Permission.ASSESSMENT_SELF_WRITE)
    ),
):
    player_or_404(db, player_id)
    if not get_curriculum(body.curriculum_slug):
        raise HTTPException(status_code=404, detail="Curriculum not found")
    profile = db.query(LearnerProfile).filter(LearnerProfile.player_id == player_id).first()
    measured = measured_scores(db, player_id)
    curriculum = get_curriculum(body.curriculum_slug)
    evidence, role_targets = _resolve_competency_context(
        db, player_id, body.curriculum_slug, curriculum, profile
    )
    try:
        result = analyse_competencies(
            body.curriculum_slug,
            body.self_ratings,
            measured,
            profile.experience_level if profile else "beginner",
            evidence=evidence,
            role_targets=role_targets,
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
    principal: BoundPrincipal = Depends(
        require_own_player_dependency(Permission.PATHWAY_SELF_READ)
    ),
):
    player_or_404(db, player_id)
    profile = db.query(LearnerProfile).filter(LearnerProfile.player_id == player_id).first()
    latest = get_latest_assessment(db, player_id, curriculum_slug)
    curriculum = get_curriculum(curriculum_slug)
    if not curriculum:
        raise HTTPException(status_code=404, detail="Curriculum not found")
    evidence, role_targets = _resolve_competency_context(
        db, player_id, curriculum_slug, curriculum, profile
    )
    try:
        return analyse_competencies(
            curriculum_slug,
            latest.self_ratings if latest else {},
            measured_scores(db, player_id),
            profile.experience_level if profile else "beginner",
            evidence=evidence,
            role_targets=role_targets,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/assessment/{player_id}/latest")
async def latest_assessment(
    player_id: str,
    curriculum_slug: str = Query(..., min_length=2, max_length=120),
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_own_player_dependency(Permission.ASSESSMENT_SELF_READ)
    ),
):
    player_or_404(db, player_id)
    assessment = get_latest_assessment(db, player_id, curriculum_slug)
    return {"assessment": serialize_assessment(assessment) if assessment else None}