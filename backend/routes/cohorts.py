"""Real trainer/cohort assignment and scoped performance visibility
(SIH26075 CC-08/PS75-09).

Admin creates a cohort and assigns it to exactly one trainer
(`Permission.COHORT_MANAGE`); the trainer gets read access
(`Permission.COHORT_READ`) scoped to only that cohort's members. Every
trainer-facing read route checks ownership via `_cohort_or_404_scoped`
below, the same pattern `routes/course_catalog.py` established for
courses -- a role name is never object scope by itself.

The performance view reports only data that already exists in this
codebase's own tables (CourseEnrollment, CompetencyAssessment) -- no
invented score, no fabricated trend. A member with no assessments yet
reports that honestly (null/zero), never a default that looks like a
real measurement.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from db.database import get_db
from models.cohort import Cohort, CohortMembership
from models.course_enrollment import CourseEnrollment
from models.learning import CompetencyAssessment
from models.player import Player
from routes.authorization import require_own_player, require_permission_dependency
from routes.learning_common import player_or_404
from security.rbac import BoundPrincipal, Permission, permissions_for

router = APIRouter(prefix="/learning/cohorts", tags=["Cohorts"])


class CohortCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    trainer_id: str


class CohortResponse(BaseModel):
    cohort_id: str
    name: str
    trainer_id: str
    member_count: int
    created_at: datetime


class MemberResponse(BaseModel):
    player_id: str
    username: str
    added_at: datetime


class MemberPerformance(BaseModel):
    player_id: str
    username: str
    courses_enrolled: int
    courses_completed: int
    assessments_taken: int
    latest_assessment_at: datetime | None
    open_skill_gaps: int | None


def _serialize(cohort: Cohort, db: Session) -> CohortResponse:
    count = db.query(CohortMembership).filter(CohortMembership.cohort_id == cohort.cohort_id).count()
    return CohortResponse(
        cohort_id=cohort.cohort_id,
        name=cohort.name,
        trainer_id=cohort.trainer_id,
        member_count=count,
        created_at=cohort.created_at,
    )


def _cohort_or_404_scoped(db: Session, cohort_id: str, principal: BoundPrincipal) -> Cohort:
    """Admin (COHORT_MANAGE) may read any cohort; a trainer may only read
    a cohort assigned to them. Both cases collapse to the same 404 on
    denial -- a trainer probing another trainer's cohort id should learn
    nothing about whether it exists, matching this codebase's existing
    object-scope conventions (routes/course_catalog.py, routes/authorization.py)."""
    cohort = db.query(Cohort).filter(Cohort.cohort_id == cohort_id).one_or_none()
    if cohort is None:
        raise HTTPException(status_code=404, detail="Cohort not found")
    if Permission.COHORT_MANAGE in permissions_for(principal):
        return cohort
    if cohort.trainer_id == principal.player_id:
        return cohort
    raise HTTPException(status_code=404, detail="Cohort not found")


@router.post("", response_model=CohortResponse)
def create_cohort(
    body: CohortCreateRequest,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.COHORT_MANAGE)),
    db: Session = Depends(get_db),
) -> CohortResponse:
    player_or_404(db, body.trainer_id)
    cohort = Cohort(name=body.name.strip(), trainer_id=body.trainer_id)
    db.add(cohort)
    db.commit()
    db.refresh(cohort)
    return _serialize(cohort, db)


@router.get("", response_model=list[CohortResponse])
def list_all_cohorts(
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.COHORT_MANAGE)),
    db: Session = Depends(get_db),
) -> list[CohortResponse]:
    rows = db.query(Cohort).order_by(Cohort.created_at.desc()).all()
    return [_serialize(row, db) for row in rows]


@router.get("/mine", response_model=list[CohortResponse])
def list_my_cohorts(
    trainer_id: str,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.COHORT_READ)),
    db: Session = Depends(get_db),
) -> list[CohortResponse]:
    require_own_player(principal, trainer_id)
    rows = (
        db.query(Cohort)
        .filter(Cohort.trainer_id == trainer_id)
        .order_by(Cohort.created_at.desc())
        .all()
    )
    return [_serialize(row, db) for row in rows]


@router.post("/{cohort_id}/members", response_model=MemberResponse)
def add_member(
    cohort_id: str,
    player_id: str,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.COHORT_MANAGE)),
    db: Session = Depends(get_db),
) -> MemberResponse:
    cohort = db.query(Cohort).filter(Cohort.cohort_id == cohort_id).one_or_none()
    if cohort is None:
        raise HTTPException(status_code=404, detail="Cohort not found")
    player = player_or_404(db, player_id)

    existing = (
        db.query(CohortMembership)
        .filter(CohortMembership.cohort_id == cohort_id, CohortMembership.player_id == player_id)
        .one_or_none()
    )
    if existing is not None:
        return MemberResponse(player_id=player.player_id, username=player.username, added_at=existing.added_at)

    membership = CohortMembership(cohort_id=cohort_id, player_id=player_id)
    db.add(membership)
    db.commit()
    db.refresh(membership)
    return MemberResponse(player_id=player.player_id, username=player.username, added_at=membership.added_at)


@router.delete("/{cohort_id}/members/{player_id}")
def remove_member(
    cohort_id: str,
    player_id: str,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.COHORT_MANAGE)),
    db: Session = Depends(get_db),
) -> dict:
    membership = (
        db.query(CohortMembership)
        .filter(CohortMembership.cohort_id == cohort_id, CohortMembership.player_id == player_id)
        .one_or_none()
    )
    if membership is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    db.delete(membership)
    db.commit()
    return {"removed": True}


@router.get("/{cohort_id}/members", response_model=list[MemberResponse])
def list_members(
    cohort_id: str,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.COHORT_READ)),
    db: Session = Depends(get_db),
) -> list[MemberResponse]:
    _cohort_or_404_scoped(db, cohort_id, principal)
    rows = (
        db.query(CohortMembership, Player)
        .join(Player, Player.player_id == CohortMembership.player_id)
        .filter(CohortMembership.cohort_id == cohort_id)
        .order_by(CohortMembership.added_at.asc())
        .all()
    )
    return [
        MemberResponse(player_id=player.player_id, username=player.username, added_at=membership.added_at)
        for membership, player in rows
    ]


@router.get("/{cohort_id}/performance", response_model=list[MemberPerformance])
def cohort_performance(
    cohort_id: str,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.COHORT_READ)),
    db: Session = Depends(get_db),
) -> list[MemberPerformance]:
    """Real participation/performance for this cohort's members, pulled
    directly from CourseEnrollment and CompetencyAssessment -- nothing
    here is computed or estimated beyond a straight count/latest-row read
    of tables that already exist for other reasons."""
    _cohort_or_404_scoped(db, cohort_id, principal)
    members = (
        db.query(CohortMembership, Player)
        .join(Player, Player.player_id == CohortMembership.player_id)
        .filter(CohortMembership.cohort_id == cohort_id)
        .order_by(CohortMembership.added_at.asc())
        .all()
    )

    results: list[MemberPerformance] = []
    for membership, player in members:
        enrolled = (
            db.query(func.count(CourseEnrollment.enrollment_id))
            .filter(CourseEnrollment.player_id == player.player_id)
            .scalar()
            or 0
        )
        completed = (
            db.query(func.count(CourseEnrollment.enrollment_id))
            .filter(
                CourseEnrollment.player_id == player.player_id,
                CourseEnrollment.status == "completed",
            )
            .scalar()
            or 0
        )
        assessments_taken = (
            db.query(func.count(CompetencyAssessment.assessment_id))
            .filter(CompetencyAssessment.player_id == player.player_id)
            .scalar()
            or 0
        )
        latest_assessment = (
            db.query(CompetencyAssessment)
            .filter(CompetencyAssessment.player_id == player.player_id)
            .order_by(CompetencyAssessment.created_at.desc())
            .first()
        )
        results.append(
            MemberPerformance(
                player_id=player.player_id,
                username=player.username,
                courses_enrolled=enrolled,
                courses_completed=completed,
                assessments_taken=assessments_taken,
                latest_assessment_at=latest_assessment.created_at if latest_assessment else None,
                open_skill_gaps=len(latest_assessment.skill_gaps) if latest_assessment else None,
            )
        )
    return results
