"""Shared helpers for the behavior-specific learning route modules."""

from fastapi import HTTPException
from sqlalchemy.orm import Session

from models.accuracy_history import AccuracyHistory
from models.learning import CompetencyAssessment, LearnerProfile
from models.player import Player


def player_or_404(db: Session, player_id: str) -> Player:
    player = db.query(Player).filter(Player.player_id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    return player


def serialize_profile(profile: LearnerProfile) -> dict:
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


def measured_scores(db: Session, player_id: str) -> dict[str, float]:
    histories = db.query(AccuracyHistory).filter(AccuracyHistory.player_id == player_id).all()
    return {
        history.topic: round(max(0.0, min(1.0, history.recent_accuracy or 0.0)) * 5, 2)
        for history in histories
        if (history.attempts or 0) > 0
    }


def serialize_assessment(assessment: CompetencyAssessment) -> dict:
    return {
        "assessment_id": assessment.assessment_id,
        "player_id": assessment.player_id,
        "curriculum_slug": assessment.curriculum_slug,
        "self_ratings": assessment.self_ratings or {},
        "measured_scores": assessment.measured_scores or {},
        "skill_gaps": assessment.skill_gaps or [],
        "created_at": assessment.created_at.isoformat() if assessment.created_at else None,
    }