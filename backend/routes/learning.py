"""Compatibility aggregator for the split learning route modules."""

from fastapi import APIRouter

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

router = APIRouter()
router.include_router(profile_router)
router.include_router(competency_router)
router.include_router(content_router)
router.include_router(integration_router)
router.include_router(analytics_router)

__all__ = [
    "admin_overview",
    "assess_competencies",
    "create_quiz",
    "get_integration_status",
    "get_pathway",
    "get_profile",
    "latest_assessment",
    "list_curricula",
    "list_quizzes",
    "router",
    "upsert_profile",
]
