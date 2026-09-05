"""Tests for services/role_target_resolver.py against real RoleTarget rows.

This is the database-backed half of Lane 3's role-target policy. Lane 2 owns
the exact `(role, competency_id)` lookup and its validity window; this module
owns which role keys to try, in what order, the `"*"` fallback and the
curriculum default -- the split stated in docs/contracts/data-authorization.md
section 4.1.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base
from models.accuracy_history import AccuracyHistory  # noqa: F401 -- relationship target
from models.dungeon import Dungeon, Room  # noqa: F401 -- relationship target
from models.governance import RoleTarget
from models.guild import Guild  # noqa: F401 -- relationship target
from models.player import Player  # noqa: F401 -- relationship target
from models.question import Question  # noqa: F401 -- relationship target
from models.session import GameSession  # noqa: F401 -- relationship target
from models.submission import AnswerSubmission  # noqa: F401 -- relationship target
from services.curricula import CURRICULA
from services.learning_engine import analyse_competencies
from services.role_target_resolver import AGNOSTIC_ROLE, resolve_role_targets
from services.role_targets import PROVISIONAL, resolve_role_target

CURRICULUM = "official-statistics"
COMPETENCY = "os_official_statistics"
NOW = datetime(2026, 6, 1, tzinfo=timezone.utc)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _add(db, role, competency_id, level, **kwargs):
    db.add(RoleTarget(
        role=role, competency_id=competency_id, target_level=level,
        valid_from=kwargs.pop("valid_from", NOW - timedelta(days=30)), **kwargs,
    ))
    db.commit()


# ─── completeness and fallback ───

def test_map_covers_every_competency_even_with_no_rows(db):
    resolved = resolve_role_targets(db, CURRICULUM, as_of=NOW)
    expected = {c["id"] for c in CURRICULA[CURRICULUM]["competencies"]}
    assert set(resolved) == expected
    # With nothing stored, every entry is the curriculum's own default.
    assert all(r["source"] == "curriculum-default" for r in resolved.values())


def test_unknown_curriculum_raises(db):
    with pytest.raises(ValueError, match="Unknown curriculum"):
        resolve_role_targets(db, "not-a-curriculum", as_of=NOW)


# ─── precedence, which is Lane 3's half of the contract ───

def test_stored_role_row_beats_the_curriculum_default(db):
    _add(db, "statistical officer", COMPETENCY, 5, source="mospi-pilot")
    resolved = resolve_role_targets(db, CURRICULUM, job_role="Statistical Officer", as_of=NOW)
    assert resolved[COMPETENCY]["target_level"] == 5.0
    assert resolved[COMPETENCY]["source"] == "mospi-pilot"
    assert resolved[COMPETENCY]["matched_field"] == "job_role"


def test_more_specific_profile_field_wins(db):
    _add(db, "statistical officer", COMPETENCY, 5)
    _add(db, "statistics division", COMPETENCY, 2)
    resolved = resolve_role_targets(
        db, CURRICULUM, job_role="Statistical Officer", department="Statistics Division", as_of=NOW,
    )
    # job_role precedes department in RESOLUTION_ORDER.
    assert resolved[COMPETENCY]["target_level"] == 5.0
    assert resolved[COMPETENCY]["matched_field"] == "job_role"


def test_agnostic_row_beats_curriculum_default_but_loses_to_a_role(db):
    _add(db, AGNOSTIC_ROLE, COMPETENCY, 2)
    resolved = resolve_role_targets(db, CURRICULUM, as_of=NOW)
    assert resolved[COMPETENCY]["target_level"] == 2.0
    assert resolved[COMPETENCY]["matched_role"] == AGNOSTIC_ROLE
    assert resolved[COMPETENCY]["matched_field"] is None

    _add(db, "statistical officer", COMPETENCY, 5)
    resolved = resolve_role_targets(db, CURRICULUM, job_role="statistical officer", as_of=NOW)
    assert resolved[COMPETENCY]["target_level"] == 5.0


def test_role_keys_are_matched_case_insensitively(db):
    _add(db, "statistical officer", COMPETENCY, 5)
    resolved = resolve_role_targets(db, CURRICULUM, job_role="  STATISTICAL Officer ", as_of=NOW)
    assert resolved[COMPETENCY]["target_level"] == 5.0


# ─── validity window is Lane 2's, but the integration must honour it ───

def test_expired_row_is_not_used(db):
    _add(db, "statistical officer", COMPETENCY, 5,
         valid_from=NOW - timedelta(days=60), valid_to=NOW - timedelta(days=1))
    resolved = resolve_role_targets(db, CURRICULUM, job_role="statistical officer", as_of=NOW)
    # Falls through to the curriculum default rather than using a lapsed target.
    assert resolved[COMPETENCY]["source"] == "curriculum-default"


def test_future_row_is_not_used_yet(db):
    _add(db, "statistical officer", COMPETENCY, 5, valid_from=NOW + timedelta(days=1))
    resolved = resolve_role_targets(db, CURRICULUM, job_role="statistical officer", as_of=NOW)
    assert resolved[COMPETENCY]["source"] == "curriculum-default"


# ─── assurance is derived, never invented ───

def test_unapproved_row_is_provisional(db):
    _add(db, "statistical officer", COMPETENCY, 5, approved_by=None)
    resolved = resolve_role_targets(db, CURRICULUM, job_role="statistical officer", as_of=NOW)
    assert resolved[COMPETENCY]["assurance"] == PROVISIONAL
    assert resolved[COMPETENCY]["approved_by"] is None


def test_approved_row_carries_no_invented_assurance_term(db):
    _add(db, "statistical officer", COMPETENCY, 5, approved_by="Dr Domain Reviewer")
    resolved = resolve_role_targets(db, CURRICULUM, job_role="statistical officer", as_of=NOW)
    # The fixed vocabulary has no word for "approved", so none is invented --
    # approved_by itself carries the fact.
    assert resolved[COMPETENCY]["assurance"] is None
    assert resolved[COMPETENCY]["approved_by"] == "Dr Domain Reviewer"


# ─── shape compatibility with the in-memory path ───

def test_db_and_in_memory_paths_return_the_same_record_shape(db):
    _add(db, "statistical officer", COMPETENCY, 5)
    from_db = resolve_role_targets(db, CURRICULUM, job_role="statistical officer", as_of=NOW)[COMPETENCY]
    in_memory = resolve_role_target(COMPETENCY, 4, job_role="statistical officer")
    assert set(from_db) == set(in_memory)


# ─── end to end into the pure engine ───

def test_resolved_targets_flow_into_the_engine(db):
    _add(db, "statistical officer", COMPETENCY, 5, approved_by="Dr Domain Reviewer")
    result = analyse_competencies(
        CURRICULUM, {}, {}, "expert",
        role_targets=resolve_role_targets(db, CURRICULUM, job_role="statistical officer", as_of=NOW),
    )
    row = next(c for c in result["competencies"] if c["competency_id"] == COMPETENCY)
    assert row["role_target"] == 5.0
    assert row["role_target_assurance"] is None       # approved
    assert row["matched_field"] == "job_role"


def test_engine_without_role_targets_still_uses_the_in_memory_set(db):
    # Backward compatibility: the argument is optional and its absence must
    # not change any existing behaviour.
    result = analyse_competencies(CURRICULUM, {}, {}, "expert", job_role="statistical officer")
    row = next(c for c in result["competencies"] if c["competency_id"] == COMPETENCY)
    assert row["role_target"] == 5.0
    assert row["role_target_source"] == "internal-prototype"
