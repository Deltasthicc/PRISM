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

import os
import subprocess
import uuid
from pathlib import Path

from sqlalchemy.exc import ArgumentError
from sqlalchemy.engine import make_url

# The only hosts for which "run pg_dump/pg_restore inside the named
# container, against its own -h localhost" is actually the database
# DATABASE_URL describes. Anything else (a remote hostname, a different
# container's service name) would silently execute against the wrong
# database while claiming to have backed up/restored the configured one --
# fail closed instead of guessing.
_SUPPORTED_LOCAL_HOSTS = {"localhost", "127.0.0.1"}

# docker-compose.dev.yml maps the container's Postgres port 5432 to this
# fixed host port ("55432:5432"), and .env.example's documented Postgres
# DATABASE_URL uses it exactly. A DATABASE_URL naming any other port is
# describing a different mapping than the one this module actually talks to
# (it always execs into the container and connects to its internal 5432 via
# `-h localhost`), so a mismatched port is the same class of configuration
# error as a mismatched host and must fail closed the same way.
_SUPPORTED_LOCAL_PORT = 55432
_DEFAULT_CONTAINER_NAME = "prism-postgres"


class BackupRestoreError(RuntimeError):
    """Raised when a backup or restore step fails or returns a non-zero exit code."""


def _redact(command: list[str]) -> list[str]:
    """Return `command` with any `PGPASSWORD=...` argument's value hidden."""
    return [
        "PGPASSWORD=***REDACTED***" if part.startswith("PGPASSWORD=") else part
        for part in command
    ]


def _connection_parts(database_url: str) -> tuple[str, str, str, int, str]:
    """Return (user, password, host, port, dbname) parsed from DATABASE_URL.

    Both `host` and `port` are enforced, not just parsed for display: this
    module only ever execs into a named local container and connects to its
    internal Postgres via `-h localhost`, so a DATABASE_URL naming any other
    host, or any port besides the documented local-compose mapping, is a
    configuration mismatch -- not something to silently ignore and act on
    the named container's own database anyway.
    """
    try:
        url = make_url(database_url)
    except (ArgumentError, ValueError) as exc:
        raise BackupRestoreError(f"DATABASE_URL is not a valid URL: {exc}") from exc
    if url.get_backend_name() != "postgresql":
        raise BackupRestoreError(
            f"backup_restore.py only supports PostgreSQL, got: {url.get_backend_name()!r}"
        )
    if not url.username or not url.database:
        raise BackupRestoreError("DATABASE_URL must include a username and a database name")
    host = url.host or "localhost"
    if host not in _SUPPORTED_LOCAL_HOSTS:
        raise BackupRestoreError(
            f"DATABASE_URL host {host!r} is not a supported local host "
            f"({sorted(_SUPPORTED_LOCAL_HOSTS)}); this module only operates on the named "
            "docker-compose container's own local Postgres and refuses to silently run "
            "against a different host than the one DATABASE_URL names"
        )
    port = url.port
    if port != _SUPPORTED_LOCAL_PORT:
        raise BackupRestoreError(
            f"DATABASE_URL port {port!r} does not match the documented local-compose port "
            f"{_SUPPORTED_LOCAL_PORT} (docker-compose.dev.yml maps \"{_SUPPORTED_LOCAL_PORT}:5432\"); "
            "this module always connects inside the named container regardless of the port "
            "given, so a mismatched port means DATABASE_URL is not actually describing this "
            "docker-compose stack -- refusing to silently run against it anyway"
        )
    return url.username, url.password or "", host, port, url.database


def _run(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    try:
        result = subprocess.run(command, capture_output=True, text=True, env=env)
    except FileNotFoundError as exc:
        # e.g. the `docker` binary itself isn't on PATH -- every other
        # failure mode in this module raises BackupRestoreError, so this
        # one should too rather than leaking a raw FileNotFoundError past
        # the module's documented exception contract.
        raise BackupRestoreError(f"command not found: {command[0]!r} ({exc})") from exc
    if result.returncode != 0:
        raise BackupRestoreError(
            f"command failed ({result.returncode}): {' '.join(_redact(command))}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result


def _unique_container_path(prefix: str) -> str:
    """Return a per-operation, collision-safe temp path inside the container.

    Both create_backup() and restore_backup() used to write to a single
    process-global fixed path (e.g. /tmp/backup_restore_dump.pgdump).
    Concurrent invocations -- two backups, two restores, or a backup and a
    restore running at once against the same container -- could then
    overwrite, copy, or delete each other's archive mid-operation. A random
    suffix per call makes that impossible without needing any locking.
    """
    return f"/tmp/backup_restore_{prefix}_{uuid.uuid4().hex}.pgdump"


def _pgpassword_env(password: str) -> dict[str, str]:
    """Build a subprocess environment carrying PGPASSWORD as an env var only.

    `docker exec -e PGPASSWORD` (bare, no `=value`) makes the Docker CLI
    forward *its own* process's PGPASSWORD into the container -- so pairing
    that bare flag with this environment means the password is never a
    literal value in this process's argv (which any other local user can
    read via `ps`/`/proc/<pid>/cmdline` on Linux, or Task Manager's command
    line column on Windows), only in its environment block. `_redact()` on
    the command list is no longer the only thing standing between the
    secret and an exception message with this in place; the secret string
    simply never appears in `command` at all.
    """
    return {**os.environ, "PGPASSWORD": password}


def create_backup(container_name: str, database_url: str, output_path: str | Path) -> Path:
    """Dump `database_url`'s database (running inside `container_name`) to a
    local file at `output_path`, using pg_dump's custom format (compressed,
    supports selective/parallel restore -- the standard choice for anything
    beyond a toy `.sql` text dump).
    """
    username, password, _host, _port, dbname = _connection_parts(database_url)
    output_path = Path(output_path)
    container_dump_path = _unique_container_path("dump")

    def _cleanup_dump(*, suppress: bool) -> None:
        # Same primary-error-preserving discipline as restore_backup: a
        # cleanup failure must never replace a primary pg_dump/docker cp
        # failure, but on the success path an actual cleanup failure (a
        # leftover container-side temp file) must still surface rather than
        # being silently swallowed.
        try:
            _run(["docker", "exec", container_name, "rm", "-f", container_dump_path])
        except BackupRestoreError:
            if not suppress:
                raise

    try:
        _run(
            [
                "docker", "exec",
                "-e", "PGPASSWORD",
                container_name,
                "pg_dump",
                "-h", "localhost",
                "-U", username,
                "-d", dbname,
                "--format=custom",
                "--file", container_dump_path,
            ],
            env=_pgpassword_env(password),
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        _run(["docker", "cp", f"{container_name}:{container_dump_path}", str(output_path)])
    except Exception:
        # pg_dump may have written a partial file inside the container even
        # if `docker cp` (or something after it) then fails -- clean it up
        # without letting that cleanup mask the real failure.
        _cleanup_dump(suppress=True)
        raise
    _cleanup_dump(suppress=False)

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

    container_dump_path = _unique_container_path("restore")

    def _cleanup_archive(*, suppress: bool) -> None:
        # A cleanup failure must never replace a primary restore failure --
        # that would surface "rm: No such file" as the reported error and
        # hide the actual problem, so the exception-path caller passes
        # suppress=True. On the success path there is no primary failure to
        # protect, so a genuine cleanup failure (a leftover container-side
        # temp file) must surface instead of being silently swallowed.
        try:
            _run(["docker", "exec", container_name, "rm", "-f", container_dump_path])
        except BackupRestoreError:
            if not suppress:
                raise

    try:
        # Copying the archive INTO the container must be inside this
        # cleanup-protected scope too: if it fails partway through (a
        # partial transfer), the container can be left holding a partial
        # archive at container_dump_path with nothing to remove it.
        _run(["docker", "cp", str(input_path), f"{container_name}:{container_dump_path}"])

        # Non-destructive preflight: `--list` only reads the archive's table
        # of contents, so a corrupt/truncated/non-pg_dump file is rejected
        # here, before `--clean` has dropped a single object in the target
        # database.
        try:
            _run(["docker", "exec", container_name, "pg_restore", "--list", container_dump_path])
        except BackupRestoreError as exc:
            raise BackupRestoreError(
                f"restore aborted: {input_path} is not a valid pg_dump custom-format "
                f"archive readable by pg_restore --list ({exc})"
            ) from exc

        command = [
            "docker", "exec",
            "-e", "PGPASSWORD",
            container_name,
            "pg_restore",
            "-h", "localhost",
            "-U", username,
            "-d", dbname,
            "--no-owner",
            "--no-privileges",
            "--exit-on-error",
            # --exit-on-error alone only stops at the first error; it does
            # not undo statements that already ran. --single-transaction
            # wraps the whole restore in one transaction so it is actually
            # atomic: either every statement applies, or (on any error) none
            # of them do.
            "--single-transaction",
        ]
        if clean:
            command += ["--clean", "--if-exists"]
        command.append(container_dump_path)

        _run(command, env=_pgpassword_env(password))
    except Exception:
        _cleanup_archive(suppress=True)
        raise
    _cleanup_archive(suppress=False)


def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["backup", "restore"])
    parser.add_argument("path", help="File to write to (backup) or read from (restore)")
    parser.add_argument("--container", default=_DEFAULT_CONTAINER_NAME)
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
