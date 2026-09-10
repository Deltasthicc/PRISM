"""Provider integration routes."""

from fastapi import APIRouter, Query

from services.learning_catalog import integration_status

router = APIRouter(prefix="/learning", tags=["Learning Integrations"])


@router.get("/integrations/status")
async def get_integration_status(lang: str = Query("en", pattern="^(en|hi|bn|mr|te|ta|gu|ur|kn|or|ml)$")):
    return integration_status(lang)
