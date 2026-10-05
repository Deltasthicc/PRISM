"""Trainer content library (SIH26075 PS75-10).

Trainers upload recorded lectures, presentations and study materials; their
trainees download them. Uploaded files are untrusted input: every storage,
type and path-safety rule lives in `services/content_storage.py`; this file
owns identity, ownership and visibility.

Identity follows the project pattern (see routes/course_catalog.py): every
route resolves a verified principal via `require_permission_dependency`, and
acts "as" an explicit `trainer_id` / `player_id` validated with
`require_own_player` -- never `principal.player_id` directly, because the
DISABLE_AUTH demo principal has `player_id=None`.

Ownership failures return 404, never 403, so probing ids reveals nothing.

Visibility for a trainee: the item must be published AND either have no
course link or the player must hold a `CourseEnrollment` for
`internal::<course_id>`. The owner can always see and download their own
drafts. Anything else is a 404.

Download integrity check: before serving we compare the on-disk size with
`size_bytes` (a cheap stat) and refuse to serve a mismatch. We do not
re-hash on every download -- hashing up to 25 MiB per request is wasteful --
the stored `sha256` is exposed in the metadata for audit/verification.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db.database import get_db
from models.content_library import ContentItem
from models.course import Course
from models.course_enrollment import CourseEnrollment
from routes.authorization import require_own_player, require_permission_dependency
from routes.learning_common import player_or_404
from security.rbac import BoundPrincipal, Permission
from services import content_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learning/library", tags=["Content Library"])

ContentKind = Literal["recorded_lecture", "presentation", "study_material"]


class TrainerScopedRequest(BaseModel):
    trainer_id: str


class ContentItemResponse(BaseModel):
    content_id: str
    trainer_id: str
    title: str
    description: str
    kind: str
    course_id: str | None
    course_title: str | None
    original_filename: str
    media_type: str
    size_bytes: int
    sha256: str
    is_published: bool
    created_at: datetime
    updated_at: datetime


def _course_titles(db: Session, items: list[ContentItem]) -> dict[str, str]:
    ids = {item.course_id for item in items if item.course_id}
    if not ids:
        return {}
    rows = db.query(Course.course_id, Course.title).filter(Course.course_id.in_(ids)).all()
    return {course_id: title for course_id, title in rows}


def _serialize_many(db: Session, items: list[ContentItem]) -> list[ContentItemResponse]:
    titles = _course_titles(db, items)
    return [
        ContentItemResponse(
            content_id=item.content_id,
            trainer_id=item.trainer_id,
            title=item.title,
            description=item.description,
            kind=item.kind,
            course_id=item.course_id,
            course_title=titles.get(item.course_id) if item.course_id else None,
            original_filename=item.original_filename,
            media_type=item.media_type,
            size_bytes=item.size_bytes,
            sha256=item.sha256,
            is_published=item.is_published,
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
        for item in items
    ]


def _own_item_or_404(db: Session, content_id: str, trainer_id: str) -> ContentItem:
    item = db.query(ContentItem).filter(ContentItem.content_id == content_id).one_or_none()
    # Missing and not-yours are deliberately indistinguishable.
    if item is None or item.trainer_id != trainer_id:
        raise HTTPException(status_code=404, detail="Content item not found")
    return item


def _enrolled_internal_course_ids(db: Session, player_id: str) -> set[str]:
    rows = (
        db.query(CourseEnrollment.course_id)
        .filter(
            CourseEnrollment.player_id == player_id,
            CourseEnrollment.course_id.like("internal::%"),
        )
        .all()
    )
    prefix = "internal::"
    return {course_id[len(prefix):] for (course_id,) in rows}


def _visible_to_trainee(item: ContentItem, enrolled_course_ids: set[str]) -> bool:
    if not item.is_published:
        return False
    return item.course_id is None or item.course_id in enrolled_course_ids


@router.post("/items", response_model=ContentItemResponse)
def upload_item(
    trainer_id: str = Form(...),
    title: str = Form(..., min_length=1, max_length=200),
    kind: ContentKind = Form(...),
    description: str = Form("", max_length=2000),
    course_id: str | None = Form(None),
    file: UploadFile = File(...),
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.CONTENT_LIBRARY_WRITE)
    ),
    db: Session = Depends(get_db),
) -> ContentItemResponse:
    require_own_player(principal, trainer_id)
    player_or_404(db, trainer_id)

    clean_title = title.strip()
    if not clean_title:
        raise HTTPException(status_code=422, detail="Title must not be blank")

    linked_course_id = (course_id or "").strip() or None
    if linked_course_id is not None:
        owned = (
            db.query(Course.course_id)
            .filter(Course.course_id == linked_course_id, Course.trainer_id == trainer_id)
            .first()
        )
        if owned is None:
            raise HTTPException(status_code=404, detail="Course not found")

    try:
        stored = content_storage.store_upload(file.file, file.filename)
    except content_storage.StorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    item = ContentItem(
        trainer_id=trainer_id,
        title=clean_title,
        description=description.strip(),
        kind=kind,
        course_id=linked_course_id,
        original_filename=stored.original_filename,
        stored_name=stored.stored_name,
        media_type=stored.media_type,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        is_published=False,
    )
    db.add(item)
    try:
        db.commit()
    except Exception:
        # Do not leave an unreferenced file behind if the row never landed.
        db.rollback()
        try:
            content_storage.delete_stored_file(stored.stored_name)
        except content_storage.StorageError:
            logger.exception("Could not remove orphaned upload after failed commit")
        raise
    db.refresh(item)
    return _serialize_many(db, [item])[0]


@router.get("/items/mine", response_model=list[ContentItemResponse])
def list_my_items(
    trainer_id: str,
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.CONTENT_LIBRARY_WRITE)
    ),
    db: Session = Depends(get_db),
) -> list[ContentItemResponse]:
    require_own_player(principal, trainer_id)
    rows = (
        db.query(ContentItem)
        .filter(ContentItem.trainer_id == trainer_id)
        .order_by(ContentItem.created_at.desc())
        .all()
    )
    return _serialize_many(db, rows)


@router.get("/items", response_model=list[ContentItemResponse])
def list_items_for_trainee(
    player_id: str,
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.CONTENT_LIBRARY_READ)
    ),
    db: Session = Depends(get_db),
) -> list[ContentItemResponse]:
    require_own_player(principal, player_id)
    player_or_404(db, player_id)
    enrolled = _enrolled_internal_course_ids(db, player_id)
    rows = (
        db.query(ContentItem)
        .filter(ContentItem.is_published.is_(True))
        .order_by(ContentItem.created_at.desc())
        .all()
    )
    visible = [row for row in rows if _visible_to_trainee(row, enrolled)]
    return _serialize_many(db, visible)


def _set_published(
    content_id: str,
    body: TrainerScopedRequest,
    principal: BoundPrincipal,
    db: Session,
    published: bool,
) -> ContentItemResponse:
    require_own_player(principal, body.trainer_id)
    item = _own_item_or_404(db, content_id, body.trainer_id)
    item.is_published = published
    db.commit()
    db.refresh(item)
    return _serialize_many(db, [item])[0]


@router.post("/items/{content_id}/publish", response_model=ContentItemResponse)
def publish_item(
    content_id: str,
    body: TrainerScopedRequest,
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.CONTENT_LIBRARY_WRITE)
    ),
    db: Session = Depends(get_db),
) -> ContentItemResponse:
    return _set_published(content_id, body, principal, db, True)


@router.post("/items/{content_id}/unpublish", response_model=ContentItemResponse)
def unpublish_item(
    content_id: str,
    body: TrainerScopedRequest,
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.CONTENT_LIBRARY_WRITE)
    ),
    db: Session = Depends(get_db),
) -> ContentItemResponse:
    return _set_published(content_id, body, principal, db, False)


@router.delete("/items/{content_id}", status_code=204)
def delete_item(
    content_id: str,
    trainer_id: str,
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.CONTENT_LIBRARY_WRITE)
    ),
    db: Session = Depends(get_db),
) -> None:
    require_own_player(principal, trainer_id)
    item = _own_item_or_404(db, content_id, trainer_id)
    stored_name = item.stored_name
    db.delete(item)
    db.flush()
    try:
        content_storage.delete_stored_file(stored_name)
    except (content_storage.StorageError, OSError):
        # Keep the row: dropping it would orphan the bytes with no record.
        db.rollback()
        logger.exception("Could not delete stored file for content item")
        raise HTTPException(
            status_code=500, detail="Could not delete the stored file; nothing was removed"
        ) from None
    db.commit()


@router.get("/items/{content_id}/download")
def download_item(
    content_id: str,
    player_id: str,
    principal: BoundPrincipal = Depends(
        require_permission_dependency(Permission.CONTENT_LIBRARY_READ)
    ),
    db: Session = Depends(get_db),
) -> FileResponse:
    require_own_player(principal, player_id)
    item = db.query(ContentItem).filter(ContentItem.content_id == content_id).one_or_none()
    if item is None:
        raise HTTPException(status_code=404, detail="Content item not found")
    is_owner = item.trainer_id == player_id
    if not is_owner and not _visible_to_trainee(item, _enrolled_internal_course_ids(db, player_id)):
        raise HTTPException(status_code=404, detail="Content item not found")

    path = content_storage.resolve_stored_path(item.stored_name)
    try:
        on_disk = os.stat(path).st_size if path is not None else None
    except OSError:
        on_disk = None
    if path is None or on_disk is None:
        logger.error("Stored file missing for content item %s", item.content_id)
        raise HTTPException(status_code=404, detail="Content item not found")
    if on_disk != item.size_bytes:
        logger.error("Stored file size mismatch for content item %s", item.content_id)
        raise HTTPException(status_code=500, detail="Stored file failed its integrity check")

    # Never inline; media type comes from the server allowlist (stored at
    # upload), not from anything the client sent.
    return FileResponse(
        path,
        media_type=item.media_type,
        filename=item.original_filename,
        content_disposition_type="attachment",
        headers={
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "Cache-Control": "private, no-store",
        },
    )
