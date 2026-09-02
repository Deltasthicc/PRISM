"""Focused tests for Lane 2 database selection and migration readiness."""

import pytest
from sqlalchemy import create_engine, text

from db.database import (
    database_revision,
    migration_head_revision,
    normalize_database_url,
    require_database_at_migration_head,
)


def test_sqlite_database_url_is_unchanged():
    assert normalize_database_url("sqlite:///./app.db") == "sqlite:///./app.db"


def test_standard_postgresql_url_selects_psycopg_3():
    assert (
        normalize_database_url("postgresql://user:pass@db.example/skillquest")
        == "postgresql+psycopg://user:pass@db.example/skillquest"
    )


def test_legacy_postgres_url_selects_psycopg_3():
    assert (
        normalize_database_url("postgres://user:pass@db.example/skillquest")
        == "postgresql+psycopg://user:pass@db.example/skillquest"
    )


def test_explicit_postgresql_driver_is_preserved():
    url = "postgresql+psycopg://user:pass@db.example/skillquest"
    assert normalize_database_url(url) == url


def test_identity_binding_revision_is_the_single_migration_head():
    assert migration_head_revision() == "4631f204d4ba"


def test_unversioned_database_is_rejected_with_upgrade_instruction():
    bind = create_engine("sqlite:///:memory:")

    with pytest.raises(RuntimeError, match="current=unversioned") as exc_info:
        require_database_at_migration_head(bind)

    assert "python -m alembic upgrade head" in str(exc_info.value)


def test_baseline_only_database_is_rejected():
    bind = create_engine("sqlite:///:memory:")
    with bind.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('65bc8695fadc')")
        )

    assert database_revision(bind) == "65bc8695fadc"
    with pytest.raises(RuntimeError, match="required=4631f204d4ba"):
        require_database_at_migration_head(bind)


def test_governance_only_database_is_rejected_after_identity_migration():
    bind = create_engine("sqlite:///:memory:")
    with bind.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('2baf7d4bd8a2')")
        )

    with pytest.raises(
        RuntimeError,
        match="current=2baf7d4bd8a2, required=4631f204d4ba",
    ):
        require_database_at_migration_head(bind)


def test_database_at_head_is_accepted():
    bind = create_engine("sqlite:///:memory:")
    with bind.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('4631f204d4ba')")
        )

    require_database_at_migration_head(bind)
