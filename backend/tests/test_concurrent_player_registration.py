"""Regression coverage for a real concurrency bug found via a concurrent-load
test against the deployed Render/Neon stack: POST /game/player/create's
check-then-insert pattern (query for an existing username, then commit a new
row) is a classic time-of-check-to-time-of-use race. Two concurrent requests
for the *same* not-yet-taken username can both pass the pre-check before
either commits; the loser's commit then hits Player.username's real
`unique=True` constraint. Before the fix, that raised an uncaught
IntegrityError straight out of create_player -- an unhandled 500, not the
clean 400 a non-concurrent duplicate already gets.

A real, un-mocked SQLite connection enforces the unique constraint the same
way Postgres does, but SQLite (unlike Postgres's row-level MVCC) serializes
writers at the connection/file level, so two genuinely-simultaneous
uncommitted transactions on the same DB can't be staged the way they can in
production. Deterministically forcing the exact interleaving instead: the
pre-check is monkeypatched to report "not taken" for one call even though
the username is already committed in the table -- exactly what a real
pre-check sees when it races a concurrent request that commits microseconds
later. This exercises the real commit -> IntegrityError -> except branch
without depending on fragile real-thread timing.
"""
import asyncio
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Query
from sqlalchemy.pool import StaticPool

from db.database import Base
from models.player import Player  # noqa: F401
from models.guild import Guild  # noqa: F401
from models.dungeon import Dungeon, Room  # noqa: F401
from models.session import GameSession  # noqa: F401
from models.question import Question  # noqa: F401
from models.submission import AnswerSubmission  # noqa: F401
from models.accuracy_history import AccuracyHistory  # noqa: F401
from models.learning import LearningMaterial  # noqa: F401 -- governance FK registration
from routes.game import create_player
from schemas.player import PlayerCreate


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def test_concurrent_identical_username_registration_does_not_crash(db_session):
    username = "race-winner"
    # Simulates the concurrent request that "won" the race: already
    # committed before our call's pre-check runs.
    db_session.add(Player(username=username))
    db_session.commit()

    # Force the pre-check to report "not taken" anyway -- exactly what a
    # real concurrent request's pre-check would have seen microseconds
    # earlier, before the winner's commit landed.
    with patch.object(Query, "first", return_value=None):
        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(create_player(PlayerCreate(username=username), db=db_session))

    # Before the fix: this raised sqlalchemy.exc.IntegrityError, an
    # unhandled 500. After the fix: the same honest 400 a plain
    # (non-racing) duplicate already gets.
    assert exc_info.value.status_code == 400
    assert "already taken" in exc_info.value.detail.lower()

    # The session is left usable afterward (a real rollback happened),
    # not stuck in a broken/aborted transaction state, and no duplicate
    # row was left behind.
    assert db_session.query(Player).filter(Player.username == username).count() == 1
    db_session.add(Player(username="still-usable-afterward"))
    db_session.commit()


def test_non_concurrent_duplicate_username_still_rejected_by_pre_check(db_session):
    """The ordinary (non-racing) path is unchanged: a plain duplicate is
    still rejected by the fast pre-check, never reaching the commit/except
    branch at all."""
    asyncio.run(create_player(PlayerCreate(username="taken"), db=db_session))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(create_player(PlayerCreate(username="taken"), db=db_session))
    assert exc_info.value.status_code == 400
    assert "already taken" in exc_info.value.detail.lower()
