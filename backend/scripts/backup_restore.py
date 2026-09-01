"""PostgreSQL backup/restore -- Package L.

This repository's host has no local pg_dump/pg_restore; the Postgres client
tools live inside the `postgres:16-alpine` container started by
docker-compose.dev.yml, which does ship them. Every function here shells out
to `docker exec`/`docker cp` against a named running container rather than
assuming a local Postgres client install -- this is what actually works in
this project's documented local-dev setup, not a claim about how a real
production backup pipeline would be operated (that needs Lane 6's
deployment/DR work, which this is explicitly not).

This module never runs against SQLite -- the local zero-setup demo profile's
backup story is "the app.db file", not this script.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from sqlalchemy.engine import make_url


class BackupRestoreError(RuntimeError):
    """Raised when a backup or restore step fails or returns a non-zero exit code."""


def _connection_parts(database_url: str) -> tuple[str, str, str, int, str]:
    """Return (user, password, host, port, dbname) parsed from DATABASE_URL.

    `host`/`port` are only used to confirm this isn't being pointed at
    SQLite -- the actual connection happens *inside* the container via
    `-h localhost`, since the dump/restore commands run inside the same
    container the database lives in.
    """
    url = make_url(database_url)
    if url.get_backend_name() != "postgresql":
        raise BackupRestoreError(
            f"backup_restore.py only supports PostgreSQL, got: {url.get_backend_name()!r}"
        )
    if not url.username or not url.database:
        raise BackupRestoreError("DATABASE_URL must include a username and a database name")
    return url.username, url.password or "", url.host or "localhost", url.port or 5432, url.database


def _run(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run(command, capture_output=True, text=True, env=env)
    if result.returncode != 0:
        raise BackupRestoreError(
            f"command failed ({result.returncode}): {' '.join(command)}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


def create_backup(container_name: str, database_url: str, output_path: str | Path) -> Path:
    """Dump `database_url`'s database (running inside `container_name`) to a
    local file at `output_path`, using pg_dump's custom format (compressed,
    supports selective/parallel restore -- the standard choice for anything
    beyond a toy `.sql` text dump).
    """
    username, password, _host, _port, dbname = _connection_parts(database_url)
    output_path = Path(output_path)
    container_dump_path = "/tmp/backup_restore_dump.pgdump"

    _run(
        [
            "docker", "exec",
            "-e", f"PGPASSWORD={password}",
            container_name,
            "pg_dump",
            "-h", "localhost",
            "-U", username,
            "-d", dbname,
            "--format=custom",
            "--file", container_dump_path,
        ]
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _run(["docker", "cp", f"{container_name}:{container_dump_path}", str(output_path)])
    _run(["docker", "exec", container_name, "rm", "-f", container_dump_path])

    if not output_path.exists() or output_path.stat().st_size == 0:
        raise BackupRestoreError(f"backup file was not produced or is empty: {output_path}")
    return output_path


def restore_backup(
    container_name: str, database_url: str, input_path: str | Path, *, clean: bool = True
) -> None:
    """Restore `input_path` (produced by create_backup) into the database
    named in `database_url`, inside `container_name`.

    `clean=True` (default) passes pg_restore's `--clean --if-exists`, which
    drops each object before recreating it -- the correct behavior for a
    restore drill (dump -> wipe -> restore -> verify) or a real disaster
    recovery onto an already-provisioned database. Pass `clean=False` only
    when restoring into a genuinely empty database.
    """
    username, password, _host, _port, dbname = _connection_parts(database_url)
    input_path = Path(input_path)
    if not input_path.exists():
        raise BackupRestoreError(f"backup file does not exist: {input_path}")

    container_dump_path = "/tmp/backup_restore_restore.pgdump"
    _run(["docker", "cp", str(input_path), f"{container_name}:{container_dump_path}"])

    command = [
        "docker", "exec",
        "-e", f"PGPASSWORD={password}",
        container_name,
        "pg_restore",
        "-h", "localhost",
        "-U", username,
        "-d", dbname,
        "--no-owner",
        "--no-privileges",
    ]
    if clean:
        command += ["--clean", "--if-exists"]
    command.append(container_dump_path)

    try:
        _run(command)
    finally:
        _run(["docker", "exec", container_name, "rm", "-f", container_dump_path])


def _main() -> None:
    import argparse
    import os

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "restore"])
    parser.add_argument("path", help="File to write to (backup) or read from (restore)")
    parser.add_argument("--container", default="sih-learning-postgres")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="Defaults to $DATABASE_URL",
    )
    parser.add_argument(
        "--no-clean", action="store_true", help="Restore without --clean --if-exists"
    )
    args = parser.parse_args()

    if not args.database_url:
        parser.error("--database-url is required (or set DATABASE_URL)")

    if args.action == "backup":
        result = create_backup(args.container, args.database_url, args.path)
        print(f"Backup written to {result} ({result.stat().st_size} bytes)")
    else:
        restore_backup(args.container, args.database_url, args.path, clean=not args.no_clean)
        print(f"Restored {args.path} into the database named in --database-url")


if __name__ == "__main__":
    _main()
