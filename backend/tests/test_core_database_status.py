"""Tests for scripts/database_status.py -- Package W-B.

The privacy assertions here (`test_status_never_leaks_*`) are the point of
this file, not an afterthought: this tool exists specifically so other
lanes/operators can ask "what's the schema state" without ever seeing a
row's content, so every test that would catch a future accidental leak is
written as an executable fact, not a comment asking a reviewer to notice.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from db.database import Base, migration_head_revision
from models.accuracy_history import AccuracyHistory  # noqa: F401 -- relationship target
from models.dungeon import Dungeon, Room  # noqa: F401 -- relationship target
from models.governance import (  # noqa: F401 -- AuditEvent/RoleTarget/SourceVersion are relationship targets
    AuditEvent,
    EvidenceRecord,
    RoleTarget,
    SourceVersion,
)
from models.guild import Guild  # noqa: F401 -- relationship target
from models.identity import IdentityBinding  # noqa: F401 -- relationship target
from models.learning import (  # noqa: F401 -- GeneratedQuiz/LearnerProfile/LearningMaterial are relationship targets
    CompetencyAssessment,
    GeneratedQuiz,
    LearnerProfile,
    LearningMaterial,
)
from models.player import Player
from models.question import Question  # noqa: F401 -- relationship target
from models.session import GameSession  # noqa: F401 -- relationship target
from models.submission import AnswerSubmission  # noqa: F401 -- relationship target
from scripts import database_status as status_module
from scripts.database_status import (
    CONFIGURED_ENV_FLAGS,
    TABLE_COUNTERS,
    format_human,
    get_configured_flags,
    get_database_status,
    get_migration_status,
    get_table_row_counts,
    status_to_dict,
)

SECRET_LOOKING_VALUE = "s3cret-token-do-not-print-me"


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def empty_db():
    """A genuinely fresh database with zero tables -- not even
    `alembic_version`. Reproduces the fresh-clone crash Codex found in
    review: `get_table_row_counts` must report this, not raise."""
    engine = create_engine("sqlite:///:memory:")
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


@pytest.fixture
def partially_migrated_db(db):
    """Two tables dropped after a full create_all() -- simulates a database
    stamped at a revision whose migration never actually finished, or a
    demo file that predates a couple of newer models."""
    db.execute(text("DROP TABLE players"))
    db.execute(text("DROP TABLE audit_events"))
    db.commit()
    return db


def _set_alembic_version(db, revision: str) -> None:
    db.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
    db.execute(text("INSERT INTO alembic_version (version_num) VALUES (:rev)"), {"rev": revision})
    db.commit()


# ---------------------------------------------------------------------------
# Migration status
# ---------------------------------------------------------------------------


def test_unversioned_database_reports_not_at_head_without_raising(db):
    status = get_migration_status(db.get_bind())
    assert status.current_revision is None
    assert status.at_head is False
    assert status.head_revision == migration_head_revision()
    assert status.dialect == "sqlite"


def test_database_at_head_reports_at_head_true(db):
    head = migration_head_revision()
    _set_alembic_version(db, head)
    status = get_migration_status(db.get_bind())
    assert status.current_revision == head
    assert status.at_head is True


def test_database_behind_head_reports_at_head_false(db):
    _set_alembic_version(db, "0000000000ab")
    status = get_migration_status(db.get_bind())
    assert status.current_revision == "0000000000ab"
    assert status.at_head is False


def test_get_database_status_rejects_a_session_bound_to_a_bare_connection(db):
    # get_database_status takes a Session, not a Connection. Simulate a
    # Session whose get_bind() incorrectly returns a Connection (e.g. inside
    # someone else's open transaction) to prove the explicit type guard fires
    # instead of silently misreporting dialect from the wrong object.
    with db.get_bind().connect() as connection:

        class _FakeSessionWithConnectionBind:
            def get_bind(self):
                return connection

            def query(self, *_args, **_kwargs):  # pragma: no cover - not reached
                raise AssertionError("should not be queried before the bind check")

        with pytest.raises(TypeError, match="Engine"):
            get_database_status(_FakeSessionWithConnectionBind())


# ---------------------------------------------------------------------------
# Table row counts
# ---------------------------------------------------------------------------


def test_all_advertised_tables_start_at_zero(db):
    counts, missing = get_table_row_counts(db)
    assert set(counts) == set(TABLE_COUNTERS)
    assert all(count == 0 for count in counts.values())
    assert missing == []


def test_counts_reflect_inserted_rows_exactly(db):
    db.add_all(
        [
            Player(player_id="p1", username="alice"),
            Player(player_id="p2", username="bob"),
        ]
    )
    db.add(
        CompetencyAssessment(
            assessment_id="a1",
            player_id="p1",
            curriculum_slug="official-statistics",
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    )
    db.commit()

    counts, missing = get_table_row_counts(db)
    assert counts["players"] == 2
    assert counts["competency_assessments"] == 1
    # Untouched tables must remain zero, not silently drift.
    assert counts["role_targets"] == 0
    assert counts["audit_events"] == 0
    assert missing == []


def test_counts_only_ever_call_count_never_fetch_rows(db, monkeypatch):
    """A regression guard against someone "optimizing" this into a query
    that materializes rows (and therefore their content) before counting."""
    from sqlalchemy.orm import Query

    original_all = Query.all

    def _explode(self):  # pragma: no cover - only triggered on regression
        raise AssertionError("get_table_row_counts must never fetch full rows")

    monkeypatch.setattr(Query, "all", _explode)
    try:
        get_table_row_counts(db)
    finally:
        monkeypatch.setattr(Query, "all", original_all)


def test_get_table_row_counts_reports_missing_tables_instead_of_raising(empty_db):
    """Regression test for the fresh-clone crash Codex found on review:
    a database with zero tables must be reportable, not fatal."""
    counts, missing = get_table_row_counts(empty_db)
    assert counts == {}
    assert missing == sorted(TABLE_COUNTERS)


def test_get_table_row_counts_reports_a_partially_migrated_schema_correctly(
    partially_migrated_db,
):
    counts, missing = get_table_row_counts(partially_migrated_db)
    assert missing == sorted(["players", "audit_events"])
    assert "players" not in counts
    assert "audit_events" not in counts
    # Every still-present table is still counted normally, not skipped just
    # because two unrelated tables are missing.
    assert counts["role_targets"] == 0
    assert set(counts) == set(TABLE_COUNTERS) - {"players", "audit_events"}


# ---------------------------------------------------------------------------
# Configured-flag booleans (the actual secret value must never surface)
# ---------------------------------------------------------------------------


def test_blank_and_missing_env_vars_are_reported_as_not_set():
    flags = get_configured_flags({"DATABASE_URL": "", "OIDC_ISSUER": "   "})
    assert flags["DATABASE_URL"] is False
    assert flags["OIDC_ISSUER"] is False
    assert flags["GEMINI_API_KEY"] is False  # absent entirely


def test_non_blank_env_vars_are_reported_as_set():
    flags = get_configured_flags({"GEMINI_API_KEY": SECRET_LOOKING_VALUE})
    assert flags["GEMINI_API_KEY"] is True


def test_configured_flags_cover_exactly_the_documented_set():
    flags = get_configured_flags({})
    assert set(flags) == set(CONFIGURED_ENV_FLAGS)


def test_secret_value_never_appears_anywhere_in_full_status_output(db):
    status = get_database_status(
        db, env={"DATABASE_URL": f"postgresql://user:{SECRET_LOOKING_VALUE}@host/db"}
    )
    serialized = json.dumps(status_to_dict(status))
    assert SECRET_LOOKING_VALUE not in serialized
    assert status.configured["DATABASE_URL"] is True


# ---------------------------------------------------------------------------
# Full status: shape and the privacy allowlist
# ---------------------------------------------------------------------------

# Every key that may ever appear anywhere in a serialized DatabaseStatus.
# Adding a table to TABLE_COUNTERS or a flag to CONFIGURED_ENV_FLAGS is fine
# (those are known-safe key SETS, not literal keys) -- but a brand-new
# top-level field must be deliberately added here, or this test fails and
# forces a reviewer to look at what just started being reported.
_ALLOWED_TOP_LEVEL_KEYS = {
    "generated_at",
    "tenant_scope",
    "migration",
    "table_row_counts",
    "missing_tables",
    "configured",
}
_ALLOWED_MIGRATION_KEYS = {"dialect", "current_revision", "head_revision", "at_head"}

# Field names that must never appear anywhere in this tool's output, at any
# nesting level -- these are exactly the kinds of identifying/content fields
# this tool is not supposed to be able to see, drawn from the real
# subject-owned schema (models/learning.py, models/governance.py,
# models/identity.py) and common secret-shaped names. Deliberately excludes
# the bare substring "sub" (the OIDC subject claim): it collides with the
# legitimate "submissions" table label, so "subject_id" below is the real,
# precise check instead.
_FORBIDDEN_ANYWHERE = {
    "player_id",
    "username",
    "email",
    "self_ratings",
    "measured_scores",
    "skill_gaps",
    "detail",
    "value",
    "excerpt",
    "source_excerpt",
    "reason",
    "issuer",
    "subject_id",
    "token",
    "password",
    "api_key",
    "authorization",
    "content_text",
    "extracted_text",
}


def test_full_status_shape_matches_the_declared_allowlist(db):
    status = get_database_status(db)
    payload = status_to_dict(status)

    assert set(payload) == _ALLOWED_TOP_LEVEL_KEYS
    assert set(payload["migration"]) == _ALLOWED_MIGRATION_KEYS
    assert set(payload["table_row_counts"]) == set(TABLE_COUNTERS)
    assert set(payload["configured"]) == set(CONFIGURED_ENV_FLAGS)


def test_status_never_leaks_a_forbidden_field_name(db):
    db.add(Player(player_id="p1", username="alice"))
    db.add(
        EvidenceRecord(
            evidence_id="e1",
            player_id="p1",
            competency_id="os_sampling_design",
            evidence_type="self_report",
            detail="this must never appear in status output",
        )
    )
    db.commit()

    status = get_database_status(db, env={"DATABASE_URL": SECRET_LOOKING_VALUE})
    serialized = json.dumps(status_to_dict(status))

    for forbidden in _FORBIDDEN_ANYWHERE:
        assert forbidden not in serialized, f"forbidden field/value leaked: {forbidden}"
    assert "alice" not in serialized
    assert "this must never appear" not in serialized
    assert SECRET_LOOKING_VALUE not in serialized


def test_get_database_status_on_a_genuinely_empty_database_does_not_raise(empty_db):
    status = get_database_status(empty_db)
    assert status.table_row_counts == {}
    assert status.missing_tables == sorted(TABLE_COUNTERS)
    assert status.migration.at_head is False


def test_get_database_status_on_a_partially_migrated_database(partially_migrated_db):
    status = get_database_status(partially_migrated_db)
    assert set(status.missing_tables) == {"players", "audit_events"}
    assert "role_targets" in status.table_row_counts


def test_status_accepts_no_player_or_free_text_argument_of_any_kind():
    """Executable documentation: get_database_status's signature has no
    parameter that could be pointed at one subject or one free-text filter."""
    import inspect

    parameters = inspect.signature(get_database_status).parameters
    assert set(parameters) == {"db", "tables", "env"}


# ---------------------------------------------------------------------------
# Human-readable rendering
# ---------------------------------------------------------------------------


def test_format_human_includes_every_table_and_flag_label(db):
    status = get_database_status(db, env={"OIDC_ISSUER": "https://example.test"})
    rendered = format_human(status)

    for label in TABLE_COUNTERS:
        assert label in rendered
    for name in CONFIGURED_ENV_FLAGS:
        assert name in rendered
    assert "NOT AT HEAD" in rendered


def test_format_human_never_contains_a_configured_secret_value(db):
    status = get_database_status(db, env={"GEMINI_API_KEY": SECRET_LOOKING_VALUE})
    assert SECRET_LOOKING_VALUE not in format_human(status)


def test_format_human_lists_missing_tables_when_present(empty_db):
    status = get_database_status(empty_db)
    rendered = format_human(status)
    assert "missing_tables" in rendered
    for label in TABLE_COUNTERS:
        assert label in rendered


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def test_main_json_output_is_valid_json_and_exits_zero(monkeypatch, db, capsys):
    monkeypatch.setattr("db.database.SessionLocal", lambda: db)
    exit_code = status_module._main(["--json"])
    assert exit_code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert set(parsed) == _ALLOWED_TOP_LEVEL_KEYS


def test_main_check_migrations_fails_closed_when_not_at_head(monkeypatch, db, capsys):
    monkeypatch.setattr("db.database.SessionLocal", lambda: db)
    exit_code = status_module._main(["--check-migrations"])
    assert exit_code == 1
    capsys.readouterr()  # drain human-readable output, not asserted here


def test_main_check_migrations_passes_when_at_head(monkeypatch, db, capsys):
    _set_alembic_version(db, migration_head_revision())
    monkeypatch.setattr("db.database.SessionLocal", lambda: db)
    exit_code = status_module._main(["--check-migrations"])
    assert exit_code == 0
    capsys.readouterr()


def test_main_on_a_genuinely_empty_database_does_not_crash(monkeypatch, empty_db, capsys):
    """Direct regression test for Codex's review finding: the documented
    fresh-clone path must not raise a raw OperationalError traceback."""
    monkeypatch.setattr("db.database.SessionLocal", lambda: empty_db)
    exit_code = status_module._main(["--json"])
    assert exit_code == 0
    parsed = json.loads(capsys.readouterr().out)
    assert parsed["missing_tables"] == sorted(TABLE_COUNTERS)
    assert parsed["table_row_counts"] == {}


def test_main_check_migrations_fails_on_a_partially_migrated_database_even_if_stamped_at_head(
    monkeypatch, partially_migrated_db, capsys
):
    """A revision stamped at head with tables still missing (e.g. a
    migration that failed partway through) must still fail --check-migrations,
    not just "not yet stamped" databases."""
    _set_alembic_version(partially_migrated_db, migration_head_revision())
    monkeypatch.setattr("db.database.SessionLocal", lambda: partially_migrated_db)
    exit_code = status_module._main(["--check-migrations"])
    assert exit_code == 1
    capsys.readouterr()
