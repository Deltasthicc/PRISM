"""
Database configuration and session management.
"""
import os
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app.db")


def normalize_database_url(database_url: str) -> str:
    """Select psycopg 3 for conventional and legacy PostgreSQL URLs."""
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    if database_url.startswith("postgres://"):
        return database_url.replace("postgres://", "postgresql+psycopg://", 1)
    return database_url


SQLALCHEMY_DATABASE_URL = normalize_database_url(DATABASE_URL)
_database_backend = make_url(SQLALCHEMY_DATABASE_URL).get_backend_name()
_is_sqlite = _database_backend == "sqlite"
_is_postgresql = _database_backend == "postgresql"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    echo=False,
    pool_pre_ping=_is_postgresql,
)

if _is_sqlite:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):
        # WAL lets readers and the writer proceed concurrently instead of
        # blocking each other on SQLite's default rollback-journal locking --
        # every request here does a read then a write in the same handler.
        # synchronous=NORMAL is the standard, safe pairing with WAL (still
        # durable across an app crash; only risks the last transaction on a
        # full OS crash, which is an acceptable tradeoff for a local dev DB).
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

_BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]


def is_sqlite_database() -> bool:
    """Return whether the configured application database is SQLite."""
    return _is_sqlite


def migration_head_revision() -> str:
    """Return the repository's single Alembic head revision."""
    config = Config(str(_BACKEND_DIRECTORY / "alembic.ini"))
    config.set_main_option("script_location", str(_BACKEND_DIRECTORY / "migrations"))
    heads = ScriptDirectory.from_config(config).get_heads()
    if len(heads) != 1:
        raise RuntimeError(f"Expected one Alembic head, found {len(heads)}: {heads}")
    return heads[0]


def database_revision(bind: Engine = engine) -> str | None:
    """Read the database's current Alembic revision, or None if unversioned."""
    with bind.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def require_database_at_migration_head(bind: Engine = engine) -> None:
    """Refuse startup when a migration-managed database is not current."""
    expected = migration_head_revision()
    current = database_revision(bind)
    if current != expected:
        current_label = current or "unversioned"
        raise RuntimeError(
            "Database schema is not at the required Alembic revision "
            f"(current={current_label}, required={expected}). "
            "Run `python -m alembic upgrade head` before starting the API."
        )


def get_db():
    """FastAPI dependency that yields a DB session and auto-closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def ensure_columns(table: str, columns: list[tuple[str, str]]) -> None:
    """
    Add any of `columns` (name, SQL type/default clause) missing from `table`.

    Base.metadata.create_all() only creates tables that don't exist yet -- it
    never alters an existing table's schema. Any new column added to a model
    after the demo DB file already has that table (e.g. this repo's seeded
    app.db) needs this, or every query touching the new column raises
    "no such column" against pre-existing rows. Call once at startup, after
    create_all().
    """
    if not _is_sqlite:
        return
    with engine.connect() as conn:
        existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
        for name, type_and_default in columns:
            if name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {type_and_default}"))
        conn.commit()
