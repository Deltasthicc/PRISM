"""Privacy-safe aggregate analytics routes."""

from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from db.database import get_db
from models.learning import CompetencyAssessment, GeneratedQuiz, LearnerProfile
from models.player import Player
from routes.authorization import require_permission_dependency
from security.rbac import BoundPrincipal, Permission
from services.learning_catalog import integration_status

router = APIRouter(prefix="/learning", tags=["Learning Analytics"])


@router.get("/admin/overview")
async def admin_overview(
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.ORGANIZATION_ANALYTICS_READ)
    ),
):
    """Aggregate-only dashboard using the latest assessment per learner stream."""
    assessments_by_stream = {}
    for assessment in db.query(CompetencyAssessment).all():
        key = (assessment.player_id, assessment.curriculum_slug)
        current = assessments_by_stream.get(key)
        if current is None or (
            assessment.created_at, assessment.assessment_id
        ) > (current.created_at, current.assessment_id):
            assessments_by_stream[key] = assessment
    assessments = list(assessments_by_stream.values())
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
        "privacy_note": "This endpoint intentionally exposes latest-distinct-learner aggregates only.",
    }