"""Package 7 -- a live schema contract `alembic check` cannot fully replace.

Confirmed directly against Alembic 1.19.1 before writing this file (not
assumed): renaming a CHECK constraint's *expression* while keeping its name
unchanged (`target_level BETWEEN 1 AND 5` -> `BETWEEN 1 AND 6`) still reports
"No new upgrade operations detected." Alembic's own autogenerate plugin for
this is literally named `checkconstraint_byname` -- it detects a named CHECK
constraint's presence, not whether its expression still matches. `alembic
check` (run in every package's evidence) is real and worth keeping, but it
cannot catch this one class of drift; this file is what does.

Three things this file checks that nothing else in the suite consolidates in
one place:

1. Every named CHECK constraint's actual expression (queried live, not read
   from `models/*.py`) contains the exact literal bounds/values it should --
   belt-and-suspenders alongside the behavioral boundary tests already in
   `test_core_measured_indexes_and_constraints.py` and
   `test_core_learning_mode.py` (which prove the same thing indirectly, by
   showing the boundary value is actually rejected; this proves it directly,
   from the constraint's own stored definition). PostgreSQL normalizes CHECK
   expression text (`BETWEEN` becomes `>= AND <=`, `IN (...)` becomes
   `= ANY (ARRAY[...]::text[])` with explicit casts) -- the expected
   substrings below are the exact normalized forms observed directly against
   a real migrated PostgreSQL database, not guessed.
2. A full foreign-key inventory across every table in the schema (not a
   sample) -- each FK's exact `(constrained_column, referred_table,
   referred_column)`.
3. A full named-index inventory across every table -- each index's exact
   column list, including the ones the boundary constraint/index tests
   already assert individually and the ones (e.g. `guilds_name_key`,
   `uq_player_topic`, `uq_identity_binding_subject`) nothing else checks
   directly today.

Plus the `audit_events` trigger's *structure*, not its behavior (already
covered by
`test_core_retention_job_postgres_integration.py::test_trigger_rejects_update_but_permits_delete`):
exactly one trigger, `audit_events_reject_update`, firing `BEFORE UPDATE`;
`audit_events_reject_delete` (retired by `4631f204d4ba`) must not exist.

Grants are deliberately not checked here: no `GRANT` statement exists
anywhere in this schema yet (confirmed by grep across `models/*.py` and
`migrations/versions/*.py`) -- the three-role PostgreSQL privilege matrix is
explicitly a specify-only, not-yet-implemented item (Package 9 per the
reconciled plan), so there is nothing live to contract-test yet.
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError

from db.database import normalize_database_url

BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
_ADMIN_DATABASE_URL = "postgresql+psycopg://prism_app:prism_dev_local_only@localhost:55432/postgres"

# --- Expected foreign-key and index inventory, both dialects -------------
# Captured directly from `sa.inspect()` against a real database migrated to
# head (`6564595b3466`), not transcribed from models/*.py by hand.

_EXPECTED_FOREIGN_KEYS: dict[str, set[tuple[tuple[str, ...], str, tuple[str, ...]]]] = {
    "accuracy_history": {(("player_id",), "players", ("player_id",))},
    "competency_assessments": {(("player_id",), "players", ("player_id",))},
    "evidence_records": {(("player_id",), "players", ("player_id",))},
    "game_sessions": {
        (("dungeon_id",), "dungeons", ("dungeon_id",)),
        (("player_id",), "players", ("player_id",)),
    },
    "generated_quizzes": {
        (("material_id",), "learning_materials", ("material_id",)),
        (("player_id",), "players", ("player_id",)),
    },
    "identity_bindings": {(("player_id",), "players", ("player_id",))},
    "learner_profiles": {(("player_id",), "players", ("player_id",))},
    "learning_materials": {(("player_id",), "players", ("player_id",))},
    "players": {(("guild_id",), "guilds", ("guild_id",))},
    "rooms": {(("dungeon_id",), "dungeons", ("dungeon_id",))},
    "source_versions": {(("material_id",), "learning_materials", ("material_id",))},
    "submissions": {
        (("player_id",), "players", ("player_id",)),
        (("question_id",), "questions", ("question_id",)),
    },
}

_EXPECTED_INDEXES: dict[str, dict[str, list[str]]] = {
    "accuracy_history": {
        "ix_accuracy_history_player_id": ["player_id"],
        "uq_player_topic": ["player_id", "topic"],
    },
    "audit_events": {"ix_audit_events_created_at": ["created_at"]},
    "competency_assessments": {
        "ix_competency_assessments_curriculum_slug": ["curriculum_slug"],
        "ix_competency_assessments_lookup_newest": [
            "player_id", "curriculum_slug", "created_at", "assessment_id",
        ],
        "ix_competency_assessments_player_id": ["player_id"],
    },
    "dungeons": {"ix_dungeons_curriculum_slug": ["curriculum_slug"]},
    "evidence_records": {
        "ix_evidence_records_competency_id": ["competency_id"],
        "ix_evidence_records_lookup_newest": [
            "player_id", "competency_id", "evidence_type", "recorded_at", "evidence_id",
        ],
        "ix_evidence_records_player_id": ["player_id"],
    },
    "game_sessions": {"ix_game_sessions_player_id": ["player_id"]},
    "generated_quizzes": {
        "ix_generated_quizzes_material_id": ["material_id"],
        "ix_generated_quizzes_player_id": ["player_id"],
    },
    "identity_bindings": {
        "ix_identity_bindings_player_id": ["player_id"],
        "uq_identity_binding_subject": ["issuer", "subject_id"],
    },
    "learner_profiles": {"ix_learner_profiles_player_id": ["player_id"]},
    "learning_materials": {
        "ix_learning_materials_player_id": ["player_id"],
        "ix_learning_materials_sha256": ["sha256"],
    },
    "players": {"ix_players_username": ["username"]},
    "role_targets": {
        "ix_role_targets_competency_id": ["competency_id"],
        "ix_role_targets_lookup_newest": [
            "role", "competency_id", "valid_from", "created_at", "target_id",
        ],
        "ix_role_targets_role": ["role"],
    },
    "source_versions": {
        "ix_source_versions_lookup_newest": [
            "material_id", "version_number", "created_at", "source_version_id",
        ],
        "ix_source_versions_material_id": ["material_id"],
        "ix_source_versions_sha256": ["sha256"],
    },
    "submissions": {"ix_submissions_player_id": ["player_id"]},
}
# guilds.name (`Column(String, unique=True)`) is deliberately excluded from
# the shared inventory above: SQLAlchemy never gives this constraint an
# explicit name, so PostgreSQL auto-generates one (`guilds_name_key`) while
# SQLite reports it with `name: None` -- confirmed directly, not assumed.
# There is no portable name to assert equality on; see
# test_guilds_name_uniqueness_on_sqlite/_postgresql below, which check the
# column set instead.

# name -> substrings that must ALL appear in the live constraint definition.
# PostgreSQL and SQLite normalize differently (see module docstring), so each
# dialect gets its own expected substrings rather than one shared string.
_EXPECTED_CHECK_SUBSTRINGS_POSTGRESQL: dict[str, list[str]] = {
    "ck_role_targets_target_level_1_5": ["target_level >= 1", "target_level <= 5"],
    "ck_role_targets_valid_window": ["valid_to IS NULL", "valid_from IS NULL", "valid_to > valid_from"],
    "ck_evidence_records_type": [
        "'self_report'", "'diagnostic'", "'observed_practice'", "'reviewer'", "'provider_imported'",
    ],
    "ck_evidence_records_value_0_5": ["value >= 0", "value <= 5"],
    "ck_source_versions_version_positive": ["version_number >= 1"],
    "ck_players_preferred_mode_known_value": ["'professional'", "'quest'"],
}
_EXPECTED_CHECK_SUBSTRINGS_SQLITE: dict[str, list[str]] = {
    "ck_role_targets_target_level_1_5": ["target_level BETWEEN 1 AND 5"],
    "ck_role_targets_valid_window": ["valid_to IS NULL", "valid_from IS NULL", "valid_to > valid_from"],
    "ck_evidence_records_type": [
        "'self_report'", "'diagnostic'", "'observed_practice'", "'reviewer'", "'provider_imported'",
    ],
    "ck_evidence_records_value_0_5": ["value IS NULL OR value BETWEEN 0 AND 5"],
    "ck_source_versions_version_positive": ["version_number >= 1"],
    "ck_players_preferred_mode_known_value": ["'professional'", "'quest'"],
}
_CHECK_CONSTRAINT_TABLES = {
    "ck_role_targets_target_level_1_5": "role_targets",
    "ck_role_targets_valid_window": "role_targets",
    "ck_evidence_records_type": "evidence_records",
    "ck_evidence_records_value_0_5": "evidence_records",
    "ck_source_versions_version_positive": "source_versions",
    "ck_players_preferred_mode_known_value": "players",
}


def _assert_check_constraints(engine, expected_substrings: dict[str, list[str]]) -> None:
    inspector = inspect(engine)
    by_table: dict[str, dict[str, str]] = {}
    for name, table in _CHECK_CONSTRAINT_TABLES.items():
        if table not in by_table:
            by_table[table] = {
                c["name"]: c["sqltext"] for c in inspector.get_check_constraints(table)
            }
        assert name in by_table[table], f"missing CHECK constraint {name} on {table}"
        actual = by_table[table][name]
        for substring in expected_substrings[name]:
            assert substring in actual, (
                f"{name}: expected substring {substring!r} not found in live "
                f"definition {actual!r} -- expression drift alembic check cannot catch"
            )


def _assert_foreign_keys(engine) -> None:
    inspector = inspect(engine)
    for table, expected in _EXPECTED_FOREIGN_KEYS.items():
        actual = {
            (tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"]))
            for fk in inspector.get_foreign_keys(table)
        }
        assert actual == expected, f"{table}: FK inventory mismatch -- expected {expected}, got {actual}"


def _assert_indexes(engine) -> None:
    """Checks both `get_indexes()` and `get_unique_constraints()` -- SQLite's
    inspector reports a named `UniqueConstraint` (e.g. `uq_player_topic`,
    `uq_identity_binding_subject`, `guilds_name_key`) only through the
    latter, while PostgreSQL's reports it through both (an implicit unique
    index backs a unique constraint there). Confirmed directly: on a real
    migrated SQLite database, `uq_player_topic` is absent from
    `get_indexes('accuracy_history')` and present only in
    `get_unique_constraints(...)`."""
    inspector = inspect(engine)
    for table, expected in _EXPECTED_INDEXES.items():
        actual = {index["name"]: index["column_names"] for index in inspector.get_indexes(table)}
        actual.update(
            {uc["name"]: uc["column_names"] for uc in inspector.get_unique_constraints(table)}
        )
        for name, columns in expected.items():
            assert name in actual, f"missing index/unique constraint {name} on {table}"
            assert actual[name] == columns, (
                f"{name} on {table}: expected columns {columns}, got {actual[name]}"
            )


def test_check_constraint_expressions_on_sqlite(tmp_path):
    url = f"sqlite:///{tmp_path / 'schema_contract.db'}"
    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    _assert_check_constraints(engine, _EXPECTED_CHECK_SUBSTRINGS_SQLITE)
    engine.dispose()


def test_foreign_key_inventory_on_sqlite(tmp_path):
    url = f"sqlite:///{tmp_path / 'schema_contract_fk.db'}"
    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    _assert_foreign_keys(engine)
    engine.dispose()


def test_index_inventory_on_sqlite(tmp_path):
    url = f"sqlite:///{tmp_path / 'schema_contract_idx.db'}"
    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    _assert_indexes(engine)
    engine.dispose()


def test_guilds_name_uniqueness_on_sqlite(tmp_path):
    url = f"sqlite:///{tmp_path / 'schema_contract_guild.db'}"
    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)
    unique_column_sets = {
        tuple(uc["column_names"]) for uc in inspect(engine).get_unique_constraints("guilds")
    }
    assert ("name",) in unique_column_sets
    engine.dispose()


def test_negative_control_check_constraint_drift_is_caught_on_sqlite(tmp_path, monkeypatch):
    """Proves the CHECK-expression test is not vacuous: a deliberately wrong
    expected substring for a real constraint must fail, not silently pass."""
    url = f"sqlite:///{tmp_path / 'schema_contract_drift.db'}"
    _run_alembic(url, "upgrade", "head")
    engine = create_engine(url)

    wrong = dict(_EXPECTED_CHECK_SUBSTRINGS_SQLITE)
    wrong["ck_role_targets_target_level_1_5"] = ["target_level BETWEEN 1 AND 6"]
    with pytest.raises(AssertionError, match="expression drift"):
        _assert_check_constraints(engine, wrong)
    engine.dispose()


# --- Live PostgreSQL: triggers only exist there, and it's the real target -


def _skip_unless_postgres_reachable() -> None:
    try:
        probe = create_engine(_ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
        try:
            with probe.connect() as connection:
                connection.execute(text("SELECT 1"))
        finally:
            probe.dispose()
    except OperationalError as exc:
        pytest.skip(
            "Real PostgreSQL not reachable at the documented docker-compose.dev.yml URL "
            f"(localhost:55432) -- skipping the Package 7 schema-contract test: {exc}"
        )


def _run_alembic(database_url: str, *arguments: str) -> None:
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *arguments],
        cwd=BACKEND_DIRECTORY,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"alembic {' '.join(arguments)} failed:\n{result.stdout}\n{result.stderr}")


@contextlib.contextmanager
def _disposable_migrated_postgres_database():
    database_name = f"sih_pkg7_{uuid.uuid4().hex[:12]}"
    probe = create_engine(_ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    created = False
    try:
        with probe.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        created = True
        database_url = normalize_database_url(
            f"postgresql://prism_app:prism_dev_local_only@localhost:55432/{database_name}"
        )
        _run_alembic(database_url, "upgrade", "head")
        yield database_url
    finally:
        probe.dispose()
        if created:
            cleanup = create_engine(_ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
            try:
                with cleanup.connect() as connection:
                    connection.execute(
                        text(
                            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                            "WHERE datname = :name AND pid <> pg_backend_pid()"
                        ),
                        {"name": database_name},
                    )
                    connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
            finally:
                cleanup.dispose()


def test_check_constraint_expressions_on_postgresql():
    _skip_unless_postgres_reachable()
    with _disposable_migrated_postgres_database() as database_url:
        engine = create_engine(database_url)
        _assert_check_constraints(engine, _EXPECTED_CHECK_SUBSTRINGS_POSTGRESQL)
        engine.dispose()


def test_foreign_key_inventory_on_postgresql():
    _skip_unless_postgres_reachable()
    with _disposable_migrated_postgres_database() as database_url:
        engine = create_engine(database_url)
        _assert_foreign_keys(engine)
        engine.dispose()


def test_index_inventory_on_postgresql():
    _skip_unless_postgres_reachable()
    with _disposable_migrated_postgres_database() as database_url:
        engine = create_engine(database_url)
        _assert_indexes(engine)
        engine.dispose()


def test_guilds_name_uniqueness_on_postgresql():
    _skip_unless_postgres_reachable()
    with _disposable_migrated_postgres_database() as database_url:
        engine = create_engine(database_url)
        unique_column_sets = {
            tuple(uc["column_names"]) for uc in inspect(engine).get_unique_constraints("guilds")
        }
        assert ("name",) in unique_column_sets
        engine.dispose()


def test_audit_events_trigger_structure_is_exactly_one_update_trigger():
    """Structural check: the trigger's *shape*, not its behavior (already
    covered by test_core_retention_job_postgres_integration.py). Proves
    exactly `audit_events_reject_update` exists, firing BEFORE UPDATE, and
    that the retired `audit_events_reject_delete` (4631f204d4ba) is gone --
    the exact drift class `alembic check` cannot see, since neither
    migration change is a named CHECK constraint and Alembic's DDL-event
    autogenerate coverage does not extend to triggers at all."""
    _skip_unless_postgres_reachable()
    with _disposable_migrated_postgres_database() as database_url:
        engine = create_engine(database_url)
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT trigger_name, action_timing, event_manipulation "
                    "FROM information_schema.triggers "
                    "WHERE event_object_table = 'audit_events'"
                )
            ).all()
        engine.dispose()

        triggers = {row.trigger_name: (row.action_timing, row.event_manipulation) for row in rows}
        assert "audit_events_reject_update" in triggers
        assert triggers["audit_events_reject_update"] == ("BEFORE", "UPDATE")
        assert "audit_events_reject_delete" not in triggers
        assert len(triggers) == 1, f"expected exactly one trigger on audit_events, found {triggers}"
