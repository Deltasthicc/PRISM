"""Smoke tests for db/seed.py's structural invariants -- does the demo-data
bootstrap actually run and produce the shape other code depends on
(exactly one DSA dungeon, idempotent on rerun, one dungeon per non-DSA
curriculum). This deliberately does not assert on Lane 3-owned content
(exact topic names, competency counts, HP numbers) -- those are
services/curricula.py's and services/knowledge_graph.py's own concerns,
not something Lane 2's seeding script should be pinned to.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import db.seed as seed_module
from db.database import Base
from models.accuracy_history import AccuracyHistory  # noqa: F401 -- relationship target
from models.dungeon import Dungeon, Room
from models.guild import Guild  # noqa: F401 -- relationship target
from models.player import Player
from models.question import Question  # noqa: F401 -- relationship target
from models.session import GameSession  # noqa: F401 -- relationship target
from models.submission import AnswerSubmission  # noqa: F401 -- relationship target


@pytest.fixture
def seeded_session_factory(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    monkeypatch.setattr(seed_module, "SessionLocal", session_factory)
    yield session_factory
    engine.dispose()


def test_seed_database_creates_exactly_one_dsa_dungeon_with_a_boss_room(seeded_session_factory):
    seed_module.seed_database()

    session = seeded_session_factory()
    dungeons = session.query(Dungeon).filter(Dungeon.name == "DSA Fundamentals").all()
    assert len(dungeons) == 1

    rooms = session.query(Room).filter(Room.dungeon_id == dungeons[0].dungeon_id).all()
    assert any(room.is_boss for room in rooms)
    assert any(not room.is_boss for room in rooms)
    session.close()


def test_seed_database_creates_a_demo_player(seeded_session_factory):
    seed_module.seed_database()

    session = seeded_session_factory()
    assert session.query(Player).count() >= 1
    session.close()


def test_seed_database_is_idempotent_on_rerun(seeded_session_factory):
    """The demo app restarts against the same SQLite file constantly during
    local development -- a bug that duplicated the dungeon on every restart
    would be immediately, obviously wrong, but only if something actually
    asserts it stays a singleton."""
    seed_module.seed_database()
    seed_module.seed_database()

    session = seeded_session_factory()
    dungeons = session.query(Dungeon).filter(Dungeon.name == "DSA Fundamentals").all()
    assert len(dungeons) == 1
    session.close()


def test_seed_curricula_dungeons_creates_one_dungeon_per_non_dsa_curriculum(seeded_session_factory):
    from services.curricula import CURRICULA

    non_dsa_slugs = {slug for slug in CURRICULA if slug != "dsa-fundamentals"}
    assert non_dsa_slugs, "expected at least one non-DSA curriculum to seed against"

    seed_module.seed_curricula_dungeons()

    session = seeded_session_factory()
    seeded_slugs = {
        d.curriculum_slug for d in session.query(Dungeon).filter(Dungeon.curriculum_slug.isnot(None))
    }
    assert non_dsa_slugs <= seeded_slugs
    session.close()


def test_seed_curricula_dungeons_is_idempotent_on_rerun(seeded_session_factory):
    seed_module.seed_curricula_dungeons()
    seed_module.seed_curricula_dungeons()

    session = seeded_session_factory()
    names = [d.name for d in session.query(Dungeon).all()]
    assert len(names) == len(set(names))  # no duplicate dungeon names from the second run
    session.close()
