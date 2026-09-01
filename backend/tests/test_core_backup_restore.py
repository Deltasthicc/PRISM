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

from scripts.backup_restore import (
    BackupRestoreError,
    _connection_parts,
    _redact,
    _run,
    create_backup,
    restore_backup,
)

REAL_URL = "postgresql://sih_app:sih_dev_local_only@localhost:55432/sih_learning_tool"


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


def test_connection_parts_rejects_a_remote_looking_host():
    # This module only ever execs into the named local container and runs
    # `-h localhost` inside it; a DATABASE_URL naming a different host must
    # not be silently ignored in favor of acting on localhost anyway.
    with pytest.raises(BackupRestoreError, match="not a supported local host"):
        _connection_parts("postgresql://user:pass@remote.example:6543/prod")


def test_connection_parts_rejects_a_malformed_port_without_a_raw_valueerror():
    # sqlalchemy.engine.make_url() parses the port eagerly and raises a bare
    # ValueError for a non-numeric port -- this must surface as
    # BackupRestoreError like every other parsing failure, not leak past it.
    with pytest.raises(BackupRestoreError, match="not a valid URL"):
        _connection_parts("postgresql://user:pass@localhost:bad/db")


def test_connection_parts_rejects_a_mismatched_port_on_localhost():
    # This module always execs into the named container and connects to its
    # internal Postgres on -h localhost, ignoring whatever port the caller's
    # DATABASE_URL actually names -- so a URL naming a port other than the
    # documented local-compose mapping (55432) must not be silently accepted
    # and quietly run against the container's own database anyway.
    with pytest.raises(BackupRestoreError, match="does not match the documented local-compose port"):
        _connection_parts("postgresql://sih_app:pw@localhost:9999/sih_learning_tool")


def test_connection_parts_rejects_a_missing_port():
    with pytest.raises(BackupRestoreError, match="does not match the documented local-compose port"):
        _connection_parts("postgresql://sih_app:pw@localhost/sih_learning_tool")


def test_redact_hides_the_pgpassword_value():
    command = ["docker", "exec", "-e", "PGPASSWORD=super-secret", "container", "pg_dump"]
    redacted = _redact(command)
    assert "super-secret" not in redacted
    assert "PGPASSWORD=***REDACTED***" in redacted
    # Every other argument is untouched.
    assert redacted[0] == "docker"
    assert redacted[-1] == "pg_dump"


def test_run_failure_message_does_not_leak_the_password(monkeypatch):
    class _FakeResult:
        returncode = 1
        stdout = ""
        stderr = "synthetic failure"

    monkeypatch.setattr(
        "scripts.backup_restore.subprocess.run", lambda *a, **k: _FakeResult()
    )
    with pytest.raises(BackupRestoreError) as excinfo:
        _run(["docker", "exec", "-e", "PGPASSWORD=SYNTHETIC_REVIEW_SECRET", "container", "pg_dump"])
    assert "SYNTHETIC_REVIEW_SECRET" not in str(excinfo.value)
    assert "REDACTED" in str(excinfo.value)


def test_restore_backup_rejects_an_invalid_archive_without_running_clean(monkeypatch):
    # The pg_restore --list preflight must reject a bad archive before the
    # destructive pg_restore --clean step ever runs.
    calls = []

    def _fake_run(command, **kwargs):
        calls.append(command)
        if "cp" in command or "rm" in command:
            return None  # copying the archive in, and cleanup, always succeed here
        if "--list" in command:
            raise BackupRestoreError("command failed (1): synthetic corrupt archive")
        raise AssertionError(f"destructive restore must not run after a failed preflight: {command}")

    monkeypatch.setattr("scripts.backup_restore._run", _fake_run)
    dump = Path(__file__)  # any existing file; content is irrelevant, _run is faked
    with pytest.raises(BackupRestoreError, match="not a valid pg_dump custom-format archive"):
        restore_backup(
            "sih-learning-postgres",
            "postgresql://sih_app:x@localhost:55432/sih_learning_tool",
            dump,
        )
    # docker cp + the --list preflight ran; the destructive restore did not,
    # and cleanup was still attempted.
    joined = [" ".join(c) for c in calls]
    assert any("pg_restore --list" in c for c in joined)
    assert any("rm -f" in c for c in joined)
    assert not any("--clean" in c for c in joined)


def test_restore_backup_does_not_let_cleanup_failure_mask_the_primary_error(monkeypatch):
    def _fake_run(command, **kwargs):
        if "cp" in command or "--list" in command:
            return None  # copying the archive in and the preflight both pass
        if "rm" in command:
            raise BackupRestoreError("cleanup also failed (synthetic)")
        raise BackupRestoreError("PRIMARY pg_restore failure (synthetic)")

    monkeypatch.setattr("scripts.backup_restore._run", _fake_run)
    dump = Path(__file__)
    with pytest.raises(BackupRestoreError, match="PRIMARY pg_restore failure"):
        restore_backup(
            "sih-learning-postgres",
            "postgresql://sih_app:x@localhost:55432/sih_learning_tool",
            dump,
        )


def test_restore_backup_surfaces_a_cleanup_failure_after_a_successful_restore(monkeypatch):
    # There is no primary failure to protect here -- a cleanup failure after
    # an otherwise-successful restore is real information (a leftover
    # container-side temp file) and must not be silently swallowed.
    def _fake_run(command, **kwargs):
        if "rm" in command:
            raise BackupRestoreError("cleanup failed after a successful restore (synthetic)")
        return None  # cp, --list preflight, and the actual restore all succeed

    monkeypatch.setattr("scripts.backup_restore._run", _fake_run)
    dump = Path(__file__)
    with pytest.raises(BackupRestoreError, match="cleanup failed after a successful restore"):
        restore_backup("sih-learning-postgres", REAL_URL, dump)


def test_restore_backup_command_includes_atomicity_flags(monkeypatch):
    captured = {}

    def _fake_run(command, **kwargs):
        if "pg_restore" in command and "--list" not in command:
            captured["command"] = command
            captured["env"] = kwargs.get("env")
        return None

    monkeypatch.setattr("scripts.backup_restore._run", _fake_run)
    dump = Path(__file__)
    restore_backup("sih-learning-postgres", REAL_URL, dump)

    assert "--exit-on-error" in captured["command"]
    assert "--single-transaction" in captured["command"]


def test_restore_backup_passes_password_via_environment_not_argv(monkeypatch):
    captured = {}

    def _fake_run(command, **kwargs):
        if "pg_restore" in command and "--list" not in command:
            captured["command"] = command
            captured["env"] = kwargs.get("env")
        return None

    monkeypatch.setattr("scripts.backup_restore._run", _fake_run)
    dump = Path(__file__)
    restore_backup("sih-learning-postgres", REAL_URL, dump)

    joined = " ".join(captured["command"])
    assert "sih_dev_local_only" not in joined
    assert "-e" in captured["command"] and "PGPASSWORD" in captured["command"]
    assert captured["env"]["PGPASSWORD"] == "sih_dev_local_only"


def test_create_backup_passes_password_via_environment_not_argv(monkeypatch, tmp_path):
    captured = {}

    def _fake_run(command, **kwargs):
        if "pg_dump" in command:
            captured["command"] = command
            captured["env"] = kwargs.get("env")
        return None

    monkeypatch.setattr("scripts.backup_restore._run", _fake_run)
    output = tmp_path / "out.pgdump"
    output.write_bytes(b"fake dump bytes")  # create_backup checks the file is non-empty afterward

    create_backup("sih-learning-postgres", REAL_URL, output)

    joined = " ".join(captured["command"])
    assert "sih_dev_local_only" not in joined
    assert "-e" in captured["command"] and "PGPASSWORD" in captured["command"]
    assert captured["env"]["PGPASSWORD"] == "sih_dev_local_only"


def test_create_backup_cleans_up_the_container_dump_on_a_docker_cp_failure(monkeypatch, tmp_path):
    calls = []

    def _fake_run(command, **kwargs):
        calls.append(command)
        if "cp" in command:
            raise BackupRestoreError("docker cp failed (synthetic)")
        return None

    monkeypatch.setattr("scripts.backup_restore._run", _fake_run)
    with pytest.raises(BackupRestoreError, match="docker cp failed"):
        create_backup("sih-learning-postgres", REAL_URL, tmp_path / "wont-be-created.pgdump")

    joined = [" ".join(c) for c in calls]
    assert any("rm -f" in c for c in joined), "the leftover container-side dump must be cleaned up"


def test_create_backup_surfaces_a_cleanup_failure_after_a_successful_backup(monkeypatch, tmp_path):
    def _fake_run(command, **kwargs):
        if "rm" in command:
            raise BackupRestoreError("cleanup failed after a successful backup (synthetic)")
        return None  # pg_dump and docker cp both succeed

    monkeypatch.setattr("scripts.backup_restore._run", _fake_run)
    output = tmp_path / "out.pgdump"
    output.write_bytes(b"fake dump bytes")

    with pytest.raises(BackupRestoreError, match="cleanup failed after a successful backup"):
        create_backup("sih-learning-postgres", REAL_URL, output)
