"""Regression tests for the SEED_DEMO_DATA startup gate.

Covers the pure resolution function directly, then the real main.py lifespan
end-to-end over subprocess-driven temp SQLite, the same pattern
test_core_migrations.py uses. PostgreSQL's opt-out-by-default behavior was
additionally verified manually against a live container and is recorded in
LANE2_SYNC.md -- not exercised here, so this suite keeps running without a
database server, per CLAUDE.md's testing invariant.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

from db.database import should_seed_demo_data


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]


# --- should_seed_demo_data() ---


def test_defaults_to_true_on_the_sqlite_test_process(monkeypatch):
    monkeypatch.delenv("SEED_DEMO_DATA", raising=False)
    assert should_seed_demo_data() is True


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "On"])
def test_recognizes_every_documented_true_spelling(monkeypatch, value):
    monkeypatch.setenv("SEED_DEMO_DATA", value)
    assert should_seed_demo_data() is True


@pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off", "", "garbage"])
def test_treats_everything_else_as_false(monkeypatch, value):
    monkeypatch.setenv("SEED_DEMO_DATA", value)
    assert should_seed_demo_data() is False


# --- real main.py lifespan, over subprocess + temp SQLite ---


def _boot_and_count_players(tmp_path, seed_demo_data: str | None) -> int:
    database_url = f"sqlite:///{(tmp_path / 'seed_gate.db').as_posix()}"
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    if seed_demo_data is None:
        environment.pop("SEED_DEMO_DATA", None)
    else:
        environment["SEED_DEMO_DATA"] = seed_demo_data

    script = (
        "import asyncio\n"
        "from main import lifespan, app\n"
        "async def go():\n"
        "    async with lifespan(app):\n"
        "        pass\n"
        "asyncio.run(go())\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=BACKEND_DIRECTORY,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    engine = create_engine(database_url)
    tables = set(inspect(engine).get_table_names())
    if "players" not in tables:
        engine.dispose()
        return 0
    with engine.connect() as connection:
        count = connection.execute(text("SELECT count(*) FROM players")).scalar_one()
    engine.dispose()
    return count


def test_sqlite_seeds_demo_data_by_default(tmp_path):
    assert _boot_and_count_players(tmp_path, seed_demo_data=None) > 0


def test_sqlite_skips_seeding_when_explicitly_disabled(tmp_path):
    assert _boot_and_count_players(tmp_path, seed_demo_data="false") == 0


def test_sqlite_seeds_when_explicitly_enabled_even_if_redundant(tmp_path):
    assert _boot_and_count_players(tmp_path, seed_demo_data="true") > 0
