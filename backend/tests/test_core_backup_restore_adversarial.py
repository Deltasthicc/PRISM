"""Independent Package L acceptance tests owned by Codex.

These tests intentionally exercise failure/concurrency behavior through the
public backup/restore functions and the subprocess boundary. They do not
depend on Claude's private helper names or implementation shape.
"""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Lock

import pytest

from scripts.backup_restore import (
    BackupRestoreError,
    _run,
    create_backup,
    restore_backup,
)


REAL_URL = (
    "postgresql://sih_app:sih_dev_local_only@localhost:55432/"
    "sih_learning_tool"
)
CONTAINER = "sih-learning-postgres"


def _is_docker_cp(command: list[str]) -> bool:
    return command[:2] == ["docker", "cp"]


def _is_container_cleanup(command: list[str]) -> bool:
    return command[:3] == ["docker", "exec", CONTAINER] and "rm" in command


def _destination_container_path(command: list[str]) -> str:
    container, separator, path = command[-1].partition(":")
    assert separator == ":"
    assert container == CONTAINER
    return path


def _assert_docker_safe_temp_path(path: str) -> None:
    assert re.fullmatch(r"/tmp/[A-Za-z0-9][A-Za-z0-9._-]*", path), path


def test_restore_copy_failure_attempts_exact_cleanup_without_masking_primary(
    monkeypatch,
):
    calls: list[list[str]] = []

    def _fake_run(command, **kwargs):
        calls.append(command)
        if _is_docker_cp(command):
            raise BackupRestoreError("PRIMARY docker cp failure after partial transfer")
        if _is_container_cleanup(command):
            raise BackupRestoreError("SECONDARY cleanup failure")
        return None

    monkeypatch.setattr("scripts.backup_restore._run", _fake_run)

    with pytest.raises(BackupRestoreError, match="PRIMARY docker cp failure"):
        restore_backup(CONTAINER, REAL_URL, Path(__file__))

    copy_command = next(command for command in calls if _is_docker_cp(command))
    copied_path = _destination_container_path(copy_command)
    cleanup_paths = [command[-1] for command in calls if _is_container_cleanup(command)]
    assert cleanup_paths == [copied_path]
    _assert_docker_safe_temp_path(copied_path)


def test_concurrent_backups_use_distinct_container_paths(monkeypatch, tmp_path):
    barrier = Barrier(2)
    lock = Lock()
    dump_paths: list[str] = []

    def _fake_run(command, **kwargs):
        if "pg_dump" in command:
            path = command[command.index("--file") + 1]
            with lock:
                dump_paths.append(path)
            barrier.wait(timeout=5)
        elif _is_docker_cp(command):
            Path(command[-1]).write_bytes(b"synthetic custom-format dump")
        return None

    monkeypatch.setattr("scripts.backup_restore._run", _fake_run)
    outputs = [tmp_path / "first.pgdump", tmp_path / "second.pgdump"]

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(create_backup, CONTAINER, REAL_URL, output)
            for output in outputs
        ]
        assert [future.result(timeout=10) for future in futures] == outputs

    assert len(dump_paths) == 2
    assert len(set(dump_paths)) == 2
    for path in dump_paths:
        _assert_docker_safe_temp_path(path)


def test_concurrent_restores_use_distinct_container_paths(monkeypatch, tmp_path):
    barrier = Barrier(2)
    lock = Lock()
    restore_paths: list[str] = []
    archive = tmp_path / "source.pgdump"
    archive.write_bytes(b"synthetic custom-format dump")

    def _fake_run(command, **kwargs):
        if _is_docker_cp(command):
            path = _destination_container_path(command)
            with lock:
                restore_paths.append(path)
            barrier.wait(timeout=5)
        return None

    monkeypatch.setattr("scripts.backup_restore._run", _fake_run)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(restore_backup, CONTAINER, REAL_URL, archive)
            for _ in range(2)
        ]
        assert [future.result(timeout=10) for future in futures] == [None, None]

    assert len(restore_paths) == 2
    assert len(set(restore_paths)) == 2
    for path in restore_paths:
        _assert_docker_safe_temp_path(path)


def test_missing_docker_executable_is_normalized(monkeypatch):
    def _missing_executable(*args, **kwargs):
        raise FileNotFoundError("docker executable is unavailable")

    monkeypatch.setattr(
        "scripts.backup_restore.subprocess.run",
        _missing_executable,
    )

    with pytest.raises(BackupRestoreError, match="docker executable is unavailable"):
        _run(["docker", "version"])
