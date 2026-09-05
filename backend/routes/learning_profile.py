"""Learner profile routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from db.database import get_db
from models.learning import LearnerProfile
from routes.authorization import require_own_player_dependency
from routes.learning_common import player_or_404, serialize_profile
from schemas.learning import LearnerProfileUpsert
from security.rbac import BoundPrincipal, Permission
from services.curricula import get_curriculum

router = APIRouter(prefix="/learning", tags=["Learning Profile"])


@router.get("/profile/{player_id}")
async def get_profile(
    player_id: str,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_own_player_dependency(Permission.PROFILE_SELF_READ)
    ),
):
    player_or_404(db, player_id)
    profile = db.query(LearnerProfile).filter(LearnerProfile.player_id == player_id).first()
    return {"profile": serialize_profile(profile) if profile else None}


@router.put("/profile/{player_id}")
async def upsert_profile(
    player_id: str,
    body: LearnerProfileUpsert,
    db: Session = Depends(get_db),
    principal: BoundPrincipal = Depends(
        require_own_player_dependency(Permission.PROFILE_SELF_WRITE)
    ),
):
    player_or_404(db, player_id)
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
    return {"profile": serialize_profile(profile)}