"""Tests for the two-mode scaffold (models/enums.py's `LearningMode` and
`players.preferred_mode`) -- the team's own recorded decision (WhatsApp
thread, 2 Sep 2026) that a non-gamified, KCM/Mission Karmayogi-oriented
"professional" experience is the default/base product, with the existing
dungeon/XP/combat layer preserved as an explicit "quest" opt-in.

This is a foundation, not the feature: no route reads or writes this value
yet (see schemas/player.py's PlayerCreate docstring), no curriculum-per-mode
policy exists (Lane 3's decision), and no frontend routes on it (Lane 1/5's
decision). These tests only prove the Lane 2-owned storage layer itself:
the default is correct, invalid values are genuinely rejected (not just
documented as rejected), and the migration is symmetric.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from db.database import Base
from models.accuracy_history import AccuracyHistory  # noqa: F401 -- relationship target
from models.dungeon import Dungeon, Room  # noqa: F401 -- relationship target
from models.enums import DEFAULT_LEARNING_MODE, LEARNING_MODE_VALUES, LearningMode
from models.guild import Guild  # noqa: F401 -- relationship target
from models.player import Player
from models.question import Question  # noqa: F401 -- relationship target
from models.session import GameSession  # noqa: F401 -- relationship target
from models.submission import AnswerSubmission  # noqa: F401 -- relationship target
from schemas.player import PlayerResponse


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
PRECEDING_REVISION = "4631f204d4ba"
THIS_REVISION = "640603a37f2f"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# models/enums.py -- internal consistency
# ---------------------------------------------------------------------------


def test_default_learning_mode_is_professional_not_quest():
    # The whole point of the team's decision: a government-official learner
    # must never be defaulted into the game. Pinning this as its own
    # assertion means a future accidental reordering of the enum, or a
    # copy-paste of QUEST as the default, fails loudly and specifically --
    # not just as a side effect of some other test.
    assert DEFAULT_LEARNING_MODE == LearningMode.PROFESSIONAL.value == "professional"


def test_learning_mode_values_contains_exactly_the_two_known_modes():
    assert set(LEARNING_MODE_VALUES) == {"professional", "quest"}


def test_default_learning_mode_is_itself_a_valid_learning_mode_value():
    # Defense against the default and the allowed-value set silently
    # drifting apart -- e.g. if DEFAULT_LEARNING_MODE were hardcoded as a
    # string instead of derived from the enum.
    assert DEFAULT_LEARNING_MODE in LEARNING_MODE_VALUES


# ---------------------------------------------------------------------------
# models/player.py -- Player.preferred_mode default and persistence
# ---------------------------------------------------------------------------


def test_new_player_defaults_to_professional_mode_without_specifying_it(db):
    player = Player(player_id="p1", username="mode-default")
    db.add(player)
    db.commit()
    db.refresh(player)

    assert player.preferred_mode == DEFAULT_LEARNING_MODE


def test_explicit_quest_mode_persists_through_a_round_trip(db):
    player = Player(player_id="p2", username="mode-quest", preferred_mode="quest")
    db.add(player)
    db.commit()

    db.expire_all()
    reloaded = db.query(Player).filter(Player.player_id == "p2").one()
    assert reloaded.preferred_mode == "quest"


def test_unknown_mode_value_is_rejected_at_the_database_level_not_just_in_application_code(db):
    """The CHECK constraint (models/player.py's __table_args__, mirrored in
    migrations/versions/640603a37f2f_*.py for PostgreSQL) must be real
    enforcement, not documentation -- a bug in some future caller that
    builds `Player(preferred_mode=user_input)` from unvalidated input must
    still be caught by the database itself, the same defense-in-depth
    pattern already established by security.retention's minimum-retention
    guard.
    """
    db.add(Player(player_id="p3", username="mode-bogus", preferred_mode="dungeon-master"))
    with pytest.raises(IntegrityError, match="ck_players_preferred_mode_known_value"):
        db.commit()
    db.rollback()

    # The rejected row must not have been partially persisted.
    assert db.query(Player).filter(Player.player_id == "p3").first() is None


# ---------------------------------------------------------------------------
# schemas/player.py -- PlayerResponse validates the stored value as an enum
# ---------------------------------------------------------------------------


def test_player_response_accepts_a_valid_stored_mode(db):
    player = Player(player_id="p4", username="mode-schema-ok", preferred_mode="quest")
    db.add(player)
    db.commit()
    db.refresh(player)

    response = PlayerResponse.model_validate(player)
    assert response.preferred_mode == LearningMode.QUEST


def test_player_response_rejects_a_value_outside_the_known_enum():
    # Simulates a row written by something that bypassed the CHECK
    # constraint entirely (e.g. a raw UPDATE, or a future dialect this
    # constraint doesn't cover) -- the schema layer is a second,
    # independent line of defense, not a redundant restatement of the same
    # one.
    class _FakeOrmRow:
        player_id = "p5"
        username = "mode-schema-bad"
        level = 1
        total_xp = 0
        streak_days = 0
        last_active = None
        guild_id = None
        hint_tokens = 3
        preferred_mode = "dungeon-master"

    with pytest.raises(ValidationError):
        PlayerResponse.model_validate(_FakeOrmRow())


# ---------------------------------------------------------------------------
# Migration 640603a37f2f -- symmetric on a real (subprocess) SQLite chain,
# matching this project's established per-migration verification pattern
# (see test_core_migrations.py). Exercised via batch mode, so this also
# proves the CHECK constraint survives a real Alembic-run migration, not
# just Base.metadata.create_all().
# ---------------------------------------------------------------------------


def _run_alembic(database_url: str, *arguments: str) -> None:
    import os

    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=BACKEND_DIRECTORY,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"alembic {' '.join(arguments)} failed:\n{result.stdout}\n{result.stderr}")


def test_migration_adds_column_and_constraint_then_downgrade_removes_them_cleanly(tmp_path):
    database_url = f"sqlite:///{(tmp_path / 'mode_migration.db').as_posix()}"
    _run_alembic(database_url, "upgrade", "head")

    engine = create_engine(database_url)
    columns = {c["name"] for c in inspect(engine).get_columns("players")}
    assert "preferred_mode" in columns

    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(
                text(
                    "INSERT INTO players (player_id, username, preferred_mode) "
                    "VALUES ('x', 'y', 'nonsense')"
                )
            )
    engine.dispose()

    _run_alembic(database_url, "downgrade", PRECEDING_REVISION)
    engine = create_engine(database_url)
    columns_after_downgrade = {c["name"] for c in inspect(engine).get_columns("players")}
    assert "preferred_mode" not in columns_after_downgrade
    engine.dispose()

    _run_alembic(database_url, "upgrade", THIS_REVISION)
    engine = create_engine(database_url)
    columns_after_reupgrade = {c["name"] for c in inspect(engine).get_columns("players")}
    assert "preferred_mode" in columns_after_reupgrade
    engine.dispose()
