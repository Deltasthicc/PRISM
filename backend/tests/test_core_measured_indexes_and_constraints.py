"""Package 4 -- measured indexes and Lane 2 governance CHECK constraints
(migration `6564595b3466`, revises `640603a37f2f`).

Every index below matches the exact WHERE/ORDER BY shape one of
`db/repositories.py`'s latest-row lookups issues, and was kept only after a
representative ~120k-row PostgreSQL `EXPLAIN (ANALYZE, BUFFERS)` comparison
showed a real access-path improvement -- not added speculatively. The raw
before/after planner output is recorded in `LANE2_SYNC.md`'s Package 4 entry,
not reproduced here; this file proves the schema actually matches that
evidence (the indexes/constraints exist, with the right columns, on both
dialects) and that the new constraints actually reject bad data rather than
merely existing as decoration.

Alembic 1.14 cannot autogenerate-detect CHECK constraint drift (confirmed:
this revision's own `alembic revision --autogenerate` run detected all six
new indexes but none of the five CHECK constraints) -- the schema-contract
tests below are what actually pins the constraints' presence and correctness
where `alembic check` cannot.
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError, OperationalError

from db.database import normalize_database_url

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
_ADMIN_DATABASE_URL = "postgresql+psycopg://prism_app:prism_dev_local_only@localhost:55432/postgres"
_PARENT_REVISION = "640603a37f2f"
_THIS_REVISION = "6564595b3466"

_EXPECTED_INDEXES = {
    "competency_assessments": {
        "ix_competency_assessments_lookup_newest": ["player_id", "curriculum_slug", "created_at", "assessment_id"],
    },
    "evidence_records": {
        "ix_evidence_records_lookup_newest": ["player_id", "competency_id", "evidence_type", "recorded_at", "evidence_id"],
    },
    "game_sessions": {"ix_game_sessions_player_id": ["player_id"]},
    "role_targets": {
        "ix_role_targets_lookup_newest": ["role", "competency_id", "valid_from", "created_at", "target_id"],
    },
    "source_versions": {
        "ix_source_versions_lookup_newest": ["material_id", "version_number", "created_at", "source_version_id"],
    },
    "submissions": {"ix_submissions_player_id": ["player_id"]},
}
_EXPECTED_CHECK_NAMES = {
    "role_targets": {"ck_role_targets_target_level_1_5", "ck_role_targets_valid_window"},
    "evidence_records": {"ck_evidence_records_type", "ck_evidence_records_value_0_5"},
    "source_versions": {"ck_source_versions_version_positive"},
}


def _run_alembic(database_url: str, *arguments: str, check: bool = True) -> subprocess.CompletedProcess:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=BACKEND_DIRECTORY,
        env=environment,
        capture_output=True,
        text=True,
        check=check,
    )


@pytest.fixture
def migrated_sqlite(tmp_path):
    url = f"sqlite:///{tmp_path / 'pkg4.db'}"
    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url, connect_args={"check_same_thread": False})
    yield engine, url
    engine.dispose()


def test_migration_creates_all_six_indexes_with_correct_columns_on_sqlite(migrated_sqlite):
    engine, _ = migrated_sqlite
    inspector = inspect(engine)
    for table, expected in _EXPECTED_INDEXES.items():
        actual = {index["name"]: index["column_names"] for index in inspector.get_indexes(table)}
        for name, columns in expected.items():
            assert name in actual, f"missing index {name} on {table}"
            assert actual[name] == columns, f"{name} covers {actual[name]}, expected {columns}"


def test_migration_creates_all_five_check_constraints_on_sqlite(migrated_sqlite):
    engine, _ = migrated_sqlite
    inspector = inspect(engine)
    for table, expected_names in _EXPECTED_CHECK_NAMES.items():
        actual_names = {c["name"] for c in inspector.get_check_constraints(table)}
        assert expected_names <= actual_names, f"{table} missing {expected_names - actual_names}"


def test_migration_downgrade_removes_everything_and_upgrade_restores_it(tmp_path):
    url = f"sqlite:///{tmp_path / 'pkg4_cycle.db'}"
    _run_alembic(url, "upgrade", "head")
    _run_alembic(url, "downgrade", _PARENT_REVISION)

    engine = create_engine(url, connect_args={"check_same_thread": False})
    inspector = inspect(engine)
    for table, expected in _EXPECTED_INDEXES.items():
        actual_names = {index["name"] for index in inspector.get_indexes(table)}
        for name in expected:
            assert name not in actual_names, f"{name} survived downgrade"
    for table, expected_names in _EXPECTED_CHECK_NAMES.items():
        actual_names = {c["name"] for c in inspector.get_check_constraints(table)}
        assert not (expected_names & actual_names), f"{table} still has a constraint after downgrade"
    engine.dispose()

    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url, connect_args={"check_same_thread": False})
    inspector = inspect(engine)
    for table, expected in _EXPECTED_INDEXES.items():
        actual_names = {index["name"] for index in inspector.get_indexes(table)}
        for name in expected:
            assert name in actual_names, f"{name} did not come back after re-upgrade"
    engine.dispose()


def test_preflight_rejects_upgrade_when_existing_role_target_level_is_out_of_range(tmp_path):
    url = f"sqlite:///{tmp_path / 'pkg4_bad_role.db'}"
    _run_alembic(url, "upgrade", _PARENT_REVISION)
    engine = create_engine(url, connect_args={"check_same_thread": False})
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO role_targets (target_id, framework_version, role, competency_id, "
                "target_level, source) VALUES ('bad-target', 'v1', 'role', 'comp', 9, 'test')"
            )
        )
    engine.dispose()

    result = _run_alembic(url, "upgrade", "head", check=False)
    assert result.returncode != 0
    assert "target_level outside 1..5" in result.stdout + result.stderr
    assert "1 rows" in result.stdout + result.stderr

    # And the migration genuinely did not partially apply.
    engine = create_engine(url, connect_args={"check_same_thread": False})
    inspector = inspect(engine)
    actual_names = {index["name"] for index in inspector.get_indexes("role_targets")}
    assert "ix_role_targets_lookup_newest" not in actual_names
    engine.dispose()


def test_preflight_rejects_upgrade_when_existing_evidence_value_is_out_of_range(tmp_path):
    url = f"sqlite:///{tmp_path / 'pkg4_bad_evidence.db'}"
    _run_alembic(url, "upgrade", _PARENT_REVISION)
    engine = create_engine(url, connect_args={"check_same_thread": False})
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        connection.execute(
            text(
                "INSERT INTO evidence_records (evidence_id, player_id, competency_id, "
                "evidence_type, value) VALUES ('bad-evidence', 'ghost', 'comp', 'self_report', 99)"
            )
        )
    engine.dispose()

    result = _run_alembic(url, "upgrade", "head", check=False)
    assert result.returncode != 0
    assert "value outside 0..5" in result.stdout + result.stderr


def test_check_constraint_rejects_invalid_role_target_level_on_sqlite(migrated_sqlite):
    engine, _ = migrated_sqlite
    with pytest.raises(IntegrityError, match="ck_role_targets_target_level_1_5"):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO role_targets (target_id, framework_version, role, competency_id, "
                    "target_level, source) VALUES ('t1', 'v1', 'role', 'comp', 0, 'test')"
                )
            )


def test_check_constraint_rejects_valid_to_before_valid_from_on_sqlite(migrated_sqlite):
    engine, _ = migrated_sqlite
    with pytest.raises(IntegrityError, match="ck_role_targets_valid_window"):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO role_targets (target_id, framework_version, role, competency_id, "
                    "target_level, source, valid_from, valid_to) VALUES "
                    "('t2', 'v1', 'role', 'comp', 3, 'test', '2026-02-01', '2026-01-01')"
                )
            )


def test_check_constraint_rejects_unknown_evidence_type_on_sqlite(migrated_sqlite):
    engine, _ = migrated_sqlite
    with pytest.raises(IntegrityError, match="ck_evidence_records_type"):
        with engine.begin() as connection:
            connection.execute(text("PRAGMA foreign_keys=OFF"))
            connection.execute(
                text(
                    "INSERT INTO evidence_records (evidence_id, player_id, competency_id, "
                    "evidence_type) VALUES ('e1', 'ghost', 'comp', 'made_up_type')"
                )
            )


def test_check_constraint_rejects_source_version_below_one_on_sqlite(migrated_sqlite):
    engine, _ = migrated_sqlite
    with pytest.raises(IntegrityError, match="ck_source_versions_version_positive"):
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO source_versions (source_version_id, version_number, sha256) "
                    "VALUES ('s1', 0, 'hash')"
                )
            )


def test_valid_evidence_and_role_rows_still_insert_cleanly_on_sqlite(migrated_sqlite):
    """Negative control: the constraints reject bad data without also
    rejecting the legitimate values every existing test/seed path uses."""
    engine, _ = migrated_sqlite
    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys=OFF"))
        connection.execute(
            text(
                "INSERT INTO role_targets (target_id, framework_version, role, competency_id, "
                "target_level, source, valid_from, valid_to) VALUES "
                "('t3', 'v1', 'role', 'comp', 5, 'test', '2026-01-01', NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO evidence_records (evidence_id, player_id, competency_id, "
                "evidence_type, value) VALUES ('e2', 'ghost', 'comp', 'observed_practice', 0)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO evidence_records (evidence_id, player_id, competency_id, "
                "evidence_type, value) VALUES ('e3', 'ghost', 'comp', 'reviewer', NULL)"
            )
        )
        connection.execute(
            text(
                "INSERT INTO source_versions (source_version_id, version_number, sha256) "
                "VALUES ('s2', 1, 'hash')"
            )
        )


# --- Live PostgreSQL parity --------------------------------------------------


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
            f"(localhost:55432) -- skipping the Package 4 PostgreSQL parity contract: {exc}"
        )


@contextlib.contextmanager
def _disposable_migrated_postgres_database(*, revision: str = "head"):
    database_name = f"sih_pkg4_{uuid.uuid4().hex[:12]}"
    probe = create_engine(_ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    created = False
    try:
        with probe.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        created = True
        database_url = normalize_database_url(
            f"postgresql://prism_app:prism_dev_local_only@localhost:55432/{database_name}"
        )
        _run_alembic(database_url, "upgrade", revision)
        yield database_url
    finally:
        probe.dispose()
        if created:
            cleanup = create_engine(_ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
            try:
                with cleanup.connect() as connection:
                    connection.execute(
                        text(
                            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                            "WHERE datname = :name AND pid <> pg_backend_pid()"
                        ),
                        {"name": database_name},
                    )
                    connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
            finally:
                cleanup.dispose()


def test_migration_creates_all_six_indexes_on_postgresql():
    _skip_unless_postgres_reachable()
    with _disposable_migrated_postgres_database() as database_url:
        engine = create_engine(database_url)
        inspector = inspect(engine)
        for table, expected in _EXPECTED_INDEXES.items():
            actual = {index["name"]: index["column_names"] for index in inspector.get_indexes(table)}
            for name, columns in expected.items():
                assert name in actual, f"missing index {name} on {table}"
                assert actual[name] == columns
        engine.dispose()


def test_check_constraint_rejects_invalid_role_target_level_on_postgresql():
    _skip_unless_postgres_reachable()
    with _disposable_migrated_postgres_database() as database_url:
        engine = create_engine(database_url)
        with pytest.raises(IntegrityError, match="ck_role_targets_target_level_1_5"):
            with engine.begin() as connection:
                connection.execute(
                    text(
                        "INSERT INTO role_targets (target_id, framework_version, role, competency_id, "
                        "target_level, source) VALUES ('t1', 'v1', 'role', 'comp', 0, 'test')"
                    )
                )
        engine.dispose()


def test_preflight_rejects_upgrade_on_postgresql_when_existing_data_violates_a_constraint():
    _skip_unless_postgres_reachable()
    with _disposable_migrated_postgres_database(revision=_PARENT_REVISION) as database_url:
        engine = create_engine(database_url)
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO source_versions (source_version_id, version_number, sha256) "
                    "VALUES ('bad-source', 0, 'hash')"
                )
            )
        engine.dispose()

        result = _run_alembic(database_url, "upgrade", "head", check=False)
        assert result.returncode != 0
        assert "version_number below 1" in result.stdout + result.stderr


def test_alembic_check_reports_clean_after_upgrade_on_postgresql():
    _skip_unless_postgres_reachable()
    with _disposable_migrated_postgres_database() as database_url:
        result = _run_alembic(database_url, "check", check=False)
        assert result.returncode == 0
        assert "No new upgrade operations detected" in result.stdout + result.stderr
