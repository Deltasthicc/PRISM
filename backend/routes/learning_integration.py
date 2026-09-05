"""Provider integration routes."""

from fastapi import APIRouter

from services.learning_catalog import integration_status

router = APIRouter(prefix="/learning", tags=["Learning Integrations"])


@router.get("/integrations/status")
async def get_integration_status():
    return integration_status()