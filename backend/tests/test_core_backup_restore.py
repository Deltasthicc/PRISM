"""Tests for scripts/backup_restore.py.

Covers the pure-logic parts (URL parsing, error handling) without Docker, so
this suite runs everywhere. The actual backup/restore drill against a real
Postgres container is run manually and its evidence recorded in
LANE2_SYNC.md, same precedent as every other Docker-dependent verification
in this project (SEED_DEMO_DATA, the Alembic migrations, Keycloak).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts.backup_restore import BackupRestoreError, _connection_parts, restore_backup


def test_connection_parts_extracts_from_a_postgres_url():
    username, password, host, port, dbname = _connection_parts(
        "postgresql://sih_app:sih_dev_local_only@localhost:55432/sih_learning_tool"
    )
    assert username == "sih_app"
    assert password == "sih_dev_local_only"
    assert host == "localhost"
    assert port == 55432
    assert dbname == "sih_learning_tool"


def test_connection_parts_rejects_sqlite():
    with pytest.raises(BackupRestoreError, match="only supports PostgreSQL"):
        _connection_parts("sqlite:///./app.db")


def test_connection_parts_requires_username_and_database():
    with pytest.raises(BackupRestoreError, match="username and a database name"):
        _connection_parts("postgresql://localhost:5432/")


def test_restore_backup_rejects_a_missing_file(tmp_path):
    missing = tmp_path / "does-not-exist.pgdump"
    with pytest.raises(BackupRestoreError, match="does not exist"):
        restore_backup(
            "sih-learning-postgres",
            "postgresql://sih_app:x@localhost:55432/sih_learning_tool",
            missing,
        )


def test_restore_backup_checks_file_existence_before_touching_docker(tmp_path, monkeypatch):
    # A missing file must fail fast, before any docker/subprocess call --
    # confirmed by making _run raise if it's ever invoked in this case.
    def _run_should_not_be_called(*args, **kwargs):
        raise AssertionError("_run must not be called when the backup file is missing")

    monkeypatch.setattr("scripts.backup_restore._run", _run_should_not_be_called)
    missing = tmp_path / "nope.pgdump"
    with pytest.raises(BackupRestoreError):
        restore_backup(
            "sih-learning-postgres",
            "postgresql://sih_app:x@localhost:55432/sih_learning_tool",
            missing,
        )
