"""Opt-in real-PostgreSQL integration contract -- Package V.

Every other test file in this suite proves the retention-job/trigger
mechanisms either against SQLite (with the PostgreSQL dialect monkeypatched
for the FOR UPDATE SKIP LOCKED compiled-SQL check) or against real
PostgreSQL only via one-off manual drills whose transcripts are copied into
`LANE2_SYNC.md`/`EVIDENCE.md`. Codex's cold immutable audit of Package U
(LANE2_SYNC.md, 2026-09-01) asked for something stronger: a committed,
re-runnable "regression/opt-in PostgreSQL integration contract" that proves
the real trigger and the real retention job stay compatible at the real
Alembic head -- not just a transcript of a script that was run once.

This file is that contract. It is OPT-IN, not part of the mandatory unit
gate: it connects to the real local `docker-compose.dev.yml` PostgreSQL
instance (localhost:55432), and if that server is not reachable, the
module-scoped fixture calls `pytest.skip(...)` so `pytest -q` still passes
cleanly with this file skipped, not failed, in any environment without
Docker running -- exactly like every other PostgreSQL-only capability this
project has (see db/database.py's own migration-gated-startup policy,
which is SQLite-exempt for the same reason).

Every test creates its own disposable PostgreSQL database (never the shared
`sih_learning_tool` dev database), migrates it to the real Alembic head via
a real `alembic` subprocess (the same mechanism test_core_migrations.py
uses for SQLite), and drops it afterward -- so a run of this file never
leaves state behind for the next run or for a human using the dev database
by hand.

What this proves, matching the four items Codex's handoff asked for:
    (a) the Package V trigger boundary is real: UPDATE is rejected, DELETE
        is permitted (test_trigger_rejects_update_but_permits_delete);
    (b) a cited synthetic maximum can actually run the retention job against
        the real trigger-protected table -- the exact call that failed under
        Package U (test_synthetic_maximum_retention_can_delete_audit_events);
    (c) the four-worker/11-expired/2-young/batch-3 drill from Package S is
        exact against the real table, not only a bare SQLAlchemy model
        (test_four_concurrent_workers_delete_all_expired_rows_exactly_once);
    (d) migration downgrade/upgrade across the Package V revision is clean
        (test_migration_downgrade_restores_delete_rejection_and_upgrade_removes_it_again).
"""
from __future__ import annotations

import os
import subprocess
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import bindparam, create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import sessionmaker

from db.database import normalize_database_url
from models.governance import AuditEvent
from scripts.retention_job import _enforce_maximum_retention_core
from security.retention import RetentionPolicy


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
# Same documented local docker-compose.dev.yml credentials already relied on
# (as a URL literal, never a live connection) by test_core_backup_restore.py.
_ADMIN_DATABASE_URL = "postgresql+psycopg://sih_app:sih_dev_local_only@localhost:55432/postgres"
CATEGORY = "retain_append_only_security_log_duration_policy_pending"
PACKAGE_V_DOWN_REVISION = "036de46dd515"  # the Package U revision Package V retires DELETE-rejection from

# A synthetic, clearly test-only maximum -- never merged into the real
# security.retention.RETENTION_POLICIES registry, exactly like the pattern
# already established in test_core_retention_job.py. The real registry cites
# no maximum for anything today, so proving the deletion mechanism works at
# all (with or without the trigger) requires an injected policy.
_SYNTHETIC_MAXIMUM_POLICY = {
    CATEGORY: RetentionPolicy(
        category=CATEGORY,
        minimum_retention_days=None,
        minimum_retention_source=None,
        maximum_retention_days=30,
        maximum_retention_source=(
            "Package V PostgreSQL integration contract -- test-only, never a real cited source"
        ),
        notes=(
            "Synthetic policy proving the retention job can still delete audit_events now "
            "that Package V retired the unconditional DELETE-rejecting trigger."
        ),
    ),
}
_TABLE_MAP = {CATEGORY: (AuditEvent, "created_at", "audit_id")}


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
        raise AssertionError(
            f"alembic {' '.join(arguments)} failed:\n{result.stdout}\n{result.stderr}"
        )


@pytest.fixture(scope="module")
def postgres_head_database():
    try:
        probe = create_engine(_ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
        with probe.connect() as connection:
            connection.execute(text("SELECT 1"))
    except OperationalError as exc:
        pytest.skip(
            "Real PostgreSQL not reachable at the documented docker-compose.dev.yml URL "
            f"(localhost:55432) -- skipping the opt-in Package V integration contract: {exc}"
        )
        return

    database_name = f"sih_pkgv_{uuid.uuid4().hex[:12]}"
    with probe.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    probe.dispose()

    # Normalized once here to the psycopg-3 driver URL (normalize_database_url
    # is idempotent, see test_core_database.py's own coverage of that) and
    # reused everywhere below -- both for the alembic subprocess's
    # DATABASE_URL and for every direct create_engine() call in this file --
    # so nothing accidentally falls back to the unavailable psycopg2 driver
    # SQLAlchemy otherwise defaults a bare "postgresql://" URL to.
    database_url = normalize_database_url(
        f"postgresql://sih_app:sih_dev_local_only@localhost:55432/{database_name}"
    )
    _run_alembic(database_url, "upgrade", "head")

    yield database_url

    # PostgreSQL refuses to DROP a database with any active connection, so
    # every connection this module opened must be terminated first -- a
    # failure here would leak a disposable database into the dev server on
    # every run, not just on a test failure.
    admin = create_engine(_ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(
            text(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                "WHERE datname = :name AND pid <> pg_backend_pid()"
            ),
            {"name": database_name},
        )
        connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
    admin.dispose()


@pytest.fixture
def db_session(postgres_head_database):
    engine = create_engine(postgres_head_database)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _insert_audit_event(session, *, age_days: float, event_id: str) -> None:
    created_at = datetime.now(timezone.utc) - timedelta(days=age_days)
    session.add(
        AuditEvent(
            audit_id=event_id,
            actor="test",
            action="synthetic.event",
            entity_type="test",
            created_at=created_at,
        )
    )
    session.commit()


# ---------------------------------------------------------------------------
# (a) Trigger boundary matches what Package V actually documents: UPDATE is
# rejected, DELETE is now permitted -- the inverse of Package U's boundary.
# ---------------------------------------------------------------------------


def test_trigger_rejects_update_but_permits_delete(db_session):
    _insert_audit_event(db_session, age_days=1, event_id="pkgv-boundary-row")

    with pytest.raises(ProgrammingError, match="is not permitted"):
        db_session.execute(
            text("UPDATE audit_events SET actor = 'tampered' WHERE audit_id = :id"),
            {"id": "pkgv-boundary-row"},
        )
    db_session.rollback()

    unchanged_actor = db_session.execute(
        text("SELECT actor FROM audit_events WHERE audit_id = :id"),
        {"id": "pkgv-boundary-row"},
    ).scalar_one()
    assert unchanged_actor == "test"  # the rejected UPDATE never applied

    deleted_rows = db_session.execute(
        text("DELETE FROM audit_events WHERE audit_id = :id RETURNING audit_id"),
        {"id": "pkgv-boundary-row"},
    ).fetchall()
    db_session.commit()
    assert len(deleted_rows) == 1  # DELETE now succeeds -- Package U's regression is fixed


# ---------------------------------------------------------------------------
# (b) A synthetic cited maximum can actually run retention enforcement now.
# This is the exact call Codex's audit reproduced failing under Package U
# (ProgrammingError/RaiseException on the DELETE) once any maximum exists
# for audit_events, its only registered category.
# ---------------------------------------------------------------------------


def test_synthetic_maximum_retention_can_delete_audit_events(db_session):
    _insert_audit_event(db_session, age_days=40, event_id="pkgv-expired-row")
    _insert_audit_event(db_session, age_days=1, event_id="pkgv-young-row")

    result = _enforce_maximum_retention_core(
        db_session,
        CATEGORY,
        apply=True,
        policies=_SYNTHETIC_MAXIMUM_POLICY,
        table_map=_TABLE_MAP,
        batch_size=10,
        now=None,
        actor="test:package_v_integration",
    )

    assert result.deleted_count == 1
    assert result.deleted_ids == ("pkgv-expired-row",)
    expired_remaining = db_session.execute(
        text("SELECT count(*) FROM audit_events WHERE audit_id = :id"),
        {"id": "pkgv-expired-row"},
    ).scalar_one()
    young_remaining = db_session.execute(
        text("SELECT count(*) FROM audit_events WHERE audit_id = :id"),
        {"id": "pkgv-young-row"},
    ).scalar_one()
    assert expired_remaining == 0
    assert young_remaining == 1


# ---------------------------------------------------------------------------
# (c) The exact four-worker concurrency drill from Package S/Codex's Package
# R contract, now proven against the real trigger-protected table with a
# real PostgreSQL dialect (not a monkeypatched one).
# ---------------------------------------------------------------------------


def _worker_run(database_url: str, worker_index: int) -> dict:
    engine = create_engine(database_url)
    session = sessionmaker(bind=engine)()
    try:
        result = _enforce_maximum_retention_core(
            session,
            CATEGORY,
            apply=True,
            policies=_SYNTHETIC_MAXIMUM_POLICY,
            table_map=_TABLE_MAP,
            batch_size=3,
            now=None,
            actor=f"test:package_v_worker_{worker_index}",
        )
        return {"deleted_ids": set(result.deleted_ids), "deleted_count": result.deleted_count}
    finally:
        session.close()
        engine.dispose()


def test_four_concurrent_workers_delete_all_expired_rows_exactly_once(postgres_head_database):
    database_url = postgres_head_database
    engine = create_engine(database_url)
    try:
        setup_session = sessionmaker(bind=engine)()
        expired_ids = [f"pkgv-drill-expired-{i}" for i in range(11)]
        young_ids = [f"pkgv-drill-young-{i}" for i in range(2)]
        for event_id in expired_ids:
            _insert_audit_event(setup_session, age_days=40, event_id=event_id)
        for event_id in young_ids:
            _insert_audit_event(setup_session, age_days=1, event_id=event_id)
        setup_session.close()

        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda i: _worker_run(database_url, i), range(4)))

        deleted_sets = [r["deleted_ids"] for r in results]
        union = set().union(*deleted_sets)
        pairwise_disjoint = all(
            deleted_sets[i].isdisjoint(deleted_sets[j]) for i in range(4) for j in range(i + 1, 4)
        )

        assert pairwise_disjoint
        assert union == set(expired_ids)
        assert sum(r["deleted_count"] for r in results) == 11

        verify_session = sessionmaker(bind=engine)()
        try:
            remaining_old = verify_session.execute(
                text("SELECT count(*) FROM audit_events WHERE audit_id IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"ids": expired_ids},
            ).scalar_one()
            remaining_young = verify_session.execute(
                text("SELECT count(*) FROM audit_events WHERE audit_id IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"ids": young_ids},
            ).scalar_one()
            # Scoped to this drill's own worker actors -- earlier tests in
            # this module (test_synthetic_maximum_retention_can_delete_
            # audit_events) also write a 'retention_job.enforce_maximum'
            # audit row for the SAME category into the SAME module-scoped
            # disposable database, so an unscoped sum would double-count
            # a prior test's own deletion alongside this drill's.
            audit_sum = verify_session.execute(
                text(
                    "SELECT coalesce(sum((details->>'deleted_count')::int), 0) "
                    "FROM audit_events WHERE action = 'retention_job.enforce_maximum' "
                    "AND entity_type = :category AND actor LIKE 'test:package_v_worker_%'"
                ),
                {"category": CATEGORY},
            ).scalar_one()

            assert remaining_old == 0
            assert remaining_young == 2
            assert audit_sum == 11

            final_result = _enforce_maximum_retention_core(
                verify_session,
                CATEGORY,
                apply=True,
                policies=_SYNTHETIC_MAXIMUM_POLICY,
                table_map=_TABLE_MAP,
                batch_size=10,
                now=None,
                actor="test:package_v_final_rerun",
            )
            assert (final_result.candidate_count, final_result.deleted_count) == (0, 0)
        finally:
            # A no-candidate call through _enforce_maximum_retention_core
            # returns without commit()/rollback() (see its own docstring --
            # nothing was done, so nothing needs to be persisted), which
            # would otherwise leave this session's transaction open and
            # holding a lock on audit_events -- exactly the lock the next
            # test's ALTER-privilege migration DDL needs. A plain
            # assertion failure above would hit this same finally, which is
            # the point: no assertion failure in this test may ever leak a
            # transaction into the next test.
            verify_session.rollback()
            verify_session.close()
    finally:
        engine.dispose()


# ---------------------------------------------------------------------------
# (d) Migration upgrade/downgrade is clean across the real Package V
# revision at the real PostgreSQL head.
# ---------------------------------------------------------------------------


def test_migration_downgrade_restores_delete_rejection_and_upgrade_removes_it_again(
    postgres_head_database,
):
    database_url = postgres_head_database

    _run_alembic(database_url, "downgrade", PACKAGE_V_DOWN_REVISION)
    engine = create_engine(database_url)
    try:
        session = sessionmaker(bind=engine)()
        try:
            session.add(
                AuditEvent(
                    audit_id="pkgv-downgrade-probe", actor="test", action="x", entity_type="test"
                )
            )
            session.commit()
            with pytest.raises(ProgrammingError, match="is not permitted"):
                session.execute(
                    text("DELETE FROM audit_events WHERE audit_id = 'pkgv-downgrade-probe'")
                )
        finally:
            # Every statement above runs inside the same open transaction --
            # even the successful commit() starts a new one for the next
            # statement -- so this rollback (needed regardless to clear the
            # failed-DELETE's aborted transaction state before the
            # connection returns to the pool) must run even if the
            # pytest.raises block above did not fire as expected.
            session.rollback()
            session.close()
    finally:
        engine.dispose()

    _run_alembic(database_url, "upgrade", "head")
    engine = create_engine(database_url)
    try:
        session = sessionmaker(bind=engine)()
        try:
            deleted_rows = session.execute(
                text(
                    "DELETE FROM audit_events WHERE audit_id = 'pkgv-downgrade-probe' "
                    "RETURNING audit_id"
                )
            ).fetchall()
            session.commit()
            assert len(deleted_rows) == 1
        finally:
            session.rollback()
            session.close()
    finally:
        engine.dispose()
