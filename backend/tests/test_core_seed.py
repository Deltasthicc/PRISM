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
from models.governance import RoleTarget
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


def test_seed_role_targets_populates_every_override_row(seeded_session_factory):
    """Regression guard for the exact gap this seeder closes: without it,
    services/role_target_resolver.py (what every real HTTP route calls) never
    finds a match and every learner silently gets curriculum-default targets
    regardless of designation/job_role/department/current_assignment, even
    though services/role_targets.py's ROLE_TARGET_OVERRIDES and the whole
    precedence policy are fully implemented."""
    from services.role_targets import ROLE_TARGET_OVERRIDES

    seed_module.seed_role_targets()

    session = seeded_session_factory()
    rows = session.query(RoleTarget).all()
    expected_count = sum(len(targets) for targets in ROLE_TARGET_OVERRIDES.values())
    assert len(rows) == expected_count

    by_key = {(row.role, row.competency_id): row for row in rows}
    for role, targets in ROLE_TARGET_OVERRIDES.items():
        for competency_id, target_level in targets.items():
            row = by_key[(role, competency_id)]
            assert row.target_level == target_level
            assert row.source == "internal-prototype"
            assert row.approved_by is None
    session.close()


def test_seed_role_targets_is_idempotent_on_rerun(seeded_session_factory):
    seed_module.seed_role_targets()
    seed_module.seed_role_targets()

    session = seeded_session_factory()
    rows = session.query(RoleTarget).all()
    keys = [(row.role, row.competency_id) for row in rows]
    assert len(keys) == len(set(keys))  # no duplicate rows from the second run
    session.close()


def test_role_target_resolver_finds_seeded_rows_for_a_real_designation(seeded_session_factory):
    """End-to-end: the DB-backed resolver (the path every real route calls)
    must actually find what this seeder writes -- not just "a row exists,"
    but the exact resolver a learner's profile flows through in production."""
    from services.role_target_resolver import resolve_role_targets

    seed_module.seed_role_targets()

    session = seeded_session_factory()
    targets = resolve_role_targets(session, "official-statistics", job_role="Statistical Officer")
    assert targets["os_statistical_foundations"]["target_level"] == 4.0
    assert targets["os_statistical_foundations"]["source"] == "internal-prototype"
    assert targets["os_statistical_foundations"]["matched_field"] == "job_role"
    # A competency with no override for this role still gets a complete map
    # entry, just via the curriculum-default fallback.
    assert targets["os_visualization"]["source"] == "curriculum-default"
    session.close()
