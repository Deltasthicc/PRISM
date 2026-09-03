"""Boundary tests for the Package 1 dependency-security upgrade (starlette,
python-multipart, pyjwt, pypdf, python-dotenv).

These deliberately exercise the real HTTP multipart-parsing layer through
`routes/learning.py`'s `POST /learning/quiz/generate` upload endpoint, not
just `services/content_ingestion.py::extract_text()` directly -- unit-testing
the extractor alone (already covered in `test_learning_platform.py`) never
touches Starlette/python-multipart's own request-body parsing, which is
exactly the layer CVE-2024-47874 (the multipart DoS this upgrade fixes) lives
in. This is a Lane-2 dependency-contract verification, not a Lane-5 route
test -- it does not assert anything about `routes/learning.py`'s business
logic beyond "the upgraded ASGI/multipart stack still parses a real upload
correctly and still rejects a bad one cleanly," matching the existing
precedent of `test_combat_model.py`/`test_learning_platform.py` exercising
routes without owning them.
"""
from __future__ import annotations

import io

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base, get_db
from models.accuracy_history import AccuracyHistory  # noqa: F401 -- relationship target
from models.dungeon import Dungeon, Room  # noqa: F401 -- relationship target
from models.guild import Guild  # noqa: F401 -- relationship target
from models.player import Player
from models.question import Question  # noqa: F401 -- relationship target
from models.session import GameSession  # noqa: F401 -- relationship target
from models.submission import AnswerSubmission  # noqa: F401 -- relationship target
import routes.learning as learning_routes
from services.content_ingestion import MAX_UPLOAD_BYTES

PLAYER_ID = "dep-upgrade-test-player"


@pytest.fixture
def client(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(learning_routes.router)
    app.dependency_overrides[get_db] = override_get_db

    # No live Gemini/API-key call -- this is about multipart/ASGI parsing,
    # not quiz-generation quality. Real generate_quiz() already has its own
    # deterministic-fallback coverage in test_learning_platform.py.
    async def fake_generate_quiz(text, question_count, difficulty, language):
        return (
            [
                {
                    "question": "q",
                    "options": ["a", "b", "c", "d"],
                    "answer_index": 0,
                    "explanation": "test explanation",
                    "source_excerpt": text[:50],
                    "competency": "test-competency",
                    "bloom_level": "understand",
                }
                for _ in range(question_count)
            ],
            "extractive-fallback",
        )

    monkeypatch.setattr(learning_routes, "generate_quiz", fake_generate_quiz)

    with TestingSessionLocal() as db:
        db.add(Player(player_id=PLAYER_ID, username="dep_upgrade_tester"))
        db.commit()

    with TestClient(app) as test_client:
        yield test_client


def _form_fields() -> dict:
    return {
        "player_id": PLAYER_ID,
        "title": "Dependency upgrade smoke quiz",
        "difficulty": "mixed",
        "language": "English",
        "question_count": "3",
    }


def test_real_multipart_upload_still_succeeds_end_to_end(client):
    """A genuine multipart/form-data request, parsed by the upgraded
    starlette/python-multipart stack, must still reach the route and produce
    a normal response -- proving the security upgrade didn't silently break
    the one real upload path in this codebase."""
    body = b"This is a perfectly ordinary piece of study material. " * 20
    response = client.post(
        "/learning/quiz/generate",
        data=_form_fields(),
        files={"file": ("notes.txt", io.BytesIO(body), "text/plain")},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["generation_mode"] == "extractive-fallback"
    assert len(payload["questions"]) == 3


def test_oversized_multipart_body_is_rejected_cleanly_not_a_crash(client):
    """The exact CVE-2024-47874 shape: an oversized multipart body must be
    rejected with a clean HTTP error, not hang, not 500, not silently
    truncate-and-accept. `content.read(MAX_UPLOAD_BYTES + 1)` plus
    extract_text()'s own size check together enforce this; this test proves
    it still holds through the real ASGI multipart parser, not just at the
    Python-level read() call."""
    oversized_body = b"A" * (MAX_UPLOAD_BYTES + 1024)
    response = client.post(
        "/learning/quiz/generate",
        data=_form_fields(),
        files={"file": ("huge.txt", io.BytesIO(oversized_body), "text/plain")},
    )
    assert response.status_code == 422
    assert "large" in response.json()["detail"].lower() or "exceed" in response.json()["detail"].lower()


def test_malformed_multipart_content_type_is_rejected_not_a_server_error(client):
    """A request that claims multipart/form-data but has no boundary at all
    (a classic malformed-multipart shape) must be handled as a client error
    by the upgraded parser, not surfaced as an unhandled 500."""
    response = client.post(
        "/learning/quiz/generate",
        content=b"garbage-not-a-real-multipart-body",
        headers={"content-type": "multipart/form-data"},  # no boundary=...
    )
    assert response.status_code < 500, response.text


def test_missing_file_field_still_produces_a_clean_validation_error(client):
    """A well-formed multipart body that simply omits the required file part
    must still resolve to FastAPI's normal 422 validation response under the
    upgraded stack, not an unhandled exception."""
    response = client.post("/learning/quiz/generate", data=_form_fields())
    assert response.status_code == 422
