"""Tests for db/repositories.py against the exact ordering contract in
docs/contracts/data-authorization.md section 4."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from db.database import Base
from db.repositories import get_latest_assessment
from models.accuracy_history import AccuracyHistory  # noqa: F401 -- relationship target
from models.dungeon import Dungeon, Room  # noqa: F401 -- relationship target
from models.guild import Guild  # noqa: F401 -- relationship target
from models.learning import CompetencyAssessment
from models.player import Player
from models.question import Question  # noqa: F401 -- relationship target
from models.session import GameSession  # noqa: F401 -- relationship target
from models.submission import AnswerSubmission  # noqa: F401 -- relationship target


PLAYER_ID = "repo-test-player"
CURRICULUM = "official-statistics"
OTHER_CURRICULUM = "public-policy"
OTHER_PLAYER_ID = "repo-test-other-player"

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([Player(player_id=PLAYER_ID, username="repo_test"),
                      Player(player_id=OTHER_PLAYER_ID, username="repo_test_other")])
    session.commit()
    yield session
    session.close()


def _assessment(assessment_id, created_at, player_id=PLAYER_ID, curriculum_slug=CURRICULUM):
    return CompetencyAssessment(
        assessment_id=assessment_id,
        player_id=player_id,
        curriculum_slug=curriculum_slug,
        created_at=created_at,
    )


def test_returns_none_when_no_assessment_exists(db):
    assert get_latest_assessment(db, PLAYER_ID, CURRICULUM) is None


def test_returns_the_only_assessment(db):
    db.add(_assessment("a1", T0))
    db.commit()
    result = get_latest_assessment(db, PLAYER_ID, CURRICULUM)
    assert result.assessment_id == "a1"


def test_prefers_more_recent_created_at(db):
    db.add_all([
        _assessment("older", T0),
        _assessment("newer", T0 + timedelta(days=1)),
    ])
    db.commit()
    assert get_latest_assessment(db, PLAYER_ID, CURRICULUM).assessment_id == "newer"


def test_non_null_created_at_always_beats_null_even_if_inserted_later(db):
    db.add(_assessment("has_timestamp", T0))
    db.commit()
    # CompetencyAssessment.created_at has a Python-side `default=`, which
    # SQLAlchemy applies whenever the flushed value would be None -- so
    # constructing a row with created_at=None through the ORM can never
    # actually produce a NULL column; SQLAlchemy quietly fills in "now"
    # instead. A NULL row is therefore only reachable through a write that
    # bypasses the ORM default (a raw insert, a bulk import, a pre-default
    # legacy row) -- reproduced here with a raw UPDATE after insert, which is
    # the only way this test can honestly exercise the contract's "non-null
    # beats null" clause instead of accidentally testing something that can't
    # occur.
    db.add(_assessment("null_timestamp", T0 + timedelta(days=1)))
    db.commit()
    db.execute(
        text("UPDATE competency_assessments SET created_at = NULL WHERE assessment_id = 'null_timestamp'")
    )
    db.commit()
    db.expire_all()

    assert get_latest_assessment(db, PLAYER_ID, CURRICULUM).assessment_id == "has_timestamp"


def test_assessment_id_breaks_ties_on_identical_created_at(db):
    db.add_all([
        _assessment("aaa", T0),
        _assessment("zzz", T0),
    ])
    db.commit()
    # Same created_at for both -- assessment_id descending must decide, and
    # must do so the same way every time this test runs.
    assert get_latest_assessment(db, PLAYER_ID, CURRICULUM).assessment_id == "zzz"


def test_does_not_cross_curriculum_boundary(db):
    db.add_all([
        _assessment("this-curriculum", T0, curriculum_slug=CURRICULUM),
        _assessment("other-curriculum", T0 + timedelta(days=1), curriculum_slug=OTHER_CURRICULUM),
    ])
    db.commit()
    assert get_latest_assessment(db, PLAYER_ID, CURRICULUM).assessment_id == "this-curriculum"


def test_does_not_cross_player_boundary(db):
    db.add_all([
        _assessment("mine", T0, player_id=PLAYER_ID),
        _assessment("theirs", T0 + timedelta(days=1), player_id=OTHER_PLAYER_ID),
    ])
    db.commit()
    assert get_latest_assessment(db, PLAYER_ID, CURRICULUM).assessment_id == "mine"
