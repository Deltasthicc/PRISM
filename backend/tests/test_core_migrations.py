"""Regression tests for the complete Alembic chain and legacy-table adoption."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy import create_engine, inspect, text


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
BASELINE_REVISION = "65bc8695fadc"
GOVERNANCE_REVISION = "2baf7d4bd8a2"
IDENTITY_REVISION = "cf4271f204a3"
HEAD_REVISION = "036de46dd515"
GOVERNANCE_TABLES = {
    "audit_events",
    "evidence_records",
    "role_targets",
    "source_versions",
}
IDENTITY_TABLES = {"identity_bindings"}


def _database_url(path: Path) -> str:
    return f"sqlite:///{path.as_posix()}"


def _run_python(database_url: str, *arguments: str) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=BACKEND_DIRECTORY,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def _run_alembic(
    database_url: str, *arguments: str, succeeds: bool = True
) -> subprocess.CompletedProcess[str]:
    result = _run_python(database_url, "-m", "alembic", *arguments)
    if succeeds and result.returncode != 0:
        raise AssertionError(f"Alembic failed:\n{result.stdout}\n{result.stderr}")
    return result


def test_full_migration_chain_upgrades_and_downgrades_fresh_database(tmp_path):
    database_url = _database_url(tmp_path / "fresh.db")

    _run_alembic(database_url, "upgrade", "head")
    engine = create_engine(database_url)
    names = set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert revision == HEAD_REVISION
    assert GOVERNANCE_TABLES <= names
    assert IDENTITY_TABLES <= names
    assert len(names) == 18

    _run_alembic(database_url, "downgrade", "base")
    assert inspect(engine).get_table_names() == ["alembic_version"]
    engine.dispose()


def test_followup_adopts_compatible_tables_from_legacy_create_all(tmp_path):
    database_url = _database_url(tmp_path / "legacy.db")
    _run_alembic(database_url, "upgrade", BASELINE_REVISION)

    create_result = _run_python(
        database_url,
        "-c",
        (
            "from db.database import Base, engine; "
            "from models.governance import AuditEvent, EvidenceRecord, RoleTarget, SourceVersion; "
            "from models.learning import LearningMaterial; from models.player import Player; "
            "Base.metadata.create_all(engine, tables=[AuditEvent.__table__, "
            "EvidenceRecord.__table__, RoleTarget.__table__, SourceVersion.__table__])"
        ),
    )
    assert create_result.returncode == 0, create_result.stderr

    _run_alembic(database_url, "upgrade", "head")
    _run_alembic(database_url, "check")
    engine = create_engine(database_url)
    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert revision == HEAD_REVISION
    assert GOVERNANCE_TABLES <= set(inspect(engine).get_table_names())
    engine.dispose()


def test_identity_followup_downgrades_without_removing_governance(tmp_path):
    database_url = _database_url(tmp_path / "identity-downgrade.db")
    _run_alembic(database_url, "upgrade", "head")
    engine = create_engine(database_url)

    _run_alembic(database_url, "downgrade", GOVERNANCE_REVISION)
    names = set(inspect(engine).get_table_names())
    with engine.connect() as connection:
        revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()

    assert revision == GOVERNANCE_REVISION
    assert GOVERNANCE_TABLES <= names
    assert IDENTITY_TABLES.isdisjoint(names)
    engine.dispose()


def test_followup_rejects_partial_preexisting_governance_schema(tmp_path):
    database_url = _database_url(tmp_path / "partial.db")
    _run_alembic(database_url, "upgrade", BASELINE_REVISION)
    engine = create_engine(database_url)
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE audit_events (audit_id VARCHAR PRIMARY KEY)"))

    result = _run_alembic(database_url, "upgrade", "head", succeeds=False)
    combined_output = result.stdout + result.stderr
    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    assert result.returncode != 0
    assert "Refusing to adopt a partial governance schema" in combined_output
    assert revision == BASELINE_REVISION
    engine.dispose()
