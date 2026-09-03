"""Focused tests for Lane 2 database selection and migration readiness."""

import pytest
from sqlalchemy import create_engine, text

import db.database as database_module
from db.database import (
    database_revision,
    ensure_columns,
    get_db,
    is_sqlite_database,
    migration_head_revision,
    normalize_database_url,
    require_database_at_migration_head,
)


def test_sqlite_database_url_is_unchanged():
    assert normalize_database_url("sqlite:///./app.db") == "sqlite:///./app.db"


def test_standard_postgresql_url_selects_psycopg_3():
    assert (
        normalize_database_url("postgresql://user:pass@db.example/prism")
        == "postgresql+psycopg://user:pass@db.example/prism"
    )


def test_legacy_postgres_url_selects_psycopg_3():
    assert (
        normalize_database_url("postgres://user:pass@db.example/prism")
        == "postgresql+psycopg://user:pass@db.example/prism"
    )


def test_explicit_postgresql_driver_is_preserved():
    url = "postgresql+psycopg://user:pass@db.example/prism"
    assert normalize_database_url(url) == url


def test_identity_binding_revision_is_the_single_migration_head():
    assert migration_head_revision() == "6564595b3466"


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
    with pytest.raises(RuntimeError, match="required=6564595b3466"):
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
        match="current=2baf7d4bd8a2, required=6564595b3466",
    ):
        require_database_at_migration_head(bind)


def test_database_at_head_is_accepted():
    bind = create_engine("sqlite:///:memory:")
    with bind.begin() as connection:
        connection.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES ('6564595b3466')")
        )

    require_database_at_migration_head(bind)


def test_migration_head_revision_rejects_more_than_one_head(monkeypatch):
    """A branched/unmerged migration chain (two heads) must fail loudly here
    rather than silently pick one -- the same "never guess" principle every
    other ambiguous-state check in this module follows."""

    class _FakeScriptDirectory:
        def get_heads(self):
            return ["revision-a", "revision-b"]

    monkeypatch.setattr(
        database_module.ScriptDirectory, "from_config", lambda config: _FakeScriptDirectory()
    )

    with pytest.raises(RuntimeError, match="Expected one Alembic head, found 2"):
        migration_head_revision()


# --- is_sqlite_database() ---


def test_is_sqlite_database_reflects_the_configured_backend():
    # The module is imported under whatever DATABASE_URL this test process
    # actually has (SQLite by default -- see should_seed_demo_data's own
    # test file for the exact default), so this asserts internal
    # consistency against the module's own private flag rather than
    # hardcoding an assumption about the test environment.
    assert is_sqlite_database() == database_module._is_sqlite


# --- get_db() ---


def test_get_db_yields_a_working_session_and_closes_it_on_generator_exhaustion(monkeypatch):
    closed = {"called": False}
    real_session = database_module.SessionLocal()
    original_close = real_session.close

    def _spy_close():
        closed["called"] = True
        original_close()

    monkeypatch.setattr(real_session, "close", _spy_close)
    monkeypatch.setattr(database_module, "SessionLocal", lambda: real_session)

    generator = get_db()
    session = next(generator)
    assert session is real_session
    session.execute(text("SELECT 1"))  # a genuinely usable session, not just a truthy object
    assert closed["called"] is False  # not closed while still in use

    with pytest.raises(StopIteration):
        next(generator)

    # The meaningful assertion: the generator's `finally: db.close()` really
    # ran on exhaustion, not just that iteration stopped -- a bare "did it
    # stop raising" would also pass if close() were accidentally removed.
    assert closed["called"] is True


# --- ensure_columns() ---


def test_ensure_columns_adds_a_missing_column_on_sqlite(monkeypatch, tmp_path):
    sqlite_engine = create_engine(f"sqlite:///{(tmp_path / 'ensure_columns.db').as_posix()}")
    with sqlite_engine.begin() as connection:
        connection.execute(text("CREATE TABLE widgets (widget_id VARCHAR PRIMARY KEY)"))

    monkeypatch.setattr(database_module, "_is_sqlite", True)
    monkeypatch.setattr(database_module, "engine", sqlite_engine)

    ensure_columns("widgets", [("color", "TEXT DEFAULT 'unpainted'")])

    with sqlite_engine.connect() as connection:
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(widgets)"))}
    assert "color" in columns
    sqlite_engine.dispose()


def test_ensure_columns_does_not_duplicate_an_already_present_column(monkeypatch, tmp_path):
    """Calling ensure_columns() twice (e.g. two startups against the same
    demo file) must be idempotent -- SQLite raises on ADD COLUMN for a name
    that already exists, so a bug here would break every second app start,
    not just look redundant."""
    sqlite_engine = create_engine(f"sqlite:///{(tmp_path / 'ensure_columns_twice.db').as_posix()}")
    with sqlite_engine.begin() as connection:
        connection.execute(text("CREATE TABLE widgets (widget_id VARCHAR PRIMARY KEY)"))

    monkeypatch.setattr(database_module, "_is_sqlite", True)
    monkeypatch.setattr(database_module, "engine", sqlite_engine)

    ensure_columns("widgets", [("color", "TEXT DEFAULT 'unpainted'")])
    ensure_columns("widgets", [("color", "TEXT DEFAULT 'unpainted'")])  # must not raise

    with sqlite_engine.connect() as connection:
        columns = [row[1] for row in connection.execute(text("PRAGMA table_info(widgets)"))]
    assert columns.count("color") == 1
    sqlite_engine.dispose()


def test_ensure_columns_is_a_no_op_on_postgresql(monkeypatch, tmp_path):
    """Postgres is migration-managed; ensure_columns() must never attempt a
    schema change there, even if called -- verified here by pointing the
    module's `_is_sqlite` flag at False and confirming the (deliberately
    still-SQLite) engine it's paired with is never touched."""
    sqlite_engine = create_engine(f"sqlite:///{(tmp_path / 'never_touched.db').as_posix()}")
    with sqlite_engine.begin() as connection:
        connection.execute(text("CREATE TABLE widgets (widget_id VARCHAR PRIMARY KEY)"))

    monkeypatch.setattr(database_module, "_is_sqlite", False)
    monkeypatch.setattr(database_module, "engine", sqlite_engine)

    ensure_columns("widgets", [("color", "TEXT DEFAULT 'unpainted'")])

    with sqlite_engine.connect() as connection:
        columns = {row[1] for row in connection.execute(text("PRAGMA table_info(widgets)"))}
    assert "color" not in columns
    sqlite_engine.dispose()
