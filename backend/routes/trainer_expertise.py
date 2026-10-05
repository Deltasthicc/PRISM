"""Trainer expertise profile and trainer-to-subject matching
(SIH26075 PS75-07 / PS75-14).

* A trainer declares (PUT) which competencies they can teach, at what
  self-declared level and on what basis. Those rows are unverified claims.
* An organization admin asks "who is suitable to teach competency X"
  (GET /match); the ranking is produced by `services/trainer_matching.py`, a
  deterministic, versioned policy over stored facts. See that module for the
  honesty rules (NO_EVIDENCE is never a low score).
* `GET /{trainer_id}/profile` is a read-only combination of the existing
  `LearnerProfile` (still written through the existing profile route -- not
  duplicated here) and the expertise rows.

Every route takes an explicit `trainer_id` and checks it with
`require_own_player` (the `DISABLE_AUTH` demo principal has no `player_id`),
exactly as `routes/course_catalog.py` does. Ownership is checked before the
player lookup so a probe learns nothing about whether an id exists.
Reads by an admin (`TRAINER_MATCH_READ`) are not restricted to one trainer.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from db.database import get_db
from models.learning import LearnerProfile
from models.trainer_expertise import TrainerExpertise
from routes.authorization import require_own_player, require_permission_dependency
from routes.learning_common import player_or_404, serialize_profile
from security.rbac import BoundPrincipal, Permission, permissions_for
from services.trainer_matching import (
    SELF_DECLARED_NOTICE,
    competency_catalog,
    match_trainers,
)

router = APIRouter(prefix="/learning/trainers", tags=["Trainer Expertise"])


class ExpertiseUpsertRequest(BaseModel):
    declared_level: int = Field(..., ge=1, le=5, description="Self-declared teaching proficiency, 1-5")
    basis: Literal["degree", "certification", "experience", "other"]
    basis_detail: str = Field("", max_length=500)
    years_teaching: int = Field(0, ge=0, le=80)


class ExpertiseResponse(BaseModel):
    expertise_id: str
    trainer_id: str
    competency_id: str
    competency_label: str
    declared_level: int
    basis: str
    basis_detail: str
    years_teaching: int
    self_declared: bool = True
    verified: bool = False
    created_at: datetime
    updated_at: datetime


class TrainerExpertiseListResponse(BaseModel):
    trainer_id: str
    notice: str
    expertise: list[ExpertiseResponse]


class TrainerProfileResponse(BaseModel):
    trainer_id: str
    username: str
    profile: dict[str, Any] | None
    notice: str
    expertise: list[ExpertiseResponse]


class ScoreComponent(BaseModel):
    key: str
    label: str
    weight: float
    raw_value: Any = None
    fraction: float | None
    points: float
    available: bool
    note: str


class DeclaredFacts(BaseModel):
    declared_level: int
    basis: str
    basis_detail: str
    years_teaching: int
    self_declared: bool
    verified: bool


class MatchFacts(BaseModel):
    declared: DeclaredFacts | None
    published_courses: int
    learners_completed: int
    rating_count: int
    mean_rating: float | None
    mean_rating_reason: str | None


class TrainerMatch(BaseModel):
    rank: int | None
    trainer_id: str
    username: str
    full_name: str
    evidence_level: Literal["DECLARED_ONLY", "DECLARED_AND_ACTIVITY", "ACTIVITY_ONLY", "NO_EVIDENCE"]
    score: float | None
    components: list[ScoreComponent]
    facts: MatchFacts
    rationale: list[str]


class TrainerMatchResponse(BaseModel):
    policy_version: str
    max_points: int
    declared_max_points: float
    weights: dict[str, float]
    min_ratings_for_mean: int
    competency_id: str
    competency_label: str
    notice: str
    trainers: list[TrainerMatch]


def _serialize(row: TrainerExpertise) -> ExpertiseResponse:
    return ExpertiseResponse(
        expertise_id=row.expertise_id,
        trainer_id=row.trainer_id,
        competency_id=row.competency_id,
        competency_label=competency_catalog().get(row.competency_id, row.competency_id),
        declared_level=row.declared_level,
        basis=row.basis,
        basis_detail=row.basis_detail or "",
        years_teaching=row.years_teaching,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _require_known_competency(competency_id: str) -> str:
    if competency_id not in competency_catalog():
        raise HTTPException(status_code=422, detail=f"Unknown competency_id: {competency_id!r}")
    return competency_id


def _check_read_scope(principal: BoundPrincipal, trainer_id: str) -> None:
    """An admin who may run trainer matching may read any trainer's
    expertise; everyone else only their own."""
    if Permission.TRAINER_MATCH_READ in permissions_for(principal):
        return
    require_own_player(principal, trainer_id)


def _find(db: Session, trainer_id: str, competency_id: str) -> TrainerExpertise | None:
    return (
        db.query(TrainerExpertise)
        .filter(
            TrainerExpertise.trainer_id == trainer_id,
            TrainerExpertise.competency_id == competency_id,
        )
        .one_or_none()
    )


def _apply(row: TrainerExpertise, body: ExpertiseUpsertRequest) -> None:
    row.declared_level = body.declared_level
    row.basis = body.basis
    row.basis_detail = body.basis_detail.strip()
    row.years_teaching = body.years_teaching


def _list_rows(db: Session, trainer_id: str) -> list[TrainerExpertise]:
    return (
        db.query(TrainerExpertise)
        .filter(TrainerExpertise.trainer_id == trainer_id)
        .order_by(TrainerExpertise.competency_id.asc())
        .all()
    )


# NOTE: declared before the "/{trainer_id}/..." routes only for readability;
# "/match" has a different segment count so there is no path ambiguity.
@router.get("/match", response_model=TrainerMatchResponse)
def match(
    competency_id: str = Query(..., min_length=1, max_length=200),
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.TRAINER_MATCH_READ)),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    _require_known_competency(competency_id)
    return match_trainers(db, competency_id)


@router.put("/{trainer_id}/expertise/{competency_id}", response_model=ExpertiseResponse)
def upsert_expertise(
    trainer_id: str,
    competency_id: str,
    body: ExpertiseUpsertRequest,
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.TRAINER_EXPERTISE_MANAGE)
    ),
    db: Session = Depends(get_db),
) -> ExpertiseResponse:
    require_own_player(principal, trainer_id)
    _require_known_competency(competency_id)
    player_or_404(db, trainer_id)

    row = _find(db, trainer_id, competency_id)
    if row is None:
        row = TrainerExpertise(trainer_id=trainer_id, competency_id=competency_id)
        _apply(row, body)
        db.add(row)
        try:
            db.commit()
        except IntegrityError:
            # A concurrent PUT for the same (trainer, competency) inserted the
            # row first; the unique constraint is the real guard. Apply this
            # request's values onto the winner (PUT is last-writer-wins).
            db.rollback()
            row = _find(db, trainer_id, competency_id)
            if row is None:
                raise
            _apply(row, body)
            db.commit()
    else:
        _apply(row, body)
        db.commit()
    db.refresh(row)
    return _serialize(row)


@router.get("/{trainer_id}/expertise", response_model=TrainerExpertiseListResponse)
def list_expertise(
    trainer_id: str,
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.TRAINER_EXPERTISE_MANAGE)
    ),
    db: Session = Depends(get_db),
) -> TrainerExpertiseListResponse:
    _check_read_scope(principal, trainer_id)
    player_or_404(db, trainer_id)
    return TrainerExpertiseListResponse(
        trainer_id=trainer_id,
        notice=SELF_DECLARED_NOTICE,
        expertise=[_serialize(row) for row in _list_rows(db, trainer_id)],
    )


@router.delete("/{trainer_id}/expertise/{competency_id}")
def delete_expertise(
    trainer_id: str,
    competency_id: str,
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.TRAINER_EXPERTISE_MANAGE)
    ),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    require_own_player(principal, trainer_id)
    deleted = (
        db.query(TrainerExpertise)
        .filter(
            TrainerExpertise.trainer_id == trainer_id,
            TrainerExpertise.competency_id == competency_id,
        )
        .delete(synchronize_session=False)
    )
    if deleted == 0:
        db.rollback()
        raise HTTPException(status_code=404, detail="Expertise not found")
    db.commit()
    return {"removed": True}


@router.get("/{trainer_id}/profile", response_model=TrainerProfileResponse)
def trainer_profile(
    trainer_id: str,
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.TRAINER_EXPERTISE_MANAGE)
    ),
    db: Session = Depends(get_db),
) -> TrainerProfileResponse:
    """Read-only: the existing LearnerProfile plus declared expertise. The
    base profile is still edited through PUT /learning/profile/{player_id}."""
    _check_read_scope(principal, trainer_id)
    player = player_or_404(db, trainer_id)
    profile = db.query(LearnerProfile).filter(LearnerProfile.player_id == trainer_id).first()
    return TrainerProfileResponse(
        trainer_id=trainer_id,
        username=player.username,
        profile=serialize_profile(profile) if profile else None,
        notice=SELF_DECLARED_NOTICE,
        expertise=[_serialize(row) for row in _list_rows(db, trainer_id)],
    )
