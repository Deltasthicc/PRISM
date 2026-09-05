"""Package 2 -- SQLite foreign-key enforcement and transaction-semantics
parity.

Before this package, `db/database.py` set `PRAGMA journal_mode=WAL` and
`PRAGMA synchronous=NORMAL` on every SQLite connection but never
`PRAGMA foreign_keys=ON` -- SQLite ships FK enforcement OFF by default, so
every `ForeignKey()` column across `models/*.py` was silently unenforced. An
orphan INSERT and a parent DELETE that orphans its children both succeeded
without error, unlike PostgreSQL, which enforces FKs unconditionally.

This file proves, on SQLite:
  1. the fix applies process-wide, including to ad hoc `create_engine(...)`
     calls the ~20 other test files make directly, not just `db.database`'s
     own module-level `engine`;
  2. an orphan INSERT is now rejected;
  3. deleting a still-referenced parent is now rejected (SQLite's default,
     matching PostgreSQL's default RESTRICT/NO ACTION -- neither model
     declares an explicit ON DELETE CASCADE);
  4. `PRAGMA foreign_key_check` -- SQLite's own retroactive audit tool --
     can find a violation that predates this fix (the "legacy unversioned
     SQLite adoption path" Codex's package spec asked to be audited: an
     existing demo `app.db` created before this pragma existed could already
     contain an orphan row that enabling the pragma alone would not detect
     until something touches it);
  5. the one-time-admin bootstrap's raw `BEGIN IMMEDIATE` (see
     `security/identity_bootstrap.py::_acquire_bootstrap_lock`) still opens
     and holds SQLite's write lock correctly with FK enforcement on --
     the specific regression risk this package's `db/database.py` docstring
     names and was told not to introduce via `sqlite3.Connection.autocommit`;
  6. a nested savepoint rollback discards only the nested change.

`test_core_seed.py` (unchanged by this package) is the existing regression
proof that `db/seed.py`'s parent-before-child insert order already satisfies
real FK enforcement -- both its dungeon/room and player/accuracy-history
insert sequences flush the parent before creating a child that references
it. `test_core_identity_bootstrap.py::test_concurrent_bootstrap_attempts_create_exactly_one_binding`
is the existing regression proof that the same `BEGIN IMMEDIATE` mechanism
still serializes two genuinely concurrent writers correctly. Both were run
after this package's `db/database.py` change and are cited as evidence in
`LANE2_SYNC.md` rather than duplicated here.

The live-PostgreSQL tests exist for documented parity, not because
PostgreSQL needed a fix -- it has always enforced FKs unconditionally.
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker

from db.database import Base, normalize_database_url
from models.accuracy_history import AccuracyHistory  # noqa: F401 -- relationship target
from models.dungeon import Dungeon, Room  # noqa: F401 -- relationship target
from models.governance import EvidenceRecord
from models.guild import Guild  # noqa: F401 -- relationship target
from models.identity import IdentityBinding  # noqa: F401 -- relationship target
from models.learning import (  # noqa: F401 -- relationship target
    CompetencyAssessment,
    GeneratedQuiz,
    LearnerProfile,
    LearningMaterial,
)
from models.player import Player
from models.question import Question  # noqa: F401 -- relationship target
from models.session import GameSession  # noqa: F401 -- relationship target
from models.submission import AnswerSubmission  # noqa: F401 -- relationship target
from security.identity_bootstrap import _acquire_bootstrap_lock
import db.seed as seed_module

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
_ADMIN_DATABASE_URL = "postgresql+psycopg://prism_app:prism_dev_local_only@localhost:55432/postgres"


@pytest.fixture
def sqlite_session_factory():
    """A bare ad hoc SQLite engine, deliberately NOT `db.database.engine` --
    proves the class-level listener applies here too, not just to the one
    engine `db/database.py` builds for itself."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


def test_foreign_keys_pragma_enabled_on_every_sqlite_connection_process_wide(sqlite_session_factory):
    session = sqlite_session_factory()
    enabled = session.execute(text("PRAGMA foreign_keys")).scalar()
    session.close()
    assert enabled == 1


def test_orphan_insert_is_rejected_on_sqlite(sqlite_session_factory):
    session = sqlite_session_factory()
    session.add(
        EvidenceRecord(
            player_id="no-such-player",
            competency_id="os_statistical_programming",
            evidence_type="self_report",
            value=3,
        )
    )
    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        session.commit()
    session.rollback()
    session.close()


def test_deleting_a_still_referenced_parent_is_rejected_on_sqlite(sqlite_session_factory):
    session = sqlite_session_factory()
    player = Player(username="fk-parity-learner")
    session.add(player)
    session.flush()
    session.add(
        EvidenceRecord(
            player_id=player.player_id,
            competency_id="os_statistical_programming",
            evidence_type="self_report",
            value=3,
        )
    )
    session.commit()

    session.delete(player)
    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        session.commit()
    session.rollback()
    session.close()


def test_deleting_the_child_then_the_parent_succeeds_on_sqlite(sqlite_session_factory):
    """Negative control for the previous test: proves the rejection is
    specifically about the dangling reference, not about deleting a `Player`
    row at all."""
    session = sqlite_session_factory()
    player = Player(username="fk-parity-learner-cleanup")
    session.add(player)
    session.flush()
    evidence = EvidenceRecord(
        player_id=player.player_id,
        competency_id="os_statistical_programming",
        evidence_type="self_report",
        value=3,
    )
    session.add(evidence)
    session.commit()

    session.delete(evidence)
    session.delete(player)
    session.commit()  # must not raise

    assert session.query(Player).filter_by(player_id=player.player_id).first() is None
    session.close()


def test_foreign_key_check_detects_a_preexisting_orphan_row(sqlite_session_factory):
    """Simulates exactly the risk this package's `db/database.py` docstring
    names: an existing SQLite file created *before* this fix, already
    holding an orphan row that turning the pragma on today cannot
    retroactively catch (SQLite only checks FKs at write time). `PRAGMA
    foreign_key_check` is SQLite's own tool for auditing already-committed
    data for exactly this, and this proves it actually finds the row --
    the concrete audit step for the "legacy unversioned SQLite adoption
    path" the package spec asked to be checked, since no such file exists
    in a fresh checkout to inspect directly.
    """
    session = sqlite_session_factory()
    # Briefly disable enforcement to construct the exact state a
    # pre-this-fix file could already be in -- this does not exercise
    # `db.database`'s fix at all, only the detector's ability to find its
    # damage after the fact. Issued via `session.execute()`, not a raw
    # `Connection` held across the intervening `commit()`, because a plain
    # (non-`session.begin()`) session returns its connection to the pool on
    # commit -- a stashed `Connection` object would be stale afterward.
    session.execute(text("PRAGMA foreign_keys=OFF"))
    session.add(
        EvidenceRecord(
            evidence_id="preexisting-orphan",
            player_id="ghost-player-never-existed",
            competency_id="os_statistical_programming",
            evidence_type="self_report",
            value=3,
        )
    )
    session.commit()
    session.execute(text("PRAGMA foreign_keys=ON"))

    violations = session.execute(text("PRAGMA foreign_key_check")).fetchall()
    session.close()

    assert len(violations) == 1
    table, rowid, parent_table, fk_index = violations[0]
    assert table == "evidence_records"
    assert parent_table == "players"


def test_ensure_columns_ddl_still_works_with_fk_enforcement_on(sqlite_session_factory):
    """`db/database.py::ensure_columns()` is the legacy SQLite adoption path
    itself (a plain `ALTER TABLE ... ADD COLUMN` against a pre-existing
    file). Proves that DDL still runs cleanly on an FK-enforced connection
    -- SQLite historically restricts some ALTER TABLE forms while FKs are
    referenced, and this is the simple additive form the app actually uses.
    """
    session = sqlite_session_factory()
    connection = session.connection()
    connection.execute(text("ALTER TABLE players ADD COLUMN fk_parity_probe_column TEXT"))
    session.commit()
    columns = {row[1] for row in session.execute(text("PRAGMA table_info(players)"))}
    session.close()
    assert "fk_parity_probe_column" in columns


def test_nested_savepoint_rollback_discards_only_the_nested_change(sqlite_session_factory):
    session = sqlite_session_factory()
    outer = Player(username="fk-parity-outer-survivor")
    session.add(outer)
    session.flush()

    nested = session.begin_nested()
    doomed = Player(username="fk-parity-nested-discarded")
    session.add(doomed)
    session.flush()
    nested.rollback()

    session.commit()

    usernames = {p.username for p in session.query(Player).all()}
    session.close()
    assert "fk-parity-outer-survivor" in usernames
    assert "fk-parity-nested-discarded" not in usernames


def test_bootstrap_begin_immediate_still_acquires_the_write_lock_under_fk_enforcement(tmp_path):
    """Regression guard for the exact risk this package's `db/database.py`
    change flags: FK enforcement must not interfere with
    `security/identity_bootstrap.py`'s raw `BEGIN IMMEDIATE`, which depends
    on SQLAlchemy's pysqlite dialect NOT pre-opening a transaction (i.e.
    `sqlite3.Connection.autocommit` staying at the legacy default this
    package deliberately does not touch). Proves the lock is genuinely held
    -- a second connection's own `BEGIN IMMEDIATE` against the same file
    must fail while the first is still open, then succeed once released.
    """
    db_path = tmp_path / "bootstrap_lock_probe.db"
    engine_a = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False, "timeout": 0.5})
    engine_b = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False, "timeout": 0.5})
    Base.metadata.create_all(engine_a)

    session_a = sessionmaker(bind=engine_a)()
    session_b = sessionmaker(bind=engine_b)()
    try:
        assert session_a.execute(text("PRAGMA foreign_keys")).scalar() == 1

        _acquire_bootstrap_lock(session_a)  # holds SQLite's RESERVED write lock

        with pytest.raises(OperationalError, match="database is locked"):
            _acquire_bootstrap_lock(session_b)
        session_b.rollback()

        session_a.commit()  # release engine_a's lock

        # Now that the first lock is released, a fresh attempt succeeds.
        _acquire_bootstrap_lock(session_b)
        session_b.commit()
    finally:
        session_a.close()
        session_b.close()
        engine_a.dispose()
        engine_b.dispose()


def test_seed_database_and_seed_curricula_dungeons_run_clean_under_fk_enforcement(monkeypatch):
    """End-to-end companion to `test_core_seed.py`'s structural assertions:
    actually runs both real seed entry points against a fresh FK-enforced
    engine and asserts neither raises `IntegrityError`. `test_core_seed.py`
    already pins the resulting shape (one DSA dungeon, a demo player, one
    dungeon per curriculum); this file only needs to prove FK-cleanliness,
    which is why it does not repeat those shape assertions.
    """
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(seed_module, "SessionLocal", factory)

    seed_module.seed_database()
    seed_module.seed_curricula_dungeons()

    engine.dispose()


# --- Live PostgreSQL parity -------------------------------------------------


def _skip_unless_postgres_reachable() -> None:
    try:
        probe = create_engine(_ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
        try:
            with probe.connect() as connection:
                connection.execute(text("SELECT 1"))
        finally:
            probe.dispose()
    except OperationalError as exc:
        pytest.skip(
            "Real PostgreSQL not reachable at the documented docker-compose.dev.yml URL "
            f"(localhost:55432) -- skipping the Package 2 PostgreSQL parity contract: {exc}"
        )


def _run_alembic(database_url: str, *arguments: str) -> None:
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


def _drop_database(database_name: str) -> None:
    admin = create_engine(_ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": database_name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
    finally:
        admin.dispose()


@contextlib.contextmanager
def _disposable_migrated_postgres_database():
    """Same disposable-database contract as
    `test_core_retention_job_postgres_integration.py` (never the shared
    `prism` dev database, `try`/`finally` cleanup unconditional on any
    failure between `CREATE DATABASE` and `yield`)."""
    database_name = f"sih_pkg2_{uuid.uuid4().hex[:12]}"
    probe = create_engine(_ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    created = False
    try:
        with probe.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        created = True
        database_url = normalize_database_url(
            f"postgresql://prism_app:prism_dev_local_only@localhost:55432/{database_name}"
        )
        _run_alembic(database_url, "upgrade", "head")
        yield database_url
    finally:
        probe.dispose()
        if created:
            _drop_database(database_name)


def test_orphan_insert_is_rejected_on_postgresql():
    _skip_unless_postgres_reachable()
    with _disposable_migrated_postgres_database() as database_url:
        engine = create_engine(database_url)
        session = sessionmaker(bind=engine)()
        session.add(
            EvidenceRecord(
                player_id="no-such-player",
                competency_id="os_statistical_programming",
                evidence_type="self_report",
                value=3,
            )
        )
        with pytest.raises(IntegrityError, match="violates foreign key constraint"):
            session.commit()
        session.rollback()
        session.close()
        engine.dispose()


def test_deleting_a_still_referenced_parent_is_rejected_on_postgresql():
    _skip_unless_postgres_reachable()
    with _disposable_migrated_postgres_database() as database_url:
        engine = create_engine(database_url)
        session = sessionmaker(bind=engine)()
        player = Player(username="fk-parity-postgres-learner")
        session.add(player)
        session.flush()
        session.add(
            EvidenceRecord(
                player_id=player.player_id,
                competency_id="os_statistical_programming",
                evidence_type="self_report",
                value=3,
            )
        )
        session.commit()

        session.delete(player)
        with pytest.raises(IntegrityError, match="violates foreign key constraint"):
            session.commit()
        session.rollback()
        session.close()
        engine.dispose()
