"""Package 5 -- export_subject_data()'s point-in-time snapshot contract.

`security/data_rights.py::export_subject_data()` issues one SELECT per
table via `_subject_records()`. Under PostgreSQL's default READ COMMITTED
isolation, each of those statements sees the database as of *its own*
start, not as of when the export began -- a row a concurrent transaction
commits partway through the export could appear in some of the export's
tables but not others, an internally inconsistent "point in time" that
never actually existed. This file proves the fix: `export_subject_data()`
now switches its PostgreSQL connection to REPEATABLE READ before its first
statement, so a concurrently-committed row is invisible everywhere in the
export, not just in whichever tables were already queried when it landed.

The proof is a genuine two-connection race, not a timing assumption: a
monkeypatched `_subject_records` commits the concurrent row from a second,
independent connection *between* `export_subject_data()`'s own first
statement and its first per-table query, so the row is guaranteed to exist
in the database before any of `_subject_records()`'s SELECTs run and the
test would fail if REPEATABLE READ did not hold.
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

import security.data_rights as data_rights
from db.database import Base, normalize_database_url
from models.dungeon import Dungeon  # noqa: F401 -- relationship target
from models.guild import Guild  # noqa: F401 -- relationship target
from models.identity import IdentityBinding  # noqa: F401 -- relationship target
from models.learning import CompetencyAssessment
from models.question import Question  # noqa: F401 -- relationship target
from security.data_rights import SubjectExportSessionError, export_subject_data

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
_ADMIN_DATABASE_URL = "postgresql+psycopg://prism_app:prism_dev_local_only@localhost:55432/postgres"


def test_export_requires_a_fresh_session_on_sqlite():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.execute(text("SELECT 1"))  # opens an implicit transaction

    with pytest.raises(SubjectExportSessionError, match="fresh database session"):
        export_subject_data(db, "anyone", actor="tester", reason="test")

    db.rollback()
    db.close()
    engine.dispose()


def test_export_on_sqlite_does_not_see_a_row_committed_mid_export(monkeypatch, tmp_path):
    """SQLite parity check: this project's WAL journal mode already gives a
    single connection's transaction a stable snapshot from its first
    statement, with no isolation-level change needed -- proves that's
    actually true rather than assumed."""
    db_path = tmp_path / "snapshot.db"
    url = f"sqlite:///{db_path}"

    def _enable_wal(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

    # Mirrors the real app: `db/database.py` only puts WAL mode on its own
    # module-level `engine`, not on every ad hoc `create_engine(...)` a test
    # happens to build -- so a raw engine here would run rollback-journal
    # mode instead, where a still-open reader genuinely blocks a concurrent
    # writer's commit ("database is locked"), unlike the real app's runtime
    # engine. Applying it explicitly here is what makes this test represent
    # the real deployment, not an unrepresentative default.
    engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listens_for(engine, "connect")(_enable_wal)
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO players (player_id, username, preferred_mode) VALUES (:id, :u, 'professional')"),
            {"id": "p1", "u": "learner"},
        )
    db = sessionmaker(bind=engine)()

    writer_engine = create_engine(url, connect_args={"check_same_thread": False})
    event.listens_for(writer_engine, "connect")(_enable_wal)

    real_subject_records = data_rights._subject_records

    def _commit_concurrently_then_delegate(db_arg, player_arg):
        with writer_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO competency_assessments "
                    "(assessment_id, player_id, curriculum_slug, self_ratings, measured_scores, "
                    "skill_gaps, recommended_course_ids, created_at) "
                    "VALUES ('concurrent-1', :pid, 'curr', '{}', '{}', '[]', '[]', :now)"
                ),
                {"pid": player_arg.player_id, "now": datetime.now(timezone.utc).isoformat()},
            )
        # Dispose the writer's pool immediately so no pooled connection is
        # still considered outstanding once our reader's own transaction
        # later needs to upgrade to a writer for its audit-event INSERT.
        writer_engine.dispose()
        return real_subject_records(db_arg, player_arg)

    monkeypatch.setattr(data_rights, "_subject_records", _commit_concurrently_then_delegate)

    result = export_subject_data(db, "p1", actor="tester", reason="test")

    assert not any(
        row["assessment_id"] == "concurrent-1" for row in result.records["competency_assessments"]
    )
    db.close()

    verify = sessionmaker(bind=engine)()
    assert verify.query(CompetencyAssessment).filter_by(assessment_id="concurrent-1").first() is not None
    verify.close()
    engine.dispose()
    writer_engine.dispose()


# --- Live PostgreSQL: the dialect the fix actually changes behavior for ----


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
            f"(localhost:55432) -- skipping the Package 5 PostgreSQL snapshot contract: {exc}"
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
    database_name = f"sih_pkg5_{uuid.uuid4().hex[:12]}"
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


def test_export_sets_repeatable_read_during_its_read_phase_on_postgresql(monkeypatch):
    """Checked *during* `_subject_records()`, not after the function
    returns -- by return time the read phase's REPEATABLE READ transaction
    has already been committed and the audit-write phase has started its
    own, separately isolated (default READ COMMITTED) transaction."""
    _skip_unless_postgres_reachable()
    with _disposable_migrated_postgres_database() as database_url:
        engine = create_engine(database_url)
        with engine.connect() as connection:
            connection.execute(
                text("INSERT INTO players (player_id, username, preferred_mode) VALUES ('p1', 'u', 'professional')")
            )
            connection.commit()
        db = sessionmaker(bind=engine)()

        observed = {}
        real_subject_records = data_rights._subject_records

        def _observe_then_delegate(db_arg, player_arg):
            observed["level"] = db_arg.execute(text("SHOW transaction_isolation")).scalar_one()
            return real_subject_records(db_arg, player_arg)

        monkeypatch.setattr(data_rights, "_subject_records", _observe_then_delegate)

        result = export_subject_data(db, "p1", actor="tester", reason="test")
        assert result.player_id == "p1"
        assert observed["level"] == "repeatable read"
        db.rollback()
        db.close()
        engine.dispose()


def test_export_on_postgresql_does_not_see_a_row_committed_mid_export(monkeypatch):
    _skip_unless_postgres_reachable()
    with _disposable_migrated_postgres_database() as database_url:
        engine = create_engine(database_url)
        with engine.connect() as connection:
            connection.execute(
                text("INSERT INTO players (player_id, username, preferred_mode) VALUES ('p1', 'u', 'professional')")
            )
            connection.commit()
        db = sessionmaker(bind=engine)()

        writer_engine = create_engine(database_url)
        real_subject_records = data_rights._subject_records

        def _commit_concurrently_then_delegate(db_arg, player_arg):
            with writer_engine.connect() as connection:
                connection.execute(
                    text(
                        "INSERT INTO competency_assessments "
                        "(assessment_id, player_id, curriculum_slug, self_ratings, measured_scores, "
                        "skill_gaps, recommended_course_ids, created_at) "
                        "VALUES ('concurrent-1', :pid, 'curr', '{}', '{}', '[]', '[]', now())"
                    ),
                    {"pid": player_arg.player_id},
                )
                connection.commit()
            return real_subject_records(db_arg, player_arg)

        monkeypatch.setattr(data_rights, "_subject_records", _commit_concurrently_then_delegate)

        result = export_subject_data(db, "p1", actor="tester", reason="test")

        assert not any(
            row["assessment_id"] == "concurrent-1" for row in result.records["competency_assessments"]
        )
        db.close()
        engine.dispose()

        verify_engine = create_engine(database_url)
        with verify_engine.connect() as connection:
            found = connection.execute(
                text("SELECT 1 FROM competency_assessments WHERE assessment_id = 'concurrent-1'")
            ).first()
        assert found is not None, "the concurrent row must have actually committed, not been lost"
        verify_engine.dispose()
        writer_engine.dispose()


def test_negative_control_default_isolation_would_have_seen_the_concurrent_row():
    """Proves the previous test is not vacuous: without switching to
    REPEATABLE READ, PostgreSQL's default READ COMMITTED isolation *would*
    have shown the concurrently-committed row, using the exact same timing
    this package's real fix is verified against above."""
    _skip_unless_postgres_reachable()
    with _disposable_migrated_postgres_database() as database_url:
        engine = create_engine(database_url)
        with engine.connect() as connection:
            connection.execute(
                text("INSERT INTO players (player_id, username, preferred_mode) VALUES ('p1', 'u', 'professional')")
            )
            connection.commit()

        # Deliberately the OLD behavior: default isolation, first statement
        # already run before any snapshot decision could be made.
        db = sessionmaker(bind=engine)()
        db.execute(text("SELECT 1"))  # a statement runs first, at READ COMMITTED

        writer_engine = create_engine(database_url)
        with writer_engine.connect() as connection:
            connection.execute(
                text(
                    "INSERT INTO competency_assessments "
                    "(assessment_id, player_id, curriculum_slug, self_ratings, measured_scores, "
                    "skill_gaps, recommended_course_ids, created_at) "
                    "VALUES ('concurrent-2', 'p1', 'curr', '{}', '{}', '[]', '[]', now())"
                )
            )
            connection.commit()
        writer_engine.dispose()

        visible = db.query(CompetencyAssessment).filter_by(assessment_id="concurrent-2").first()
        assert visible is not None, (
            "default READ COMMITTED should show a row committed after this "
            "transaction's first statement -- if it doesn't, this negative "
            "control itself is broken, not proof the real fix is unnecessary"
        )
        db.rollback()
        db.close()
        engine.dispose()
