"""
Database configuration and session management.
"""
import os
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./skillquest.db")
_is_sqlite = "sqlite" in DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    echo=False,
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
    skillquest.db) needs this, or every query touching the new column raises
    "no such column" against pre-existing rows. Call once at startup, after
    create_all().
    """
    if "sqlite" not in DATABASE_URL:
        return
    with engine.connect() as conn:
        existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}
        for name, type_and_default in columns:
            if name not in existing:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {type_and_default}"))
        conn.commit()
