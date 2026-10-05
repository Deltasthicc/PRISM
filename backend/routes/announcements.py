"""In-app announcements and the homepage feed (SIH26075 PS75-13).

"Notifications" here means this in-app feed only -- nothing is pushed,
emailed or texted. Two surfaces:

* Admin authoring (`/learning/announcements`, `ANNOUNCEMENT_MANAGE`,
  organization_admin only): create a draft or publish immediately, list
  everything (drafts and expired included), publish and unpublish. There is
  deliberately no DELETE: unpublishing is the retire path and keeps history.
  Every create/publish/unpublish writes an audit event in the same
  transaction as the change.
* The feed (`/learning/home/feed`, `HOME_FEED_READ`): derived only from rows
  that really exist -- published announcements for the caller's audience,
  recently created published internal courses, and the caller's OWN
  certificates. Empty sections are returned empty; nothing is invented.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_
from sqlalchemy.orm import Session

from db.database import get_db
from models.announcement import Announcement
from models.certificate import Certificate
from models.course import Course
from routes.authorization import require_own_player, require_permission_dependency
from routes.learning_common import player_or_404
from security.audit import record_audit_event
from security.rbac import BoundPrincipal, Permission

router = APIRouter(prefix="/learning/announcements", tags=["Announcements"])
feed_router = APIRouter(prefix="/learning/home", tags=["Home feed"])

FEED_ANNOUNCEMENT_LIMIT = 20
FEED_COURSE_LIMIT = 10
FEED_COURSE_WINDOW_DAYS = 30
FEED_ACHIEVEMENT_LIMIT = 20
FEED_ACHIEVEMENT_WINDOW_DAYS = 90

Kind = Literal["announcement", "achievement", "new_content"]
Audience = Literal["all", "learner", "trainer"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; everything we store is UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


class AnnouncementCreateRequest(BaseModel):
    title: str = Field(..., max_length=200)
    body: str = Field(..., max_length=4000)
    kind: Kind = "announcement"
    audience: Audience = "all"
    expires_at: datetime | None = None
    publish: bool = False

    @field_validator("title", "body")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("expires_at")
    @classmethod
    def _expires_aware(cls, value: datetime | None) -> datetime | None:
        return _aware(value)


class AnnouncementResponse(BaseModel):
    announcement_id: str
    title: str
    body: str
    kind: str
    audience: str
    created_by: str
    is_published: bool
    # draft = never published; published = live; unpublished = retired by an
    # admin; expired = published but past expires_at (no longer shown).
    status: Literal["draft", "published", "unpublished", "expired"]
    published_at: datetime | None
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


def _status(row: Announcement, now: datetime) -> str:
    if row.is_published:
        expires_at = _aware(row.expires_at)
        if expires_at is not None and expires_at <= now:
            return "expired"
        return "published"
    return "draft" if row.published_at is None else "unpublished"


def _serialize(row: Announcement) -> AnnouncementResponse:
    return AnnouncementResponse(
        announcement_id=row.announcement_id,
        title=row.title,
        body=row.body,
        kind=row.kind,
        audience=row.audience,
        created_by=row.created_by,
        is_published=row.is_published,
        status=_status(row, _utcnow()),
        published_at=_aware(row.published_at),
        expires_at=_aware(row.expires_at),
        created_at=_aware(row.created_at),
        updated_at=_aware(row.updated_at),
    )


def _announcement_or_404(db: Session, announcement_id: str) -> Announcement:
    row = db.query(Announcement).filter(Announcement.announcement_id == announcement_id).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return row


def _require_future_expiry(expires_at: datetime | None, now: datetime) -> None:
    if expires_at is not None and _aware(expires_at) <= now:
        raise HTTPException(status_code=422, detail="expires_at must be in the future")


@router.post("", response_model=AnnouncementResponse)
def create_announcement(
    body: AnnouncementCreateRequest,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.ANNOUNCEMENT_MANAGE)),
    db: Session = Depends(get_db),
) -> AnnouncementResponse:
    now = _utcnow()
    # A draft with an already-past expiry could never be shown, so reject it
    # at creation as well as at publish time.
    _require_future_expiry(body.expires_at, now)
    row = Announcement(
        title=body.title,
        body=body.body,
        kind=body.kind,
        audience=body.audience,
        created_by=principal.audit_actor,
        is_published=body.publish,
        published_at=now if body.publish else None,
        expires_at=body.expires_at,
    )
    db.add(row)
    db.flush()
    record_audit_event(
        db,
        actor=principal.audit_actor,
        action="announcement.create",
        entity_type="announcement",
        entity_id=row.announcement_id,
        details={"kind": row.kind, "audience": row.audience, "published": body.publish},
        commit=False,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.get("", response_model=list[AnnouncementResponse])
def list_all_announcements(
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.ANNOUNCEMENT_MANAGE)),
    db: Session = Depends(get_db),
) -> list[AnnouncementResponse]:
    rows = db.query(Announcement).order_by(Announcement.created_at.desc()).all()
    return [_serialize(row) for row in rows]


@router.post("/{announcement_id}/publish", response_model=AnnouncementResponse)
def publish_announcement(
    announcement_id: str,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.ANNOUNCEMENT_MANAGE)),
    db: Session = Depends(get_db),
) -> AnnouncementResponse:
    row = _announcement_or_404(db, announcement_id)
    if row.is_published:
        # Idempotent: already published, keep the original published_at and
        # do not write a second audit event for a no-op.
        return _serialize(row)
    now = _utcnow()
    _require_future_expiry(row.expires_at, now)
    row.is_published = True
    row.published_at = now
    record_audit_event(
        db,
        actor=principal.audit_actor,
        action="announcement.publish",
        entity_type="announcement",
        entity_id=row.announcement_id,
        details={"kind": row.kind, "audience": row.audience},
        commit=False,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row)


@router.post("/{announcement_id}/unpublish", response_model=AnnouncementResponse)
def unpublish_announcement(
    announcement_id: str,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.ANNOUNCEMENT_MANAGE)),
    db: Session = Depends(get_db),
) -> AnnouncementResponse:
    row = _announcement_or_404(db, announcement_id)
    if not row.is_published:
        return _serialize(row)
    row.is_published = False
    record_audit_event(
        db,
        actor=principal.audit_actor,
        action="announcement.unpublish",
        entity_type="announcement",
        entity_id=row.announcement_id,
        details={"kind": row.kind, "audience": row.audience},
        commit=False,
    )
    db.commit()
    db.refresh(row)
    return _serialize(row)


# --------------------------------------------------------------------------
# Home feed
# --------------------------------------------------------------------------


class FeedAnnouncement(BaseModel):
    announcement_id: str
    title: str
    body: str
    kind: str
    audience: str
    published_at: datetime | None
    expires_at: datetime | None


class FeedCourse(BaseModel):
    course_id: str
    title: str
    description: str
    created_at: datetime


class FeedAchievement(BaseModel):
    certificate_id: str
    title: str
    course_id: str
    issued_at: datetime


class HomeFeedResponse(BaseModel):
    announcements: list[FeedAnnouncement]
    new_courses: list[FeedCourse]
    my_achievements: list[FeedAchievement]
    generated_at: datetime


def _audiences_for(principal: BoundPrincipal) -> list[str]:
    """Which announcement audiences this caller's roles may see.

    Everyone sees "all". "learner"/"trainer" follow the caller's roles. A
    caller with no roles at all is treated as a learner (the default
    experience). A role set with only admin roles sees "all" -- admins read
    the full list, including audience-specific rows, on the admin page.
    """
    roles = principal.roles or frozenset()
    audiences = ["all"]
    if "learner" in roles or not roles:
        audiences.append("learner")
    if "trainer" in roles:
        audiences.append("trainer")
    return audiences


@feed_router.get("/feed", response_model=HomeFeedResponse)
def get_home_feed(
    player_id: str,
    principal: BoundPrincipal = Depends(require_permission_dependency(Permission.HOME_FEED_READ)),
    db: Session = Depends(get_db),
) -> HomeFeedResponse:
    require_own_player(principal, player_id)
    player_or_404(db, player_id)
    now = _utcnow()

    announcement_rows = (
        db.query(Announcement)
        .filter(
            Announcement.is_published.is_(True),
            Announcement.audience.in_(_audiences_for(principal)),
            or_(Announcement.expires_at.is_(None), Announcement.expires_at > now),
        )
        .order_by(Announcement.published_at.desc(), Announcement.created_at.desc())
        .limit(FEED_ANNOUNCEMENT_LIMIT)
        .all()
    )

    # Courses have no published_at column, so "newly added" is approximated
    # by created_at on rows that are currently is_published. A course
    # created long ago and published today will therefore not appear here.
    course_rows = (
        db.query(Course)
        .filter(
            Course.is_published.is_(True),
            Course.created_at >= now - timedelta(days=FEED_COURSE_WINDOW_DAYS),
        )
        .order_by(Course.created_at.desc())
        .limit(FEED_COURSE_LIMIT)
        .all()
    )

    # Privacy: strictly the caller's own, non-revoked certificates.
    certificate_rows = (
        db.query(Certificate)
        .filter(
            Certificate.player_id == player_id,
            Certificate.revoked.is_(False),
            Certificate.issued_at >= now - timedelta(days=FEED_ACHIEVEMENT_WINDOW_DAYS),
        )
        .order_by(Certificate.issued_at.desc())
        .limit(FEED_ACHIEVEMENT_LIMIT)
        .all()
    )

    return HomeFeedResponse(
        announcements=[
            FeedAnnouncement(
                announcement_id=row.announcement_id,
                title=row.title,
                body=row.body,
                kind=row.kind,
                audience=row.audience,
                published_at=_aware(row.published_at),
                expires_at=_aware(row.expires_at),
            )
            for row in announcement_rows
        ],
        new_courses=[
            FeedCourse(
                course_id=row.course_id,
                title=row.title,
                description=row.description or "",
                created_at=_aware(row.created_at),
            )
            for row in course_rows
        ],
        my_achievements=[
            FeedAchievement(
                certificate_id=row.certificate_id,
                title=row.title,
                course_id=row.course_id,
                issued_at=_aware(row.issued_at),
            )
            for row in certificate_rows
        ],
        generated_at=now,
    )
