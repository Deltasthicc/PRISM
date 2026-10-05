"""HTTP + storage contract for the trainer content library
(routes/content_library.py, services/content_storage.py; SIH26075 PS75-10).

Uploaded files are untrusted input, so most of this file is negative testing:
oversize, wrong type, type/content mismatch, hostile filenames, ownership
probes, visibility rules and header hardening on download.

Follows test_cohorts.py's isolated-app + in-memory-SQLite +
require_principal-override pattern. Each test points CONTENT_LIBRARY_DIR at
its own tmp directory so no test touches the real storage directory.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import re
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base, get_db
from models.player import Player
from models.enums import DEFAULT_LEARNING_MODE  # noqa: F401
from models.accuracy_history import AccuracyHistory  # noqa: F401
from models.question import Question  # noqa: F401
from models.submission import AnswerSubmission  # noqa: F401
from models.guild import Guild  # noqa: F401
from models.dungeon import Dungeon, Room  # noqa: F401
from models.session import GameSession  # noqa: F401
from models.learning import LearnerProfile, CompetencyAssessment, LearningMaterial, GeneratedQuiz  # noqa: F401
from models.governance import EvidenceRecord, RoleTarget, SourceVersion, AuditEvent  # noqa: F401
from models.identity import IdentityBinding  # noqa: F401
from models.question_bank import QuestionBankItem, QuestionBankAttempt  # noqa: F401
from models.dsa_submission import DsaSubmission  # noqa: F401
from models.course import Course
from models.course_enrollment import CourseEnrollment
from models.certificate import Certificate  # noqa: F401
from models.feedback import CourseFeedback  # noqa: F401
from models.cohort import Cohort, CohortMembership  # noqa: F401
from models.content_library import ContentItem
from routes.authorization import require_principal
from routes.content_library import router as library_router
from security.rbac import BoundPrincipal, Permission, ROLE_PERMISSIONS
from services import content_storage

PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF\n"


class _Subject:
    def __init__(self, subject_id: str, roles: frozenset[str]):
        self.issuer = "https://issuer.example/realm"
        self.subject_id = subject_id
        self.roles = roles


def _principal(player_id: str | None, roles: frozenset[str]) -> BoundPrincipal:
    return BoundPrincipal(
        subject=_Subject(player_id or "no-player", roles),
        binding_id="binding-1",
        player_id=player_id,
        roles=roles,
    )


TRAINER = frozenset({"trainer"})
LEARNER = frozenset({"learner"})


def _db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _app(db, principal: BoundPrincipal | None) -> FastAPI:
    app = FastAPI()
    app.include_router(library_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    if principal is not None:
        app.dependency_overrides[require_principal] = lambda: principal
    return app


def _client(db, player_id: str, roles: frozenset[str]) -> TestClient:
    return TestClient(_app(db, _principal(player_id, roles)))


def _make_player(db, prefix: str = "player") -> str:
    player_id = str(uuid.uuid4())
    db.add(Player(player_id=player_id, username=f"{prefix}-{player_id[:8]}"))
    db.commit()
    return player_id


def _make_course(db, trainer_id: str, *, published: bool = True) -> str:
    course = Course(
        trainer_id=trainer_id,
        title="Cyclone basics",
        description="",
        competency_id="cyclone_response",
        is_published=published,
    )
    db.add(course)
    db.commit()
    return course.course_id


def _enroll(db, player_id: str, course_id: str) -> None:
    db.add(
        CourseEnrollment(
            player_id=player_id,
            course_id=f"internal::{course_id}",
            provider="internal",
            competency_id="cyclone_response",
            title="Cyclone basics",
            status="enrolled",
        )
    )
    db.commit()


@pytest.fixture
def storage(tmp_path, monkeypatch):
    directory = tmp_path / "library"
    monkeypatch.setenv("CONTENT_LIBRARY_DIR", str(directory))
    monkeypatch.delenv("CONTENT_LIBRARY_MAX_BYTES", raising=False)
    return directory


def _files_on_disk(directory) -> list[str]:
    return sorted(p.name for p in directory.iterdir()) if directory.exists() else []


def _upload(
    client,
    trainer_id,
    *,
    filename="notes.pdf",
    content=PDF,
    content_type="application/pdf",
    title="Lecture 1",
    kind="study_material",
    description="",
    course_id=None,
):
    data = {"trainer_id": trainer_id, "title": title, "kind": kind, "description": description}
    if course_id is not None:
        data["course_id"] = course_id
    return client.post(
        "/learning/library/items",
        data=data,
        files={"file": (filename, content, content_type)},
    )


def _ooxml(prefix: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr(f"{prefix}document.xml", "<x/>")
    return buffer.getvalue()


SAMPLES = {
    "pdf": PDF,
    "pptx": _ooxml("ppt/"),
    "docx": _ooxml("word/"),
    "txt": "plain notes \u0939\u093f\u0928\u094d\u0926\u0940\n".encode(),
    "md": b"# Heading\n\ntext\n",
    "mp4": b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64,
    "webm": b"\x1a\x45\xdf\xa3" + b"\x00" * 64,
    "mp3": b"ID3\x03\x00\x00\x00\x00\x00\x00" + b"\x00" * 64,
}


# --------------------------------------------------------------- upload


def test_upload_happy_path_writes_file_and_unpublished_row(storage):
    db = _db()
    trainer = _make_player(db, "trainer")
    client = _client(db, trainer, TRAINER)

    response = _upload(client, trainer, description="  week one  ")

    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {
        "content_id", "trainer_id", "title", "description", "kind", "course_id",
        "course_title", "original_filename", "media_type", "size_bytes", "sha256",
        "is_published", "created_at", "updated_at",
    }  # no stored_name / disk path leaks
    assert body["is_published"] is False
    assert body["trainer_id"] == trainer
    assert body["description"] == "week one"
    assert body["media_type"] == "application/pdf"
    assert body["size_bytes"] == len(PDF)
    assert body["sha256"] == hashlib.sha256(PDF).hexdigest()

    row = db.query(ContentItem).one()
    names = _files_on_disk(storage)
    assert names == [row.stored_name]
    assert re.fullmatch(r"[0-9a-f]{32}\.pdf", row.stored_name)
    assert (storage / row.stored_name).read_bytes() == PDF


@pytest.mark.parametrize("extension", sorted(SAMPLES))
def test_every_allowed_type_is_accepted_with_server_side_media_type(storage, extension):
    db = _db()
    trainer = _make_player(db, "trainer")
    client = _client(db, trainer, TRAINER)

    response = _upload(
        client, trainer, filename=f"file.{extension}", content=SAMPLES[extension],
        content_type="application/x-attacker-chosen",
    )

    assert response.status_code == 200, response.text
    assert response.json()["media_type"] == content_storage.media_type_for(extension)
    assert response.json()["media_type"] != "application/x-attacker-chosen"


def test_learner_cannot_upload(storage):
    db = _db()
    learner = _make_player(db, "learner")
    client = _client(db, learner, LEARNER)

    response = _upload(client, learner)

    assert response.status_code == 403
    assert _files_on_disk(storage) == []
    assert db.query(ContentItem).count() == 0


def test_trainer_cannot_upload_as_someone_else(storage):
    db = _db()
    trainer = _make_player(db, "trainer")
    other = _make_player(db, "other")
    client = _client(db, trainer, TRAINER)

    response = _upload(client, other)

    assert response.status_code == 403
    assert _files_on_disk(storage) == []


def test_oversize_upload_is_413_and_leaves_no_file_or_row(storage, monkeypatch):
    monkeypatch.setenv("CONTENT_LIBRARY_MAX_BYTES", "2048")
    db = _db()
    trainer = _make_player(db, "trainer")
    client = _client(db, trainer, TRAINER)

    too_big = PDF + b"x" * 4096
    response = _upload(client, trainer, content=too_big)

    assert response.status_code == 413
    assert _files_on_disk(storage) == []
    assert db.query(ContentItem).count() == 0

    exactly_at_cap = PDF + b"x" * (2048 - len(PDF))
    assert _upload(client, trainer, content=exactly_at_cap).status_code == 200


@pytest.mark.parametrize(
    "filename",
    ["malware.exe", "page.html", "image.svg", "script.js", "archive.zip", "noextension", "pdf", ".pdf.", "a.pdf.exe"],
)
def test_disallowed_extension_is_415(storage, filename):
    db = _db()
    trainer = _make_player(db, "trainer")
    client = _client(db, trainer, TRAINER)

    response = _upload(client, trainer, filename=filename)

    assert response.status_code == 415
    assert _files_on_disk(storage) == []
    assert db.query(ContentItem).count() == 0


@pytest.mark.parametrize(
    ("filename", "content"),
    [
        ("fake.pdf", b"<html><script>alert(1)</script></html>"),
        ("fake.pptx", b"%PDF-1.4 not a zip"),
        ("fake.docx", _ooxml("ppt/")),  # a zip, but a presentation
        ("fake.pptx", b"PK\x03\x04" + b"\x00" * 50),  # zip magic, broken archive
        ("fake.txt", b"text\x00with a NUL"),
        ("fake.md", b"\xff\xfe\xfa not utf-8"),
        ("fake.mp4", b"MZ\x90\x00 an executable"),
        ("fake.webm", PDF),
        ("fake.mp3", b"<html></html>"),
    ],
)
def test_extension_content_mismatch_is_rejected_without_leftovers(storage, filename, content):
    db = _db()
    trainer = _make_player(db, "trainer")
    client = _client(db, trainer, TRAINER)

    response = _upload(client, trainer, filename=filename, content=content)

    assert response.status_code == 415, response.text
    assert _files_on_disk(storage) == []
    assert db.query(ContentItem).count() == 0


def test_empty_file_is_422(storage):
    db = _db()
    trainer = _make_player(db, "trainer")
    client = _client(db, trainer, TRAINER)

    response = _upload(client, trainer, content=b"")

    assert response.status_code == 422
    assert _files_on_disk(storage) == []


@pytest.mark.parametrize(
    "hostile",
    [
        "../../../etc/passwd.pdf",
        "..\\..\\windows\\system32\\evil.pdf",
        "/absolute/path/evil.pdf",
        "C:\\temp\\evil.pdf",
        "report\u202e.pdf",  # right-to-left override
        "caf\u00e9 \u0939\u093f\u0928\u094d\u0926\u0940 \u2603.pdf",
        "..pdf",
        "a" * 400 + ".pdf",
    ],
)
def test_hostile_filenames_are_sanitized_and_never_touch_disk_paths(storage, tmp_path, hostile):
    db = _db()
    trainer = _make_player(db, "trainer")
    client = _client(db, trainer, TRAINER)

    response = _upload(client, trainer, filename=hostile)

    if response.status_code != 200:
        # e.g. "..pdf" has no real extension; refusing is also safe.
        assert response.status_code == 415
        assert _files_on_disk(storage) == []
        return
    shown = response.json()["original_filename"]
    assert "/" not in shown and "\\" not in shown and "\x00" not in shown
    assert "\u202e" not in shown
    assert len(shown) <= 120
    assert shown.endswith(".pdf")
    # Exactly one file, with a server-generated name, inside the storage dir
    # -- and nothing was written anywhere else under tmp_path.
    assert len(_files_on_disk(storage)) == 1
    assert re.fullmatch(r"[0-9a-f]{32}\.pdf", _files_on_disk(storage)[0])
    outside = [p for p in tmp_path.rglob("*") if p.is_file() and storage not in p.parents]
    assert outside == []


def test_sanitize_display_name_strips_nul_crlf_quotes_and_directories():
    clean = content_storage.sanitize_display_name('a\x00b\r\nSet-Cookie: x"; y.pdf')
    assert "\x00" not in clean and "\r" not in clean and "\n" not in clean
    assert '"' not in clean and ";" not in clean
    assert content_storage.sanitize_display_name("..\\..\\x/y/z.pdf") == "z.pdf"
    assert content_storage.sanitize_display_name("") == "upload"
    assert content_storage.sanitize_display_name(None) == "upload"
    assert content_storage.sanitize_display_name("\x00\x00") == "upload"


def test_resolve_stored_path_rejects_anything_not_server_generated(storage):
    good = f"{uuid.uuid4().hex}.pdf"
    assert content_storage.resolve_stored_path(good) == (storage.resolve() / good)
    for bad in ["../x.pdf", "..\\x.pdf", "/etc/passwd", "x.pdf", f"{uuid.uuid4().hex}.pdf/../../x", "", f"{uuid.uuid4().hex}.exe/"]:
        assert content_storage.resolve_stored_path(bad) is None


def test_invalid_form_values_are_422(storage):
    db = _db()
    trainer = _make_player(db, "trainer")
    client = _client(db, trainer, TRAINER)

    assert _upload(client, trainer, kind="video").status_code == 422
    assert _upload(client, trainer, title="   ").status_code == 422
    assert _upload(client, trainer, title="t" * 201).status_code == 422
    assert _upload(client, trainer, description="d" * 2001).status_code == 422
    assert _files_on_disk(storage) == []


def test_upload_linked_to_another_trainers_or_missing_course_is_404(storage):
    db = _db()
    trainer = _make_player(db, "trainer")
    other = _make_player(db, "other")
    foreign_course = _make_course(db, other)
    client = _client(db, trainer, TRAINER)

    assert _upload(client, trainer, course_id=foreign_course).status_code == 404
    assert _upload(client, trainer, course_id=str(uuid.uuid4())).status_code == 404
    assert _files_on_disk(storage) == []
    assert db.query(ContentItem).count() == 0

    own_course = _make_course(db, trainer)
    linked = _upload(client, trainer, course_id=own_course)
    assert linked.status_code == 200
    assert linked.json()["course_id"] == own_course
    assert linked.json()["course_title"] == "Cyclone basics"


def test_concurrent_same_title_uploads_all_succeed_with_distinct_files(storage, tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'concurrent.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    seed = factory()
    trainer = _make_player(seed, "trainer")
    seed.close()

    app = FastAPI()
    app.include_router(library_router)

    def override_db():
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_principal] = lambda: _principal(trainer, TRAINER)
    client = TestClient(app)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: _upload(client, trainer, title="Same title"), range(4)))

    assert [r.status_code for r in results] == [200] * 4, [r.text for r in results]
    assert len({r.json()["content_id"] for r in results}) == 4
    verify = factory()
    stored = {row.stored_name for row in verify.query(ContentItem).all()}
    assert len(stored) == 4
    assert set(_files_on_disk(storage)) == stored
    verify.close()


# --------------------------------------------------------------- ownership


def test_mine_lists_only_own_items_including_drafts(storage):
    db = _db()
    trainer = _make_player(db, "trainer")
    other = _make_player(db, "other")
    mine = _client(db, trainer, TRAINER)
    theirs = _client(db, other, TRAINER)
    own_id = _upload(mine, trainer, title="Mine").json()["content_id"]
    _upload(theirs, other, title="Theirs")

    listed = mine.get("/learning/library/items/mine", params={"trainer_id": trainer})

    assert listed.status_code == 200
    assert [i["content_id"] for i in listed.json()] == [own_id]
    assert listed.json()[0]["is_published"] is False
    assert mine.get("/learning/library/items/mine", params={"trainer_id": other}).status_code == 403


def test_other_trainers_item_is_404_on_publish_unpublish_delete_and_download(storage):
    db = _db()
    owner = _make_player(db, "owner")
    intruder = _make_player(db, "intruder")
    content_id = _upload(_client(db, owner, TRAINER), owner).json()["content_id"]
    attacker = _client(db, intruder, TRAINER)
    missing = str(uuid.uuid4())

    for target in (content_id, missing):
        publish = attacker.post(f"/learning/library/items/{target}/publish", json={"trainer_id": intruder})
        unpublish = attacker.post(f"/learning/library/items/{target}/unpublish", json={"trainer_id": intruder})
        delete = attacker.delete(f"/learning/library/items/{target}", params={"trainer_id": intruder})
        download = attacker.get(f"/learning/library/items/{target}/download", params={"player_id": intruder})
        assert (publish.status_code, unpublish.status_code, delete.status_code, download.status_code) == (404, 404, 404, 404)
        # Existing-but-foreign is byte-identical to non-existent.
    a = attacker.post(f"/learning/library/items/{content_id}/publish", json={"trainer_id": intruder})
    b = attacker.post(f"/learning/library/items/{missing}/publish", json={"trainer_id": intruder})
    assert a.json() == b.json()

    row = db.query(ContentItem).one()
    assert row.is_published is False
    assert (storage / row.stored_name).exists()
    # Claiming to be the owner is a 403, not a way in.
    assert attacker.post(
        f"/learning/library/items/{content_id}/publish", json={"trainer_id": owner}
    ).status_code == 403


def test_publish_and_unpublish_by_owner(storage):
    db = _db()
    trainer = _make_player(db, "trainer")
    client = _client(db, trainer, TRAINER)
    content_id = _upload(client, trainer).json()["content_id"]

    published = client.post(f"/learning/library/items/{content_id}/publish", json={"trainer_id": trainer})
    assert published.status_code == 200 and published.json()["is_published"] is True
    unpublished = client.post(f"/learning/library/items/{content_id}/unpublish", json={"trainer_id": trainer})
    assert unpublished.status_code == 200 and unpublished.json()["is_published"] is False


# --------------------------------------------------------------- visibility


def test_draft_is_invisible_to_trainees_until_published(storage):
    db = _db()
    trainer = _make_player(db, "trainer")
    trainee = _make_player(db, "trainee")
    t_client = _client(db, trainer, TRAINER)
    l_client = _client(db, trainee, LEARNER)
    content_id = _upload(t_client, trainer).json()["content_id"]

    assert l_client.get("/learning/library/items", params={"player_id": trainee}).json() == []
    assert l_client.get(
        f"/learning/library/items/{content_id}/download", params={"player_id": trainee}
    ).status_code == 404

    t_client.post(f"/learning/library/items/{content_id}/publish", json={"trainer_id": trainer})

    listed = l_client.get("/learning/library/items", params={"player_id": trainee}).json()
    assert [i["content_id"] for i in listed] == [content_id]
    assert l_client.get(
        f"/learning/library/items/{content_id}/download", params={"player_id": trainee}
    ).status_code == 200

    t_client.post(f"/learning/library/items/{content_id}/unpublish", json={"trainer_id": trainer})
    assert l_client.get("/learning/library/items", params={"player_id": trainee}).json() == []


def test_course_linked_item_needs_enrollment(storage):
    db = _db()
    trainer = _make_player(db, "trainer")
    trainee = _make_player(db, "trainee")
    course = _make_course(db, trainer)
    other_course = _make_course(db, trainer)
    t_client = _client(db, trainer, TRAINER)
    l_client = _client(db, trainee, LEARNER)
    content_id = _upload(t_client, trainer, course_id=course).json()["content_id"]
    t_client.post(f"/learning/library/items/{content_id}/publish", json={"trainer_id": trainer})
    download = lambda: l_client.get(  # noqa: E731
        f"/learning/library/items/{content_id}/download", params={"player_id": trainee}
    )

    assert l_client.get("/learning/library/items", params={"player_id": trainee}).json() == []
    assert download().status_code == 404

    _enroll(db, trainee, other_course)  # wrong course does not help
    assert l_client.get("/learning/library/items", params={"player_id": trainee}).json() == []
    assert download().status_code == 404

    _enroll(db, trainee, course)
    listed = l_client.get("/learning/library/items", params={"player_id": trainee}).json()
    assert [i["content_id"] for i in listed] == [content_id]
    assert download().status_code == 200


def test_unlinked_published_item_is_visible_to_any_trainee(storage):
    db = _db()
    trainer = _make_player(db, "trainer")
    trainee = _make_player(db, "trainee")
    t_client = _client(db, trainer, TRAINER)
    content_id = _upload(t_client, trainer).json()["content_id"]
    t_client.post(f"/learning/library/items/{content_id}/publish", json={"trainer_id": trainer})

    listed = _client(db, trainee, LEARNER).get("/learning/library/items", params={"player_id": trainee})
    assert [i["content_id"] for i in listed.json()] == [content_id]


def test_trainee_cannot_read_as_another_player(storage):
    db = _db()
    trainee = _make_player(db, "trainee")
    victim = _make_player(db, "victim")
    client = _client(db, trainee, LEARNER)

    assert client.get("/learning/library/items", params={"player_id": victim}).status_code == 403
    assert client.get(
        f"/learning/library/items/{uuid.uuid4()}/download", params={"player_id": victim}
    ).status_code == 403


def test_learner_cannot_manage_and_auditor_cannot_read(storage):
    db = _db()
    trainer = _make_player(db, "trainer")
    learner = _make_player(db, "learner")
    auditor = _make_player(db, "auditor")
    content_id = _upload(_client(db, trainer, TRAINER), trainer).json()["content_id"]
    l_client = _client(db, learner, LEARNER)

    assert l_client.get("/learning/library/items/mine", params={"trainer_id": learner}).status_code == 403
    assert l_client.post(
        f"/learning/library/items/{content_id}/publish", json={"trainer_id": learner}
    ).status_code == 403
    assert l_client.delete(
        f"/learning/library/items/{content_id}", params={"trainer_id": learner}
    ).status_code == 403
    assert _client(db, auditor, frozenset({"auditor"})).get(
        "/learning/library/items", params={"player_id": auditor}
    ).status_code == 403


def test_role_permissions_for_content_library():
    assert Permission.CONTENT_LIBRARY_READ in ROLE_PERMISSIONS["learner"]
    assert Permission.CONTENT_LIBRARY_WRITE not in ROLE_PERMISSIONS["learner"]
    for role in ("trainer", "organization_admin"):
        assert Permission.CONTENT_LIBRARY_READ in ROLE_PERMISSIONS[role]
        assert Permission.CONTENT_LIBRARY_WRITE in ROLE_PERMISSIONS[role]
    assert Permission.CONTENT_LIBRARY_WRITE not in ROLE_PERMISSIONS["auditor"]


# --------------------------------------------------------------- download


def test_download_is_attachment_nosniff_with_allowlisted_type(storage):
    db = _db()
    trainer = _make_player(db, "trainer")
    t_client = _client(db, trainer, TRAINER)
    # The client claims text/html; the server must ignore it.
    content_id = _upload(t_client, trainer, content_type="text/html").json()["content_id"]

    response = t_client.get(
        f"/learning/library/items/{content_id}/download", params={"player_id": trainer}
    )  # the owner can fetch their own draft

    assert response.status_code == 200
    assert response.content == PDF
    assert response.headers["content-disposition"].startswith("attachment")
    assert "notes.pdf" in response.headers["content-disposition"]
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-type"] == "application/pdf"
    assert "sandbox" in response.headers["content-security-policy"]
    assert "no-store" in response.headers["cache-control"]


def test_download_filename_cannot_inject_headers(storage):
    db = _db()
    trainer = _make_player(db, "trainer")
    client = _client(db, trainer, TRAINER)
    content_id = _upload(client, trainer, filename='evil"; filename=x.html\r\nX-Injected: 1.pdf').json()["content_id"]

    response = client.get(
        f"/learning/library/items/{content_id}/download", params={"player_id": trainer}
    )

    assert response.status_code == 200
    assert "x-injected" not in response.headers
    assert response.headers["content-disposition"].startswith("attachment")


def test_download_refuses_a_file_whose_size_changed_on_disk(storage):
    db = _db()
    trainer = _make_player(db, "trainer")
    client = _client(db, trainer, TRAINER)
    content_id = _upload(client, trainer).json()["content_id"]
    row = db.query(ContentItem).one()
    (storage / row.stored_name).write_bytes(PDF + b"tampered")

    response = client.get(f"/learning/library/items/{content_id}/download", params={"player_id": trainer})

    assert response.status_code == 500
    assert "tampered" not in response.text


def test_download_of_missing_file_is_404_without_path_leak(storage):
    db = _db()
    trainer = _make_player(db, "trainer")
    client = _client(db, trainer, TRAINER)
    content_id = _upload(client, trainer).json()["content_id"]
    row = db.query(ContentItem).one()
    (storage / row.stored_name).unlink()

    response = client.get(f"/learning/library/items/{content_id}/download", params={"player_id": trainer})

    assert response.status_code == 404
    assert str(storage) not in response.text


def test_corrupted_stored_name_cannot_escape_the_storage_directory(storage, tmp_path):
    db = _db()
    trainer = _make_player(db, "trainer")
    client = _client(db, trainer, TRAINER)
    content_id = _upload(client, trainer).json()["content_id"]
    secret = tmp_path / "secret.pdf"
    secret.write_bytes(b"%PDF-1.4 secret")
    row = db.query(ContentItem).one()
    row.stored_name = "../secret.pdf"
    db.commit()

    response = client.get(f"/learning/library/items/{content_id}/download", params={"player_id": trainer})

    assert response.status_code == 404
    assert b"secret" not in response.content


# --------------------------------------------------------------- delete


def test_delete_removes_row_and_file(storage):
    db = _db()
    trainer = _make_player(db, "trainer")
    client = _client(db, trainer, TRAINER)
    content_id = _upload(client, trainer).json()["content_id"]
    assert len(_files_on_disk(storage)) == 1

    response = client.delete(f"/learning/library/items/{content_id}", params={"trainer_id": trainer})

    assert response.status_code == 204
    assert db.query(ContentItem).count() == 0
    assert _files_on_disk(storage) == []
    assert client.delete(
        f"/learning/library/items/{content_id}", params={"trainer_id": trainer}
    ).status_code == 404


def test_delete_keeps_row_when_file_removal_fails(storage, monkeypatch):
    db = _db()
    trainer = _make_player(db, "trainer")
    client = _client(db, trainer, TRAINER)
    content_id = _upload(client, trainer).json()["content_id"]

    def boom(stored_name):
        raise PermissionError("denied: /secret/server/path")

    monkeypatch.setattr(content_storage, "delete_stored_file", boom)
    response = client.delete(f"/learning/library/items/{content_id}", params={"trainer_id": trainer})

    assert response.status_code == 500
    assert "/secret/server/path" not in response.text
    assert db.query(ContentItem).count() == 1
    assert len(_files_on_disk(storage)) == 1


def test_delete_succeeds_when_file_is_already_gone(storage):
    db = _db()
    trainer = _make_player(db, "trainer")
    client = _client(db, trainer, TRAINER)
    content_id = _upload(client, trainer).json()["content_id"]
    (storage / db.query(ContentItem).one().stored_name).unlink()

    response = client.delete(f"/learning/library/items/{content_id}", params={"trainer_id": trainer})

    assert response.status_code == 204
    assert db.query(ContentItem).count() == 0


# --------------------------------------------------------------- middleware


def _run_asgi(app, *, headers, path="/learning/library/items", method="POST", body=b""):
    sent = []

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "method": method, "path": path, "headers": headers}
    asyncio.run(app(scope, receive, send))
    return sent


def test_body_limit_middleware_rejects_before_the_app_runs(monkeypatch):
    monkeypatch.setenv("CONTENT_LIBRARY_MAX_BYTES", "1000")
    reached = []

    async def inner(scope, receive, send):
        reached.append(True)

    app = content_storage.UploadBodyLimitMiddleware(inner)
    limit = 1000 + content_storage.MULTIPART_OVERHEAD_BYTES

    too_big = _run_asgi(app, headers=[(b"content-length", str(limit + 1).encode())])
    assert too_big[0]["status"] == 413
    no_length = _run_asgi(app, headers=[])
    assert no_length[0]["status"] == 411
    garbage = _run_asgi(app, headers=[(b"content-length", b"abc")])
    assert garbage[0]["status"] == 411
    assert reached == []

    _run_asgi(app, headers=[(b"content-length", str(limit).encode())])
    _run_asgi(app, headers=[], method="GET")  # other methods untouched
    _run_asgi(app, headers=[], path="/learning/courses")  # other paths untouched
    assert reached == [True, True, True]


def test_real_app_rejects_oversize_request_via_middleware(storage, monkeypatch):
    monkeypatch.setenv("CONTENT_LIBRARY_MAX_BYTES", "1000")
    db = _db()
    trainer = _make_player(db, "trainer")
    app = content_storage.UploadBodyLimitMiddleware(_app(db, _principal(trainer, TRAINER)))
    client = TestClient(app)

    response = _upload(client, trainer, content=PDF + b"x" * (2 * 1024 * 1024))

    assert response.status_code == 413
    assert db.query(ContentItem).count() == 0
    assert _files_on_disk(storage) == []
