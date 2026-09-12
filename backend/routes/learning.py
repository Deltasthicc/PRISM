"""Compatibility aggregator for the split learning route modules."""

from fastapi import APIRouter
from services.quiz_generator import generate_quiz

from routes.learning_analytics import admin_overview, router as analytics_router
from routes.learning_competency import (
    assess_competencies,
    get_pathway,
    latest_assessment,
    list_curricula,
    router as competency_router,
)
from routes.learning_content import create_quiz, list_quizzes, router as content_router
from routes.learning_integration import get_integration_status, router as integration_router
from routes.learning_profile import get_profile, router as profile_router, upsert_profile
from routes.competency_quiz import router as competency_quiz_router
from routes.dsa_sandbox import router as dsa_sandbox_router
from routes.sampling_lab import router as sampling_lab_router
from routes.course_enrollment import router as course_enrollment_router
from routes.proctoring import router as proctoring_router

router = APIRouter()
router.include_router(profile_router)
router.include_router(competency_router)
router.include_router(content_router)
router.include_router(integration_router)
router.include_router(analytics_router)
router.include_router(competency_quiz_router)
router.include_router(dsa_sandbox_router)
router.include_router(sampling_lab_router)
router.include_router(course_enrollment_router)
router.include_router(proctoring_router)

__all__ = [
    "admin_overview",
    "assess_competencies",
    "create_quiz",
    "get_integration_status",
    "get_pathway",
    "get_profile",
    "generate_quiz",
    "latest_assessment",
    "list_curricula",
    "list_quizzes",
    "router",
    "upsert_profile",
]
