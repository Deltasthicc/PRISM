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
instance (localhost:55432), and if that server is not reachable, every test
that needs it skips cleanly so `pytest -q` still passes with this file
skipped, not failed, in any environment without Docker running -- exactly
like every other PostgreSQL-only capability this project has (see
db/database.py's own migration-gated-startup policy, which is SQLite-exempt
for the same reason).

Every test creates its own disposable PostgreSQL database (never the shared
`prism` dev database), migrates it to the real Alembic head via
a real `alembic` subprocess (the same mechanism test_core_migrations.py
uses for SQLite), and drops it afterward -- so a run of this file never
leaves state behind for the next run or for a human using the dev database
by hand.

What this proves, matching the four items Codex's original handoff asked
for:
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

Codex's immutable review of the first version of this file (LANE2_SYNC.md,
2026-09-02) found two further "P2" gaps and this revision closes both:

  P2 finding 2 -- the disposable-database fixture only cleaned up after
  `yield`, so a failure between `CREATE DATABASE` and `yield` (most
  plausibly an Alembic migration failure) skipped cleanup and leaked the
  database. `_disposable_postgres_database()` below wraps the entire
  create/migrate/yield sequence in `try/finally` so cleanup is unconditional,
  and `test_setup_failure_between_create_and_yield_does_not_leak_database`
  injects a deterministic failure at exactly that point and proves no
  database survives it.

  P2 finding 1 -- `test_four_concurrent_workers_delete_all_expired_rows_exactly_once`
  only synchronized workers at thread-pool submission time, which does not
  force their candidate SELECTs to genuinely overlap while row locks are
  held; four serial (non-overlapping) executions would also satisfy the same
  assertions, so the test did not itself prove the row-claim race stays
  closed. `_BarrierSyncSession` below is a test-only `Session` subclass
  (production code is untouched) that intercepts exactly the retention job's
  `SELECT ... FOR UPDATE SKIP LOCKED` candidate select and blocks every
  worker at a shared `threading.Barrier` immediately after that select
  returns -- while the transaction (and its row locks) is still open --
  until all four workers have independently reached the same point. This
  forces genuine overlapping candidate selection deterministically, not by
  thread-scheduling luck.
  `test_negative_control_without_skip_locked_fails_the_same_contract` then
  proves that forcing overlap is meaningful: an equivalent, deliberately
  broken candidate-select-then-delete flow that omits all locking (the exact
  shape `scripts/retention_job.py`'s own inline comment describes as the
  pre-Package-S bug) is run under the identical forced-overlap barrier and
  is shown, deterministically, to be unable to satisfy the same contract --
  it relies only on PostgreSQL's own MVCC/row-lock re-check semantics under
  the forced ordering, never on sleep-based timing.
"""
from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import bindparam, create_engine, select, text
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.orm import Session, sessionmaker

from db.database import normalize_database_url
from models.governance import AuditEvent
from scripts.retention_job import _enforce_maximum_retention_core
from security.retention import RetentionPolicy


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
# Same documented local docker-compose.dev.yml credentials already relied on
# (as a URL literal, never a live connection) by test_core_backup_restore.py.
_ADMIN_DATABASE_URL = "postgresql+psycopg://prism_app:prism_dev_local_only@localhost:55432/postgres"
CATEGORY = "retain_append_only_security_log_duration_policy_pending"
PACKAGE_V_DOWN_REVISION = "036de46dd515"  # the Package U revision Package V retires DELETE-rejection from

# Upper bound only, never a pacing mechanism: real synchronization is a
# threading.Barrier, which blocks exactly until every party arrives, not for
# a fixed duration. This timeout exists purely so a genuine hang (a stuck
# connection, a real deadlock) fails the test deterministically within a
# bounded window instead of hanging the suite forever.
_BARRIER_TIMEOUT_SECONDS = 20.0

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
            f"(localhost:55432) -- skipping the opt-in Package V integration contract: {exc}"
        )


def _drop_database(database_name: str) -> None:
    """Unconditionally drop a disposable database this file created.
    PostgreSQL refuses `DROP DATABASE` while any connection is still open
    against it, so every connection must be terminated first -- a failure
    here would leak a disposable database into the dev server on every run,
    not just on a test failure.
    """
    admin = create_engine(_ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": database_name},
            )
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
    finally:
        admin.dispose()


@contextlib.contextmanager
def _disposable_postgres_database(*, migrate: bool = True, _name_holder: dict | None = None):
    """Create a uniquely-named disposable PostgreSQL database, optionally
    migrate it to the real Alembic head, yield `(database_name,
    database_url)`, and unconditionally drop it on the way out.

    This is a `try/finally`-wrapped context manager, not a bare sequence of
    statements, specifically so that a failure ANYWHERE between a successful
    `CREATE DATABASE` and the `yield` -- most plausibly an Alembic migration
    failure -- still triggers cleanup. The original version of this fixture
    (Package V's first commit) put cleanup only after a generator fixture's
    `yield`, which Codex's immutable review correctly identified as a leak:
    a pre-yield failure means the generator never resumes past `yield`, so
    code written after it never runs. Wrapping the whole body in
    `try/finally` fixes this unconditionally, because Python's `finally`
    clause runs during exception unwinding regardless of whether execution
    ever reached the `try` block's `yield` statement.

    `_name_holder`, when given, is populated with the generated database
    name as soon as `CREATE DATABASE` succeeds -- before migration, before
    `yield` -- so a test that deliberately triggers a pre-yield failure (see
    `test_setup_failure_between_create_and_yield_does_not_leak_database`
    below) can still learn the exact name to verify was actually dropped,
    without depending on the failure ever reaching `yield`.
    """
    database_name = f"sih_pkgv_{uuid.uuid4().hex[:12]}"
    probe = create_engine(_ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    created = False
    try:
        with probe.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        created = True
        if _name_holder is not None:
            _name_holder["name"] = database_name

        database_url = normalize_database_url(
            f"postgresql://prism_app:prism_dev_local_only@localhost:55432/{database_name}"
        )
        if migrate:
            _run_alembic(database_url, "upgrade", "head")

        yield database_name, database_url
    finally:
        probe.dispose()
        if created:
            _drop_database(database_name)


@pytest.fixture(scope="module")
def postgres_head_database():
    _skip_unless_postgres_reachable()
    with _disposable_postgres_database() as (_database_name, database_url):
        yield database_url


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
# Setup-failure cleanup regression (Codex P2 finding 2).
# ---------------------------------------------------------------------------


def test_setup_failure_between_create_and_yield_does_not_leak_database(monkeypatch):
    """Inject a deterministic failure exactly between a successful `CREATE
    DATABASE` and `_disposable_postgres_database`'s `yield`, and prove the
    generated database does not survive it. This is the regression Codex's
    immutable review asked for: it must be impossible for a migration
    failure (or anything else in that window) to leak a disposable database
    into the shared PostgreSQL server.
    """
    _skip_unless_postgres_reachable()

    def _always_fail(*_args, **_kwargs):
        raise AssertionError("deterministic injected post-create/pre-yield failure")

    monkeypatch.setattr(sys.modules[__name__], "_run_alembic", _always_fail)

    name_holder: dict = {}
    with pytest.raises(AssertionError, match="deterministic injected"):
        with _disposable_postgres_database(_name_holder=name_holder):
            pytest.fail(
                "unreachable: the injected _run_alembic failure must fire before yield"
            )

    assert "name" in name_holder, (
        "CREATE DATABASE must have succeeded (and been recorded) before the injected "
        "failure fired -- otherwise this test isn't proving what it claims to prove"
    )
    leaked_name = name_holder["name"]

    admin = create_engine(_ADMIN_DATABASE_URL, isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as connection:
            still_exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": leaked_name},
            ).first()
        assert still_exists is None, f"disposable database {leaked_name!r} leaked"
    finally:
        admin.dispose()


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
# Test-only forced-overlap seam (Codex P2 finding 1). Production code is
# never modified: this wraps the Session object passed into the existing,
# unmodified `_enforce_maximum_retention_core`, intercepting exactly the one
# statement that matters (the FOR UPDATE SKIP LOCKED candidate select) and
# leaving every other statement -- the `more_remain` check, the DELETE --
# completely untouched.
# ---------------------------------------------------------------------------


def _is_skip_locked_select(statement) -> bool:
    for_update = getattr(statement, "_for_update_arg", None)
    return bool(for_update is not None and getattr(for_update, "skip_locked", False))


class _BufferedResult:
    """Minimal stand-in for a SQLAlchemy `CursorResult`, supporting only the
    single `.all()` call `_enforce_maximum_retention_core` makes on the
    candidate-select result -- enough to hand back rows already fetched
    before this seam's barrier wait, without re-executing the statement or
    touching the (already-closed-over) live cursor after the wait.
    """

    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _BarrierSyncSession(Session):
    """Test-only `Session` subclass: after this session executes the
    retention job's candidate `SELECT ... FOR UPDATE SKIP LOCKED`, block at
    a shared `threading.Barrier` -- while the transaction and its row locks
    are still open -- until every concurrent worker's own candidate select
    has also returned. This forces genuine overlapping candidate selection
    instead of relying on thread-scheduling luck. Every other statement
    passes through to the real `Session.execute()` untouched.
    """

    def __init__(self, *args, barrier: threading.Barrier | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._pkgv_barrier = barrier
        self._pkgv_synced = False

    def execute(self, statement, *args, **kwargs):
        result = super().execute(statement, *args, **kwargs)
        if (
            not self._pkgv_synced
            and self._pkgv_barrier is not None
            and _is_skip_locked_select(statement)
        ):
            self._pkgv_synced = True
            rows = result.all()
            self._pkgv_barrier.wait(timeout=_BARRIER_TIMEOUT_SECONDS)
            return _BufferedResult(rows)
        return result


# ---------------------------------------------------------------------------
# (c) The exact four-worker concurrency drill from Package S/Codex's Package
# R contract, now proven against the real trigger-protected table with a
# real PostgreSQL dialect (not a monkeypatched one), and with candidate
# selection genuinely forced to overlap via the barrier seam above.
# ---------------------------------------------------------------------------


def _worker_run(database_url: str, worker_index: int, barrier: threading.Barrier) -> dict:
    engine = create_engine(database_url)
    session_factory = sessionmaker(bind=engine, class_=_BarrierSyncSession)
    session = session_factory(barrier=barrier)
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
        session.rollback()
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

        barrier = threading.Barrier(4, timeout=_BARRIER_TIMEOUT_SECONDS)
        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = [
                    pool.submit(_worker_run, database_url, i, barrier) for i in range(4)
                ]
                results = [
                    future.result(timeout=_BARRIER_TIMEOUT_SECONDS + 5) for future in futures
                ]
        except threading.BrokenBarrierError as exc:
            pytest.fail(f"barrier failed to force candidate-selection overlap: {exc}")

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

            # Explicit proof, not an inference from the returned counts alone
            # (Codex's review flagged exactly this gap): the final no-op
            # rerun's own actor must not have written ANY retention audit
            # event. `_enforce_maximum_retention_core` already returns early
            # (before ever calling `record_audit_event`) when there are no
            # candidates, but this asserts that behavior directly against
            # the database rather than trusting the dataclass fields.
            final_rerun_audit_count = verify_session.execute(
                text(
                    "SELECT count(*) FROM audit_events WHERE "
                    "action = 'retention_job.enforce_maximum' "
                    "AND actor = 'test:package_v_final_rerun'"
                )
            ).scalar_one()
            assert final_rerun_audit_count == 0
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
# Negative control (Codex P2 finding 1, second half): prove the barrier-
# forced-overlap methodology above is actually meaningful by running an
# equivalent, deliberately broken candidate-select-then-delete flow -- the
# exact unlocked-SELECT shape scripts/retention_job.py's own inline comment
# describes as the pre-Package-S bug -- under the identical forced-overlap
# barrier, and showing it CANNOT satisfy the same positive contract.
# ---------------------------------------------------------------------------


def _broken_worker_run(
    database_url: str, worker_index: int, barrier: threading.Barrier, scoped_ids: list[str]
) -> dict:
    """Deliberately broken: the exact pre-Package-S candidate-selection
    shape (a plain SELECT with NO locking at all), scoped to this negative
    control's own rows only so it can never pick up unrelated rows from
    other tests sharing this module-scoped database. This function is never
    used by production code and never will be -- it exists solely to prove
    that the forced-overlap barrier methodology can detect a real
    regression, not just pass by construction.
    """
    engine = create_engine(database_url)
    session = sessionmaker(bind=engine)()
    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=30)
        pk_column = AuditEvent.audit_id
        ts_column = AuditEvent.created_at

        candidates = session.execute(
            select(pk_column, ts_column)
            .where(ts_column < cutoff, pk_column.in_(scoped_ids))
            .order_by(ts_column.asc(), pk_column.asc())
            .limit(3)
            # Deliberately NO .with_for_update() at all -- this omission is
            # the entire point of the negative control.
        ).all()
        raw_pks = [pk for pk, _ in candidates]

        # Same forced-overlap point as the real (locked) worker: block here,
        # under whatever this statement returned, until all four broken
        # workers have also finished their own unlocked select. Because
        # nothing locked these rows, every worker is guaranteed to observe
        # the IDENTICAL snapshot -- the deterministic reproduction of the
        # historical bug.
        barrier.wait(timeout=_BARRIER_TIMEOUT_SECONDS)

        if not raw_pks:
            return {"deleted_ids": set(), "deleted_count": 0}

        deleted_rows = session.execute(
            AuditEvent.__table__.delete()
            .where(pk_column.in_(raw_pks), ts_column < cutoff)
            .returning(pk_column)
        ).all()
        session.commit()
        return {
            "deleted_ids": {row[0] for row in deleted_rows},
            "deleted_count": len(deleted_rows),
        }
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def test_negative_control_without_skip_locked_fails_the_same_contract(postgres_head_database):
    """Deterministic proof that the forced-overlap barrier methodology is
    meaningful, not just theater. Four workers use the broken (unlocked)
    candidate-selection shape above, forced via the same barrier to all
    complete their SELECT -- observing the identical unlocked snapshot --
    before any of them proceeds to DELETE.

    The outcome is deterministic PostgreSQL MVCC/row-lock behavior, not a
    timing race: all four workers select the same 3 oldest rows (the only
    ones any of them ever sees, since none locks anything); whichever
    transaction's DELETE commits first genuinely removes those 3 rows; the
    other three transactions block on those rows' locks, and once
    unblocked, re-check their WHERE clause against the now-current data,
    find the rows already gone, and delete 0. The other 8 expired rows are
    never selected by anyone. This test asserts that exact, reproducible
    failure -- proving the SAME positive contract the real drill satisfies
    (union == all expired IDs, sum == 11) is NOT satisfiable without real
    locking, even under forced overlap.
    """
    database_url = postgres_head_database
    engine = create_engine(database_url)
    try:
        setup_session = sessionmaker(bind=engine)()
        expired_ids = [f"pkgv-negctrl-expired-{i}" for i in range(11)]
        young_ids = [f"pkgv-negctrl-young-{i}" for i in range(2)]
        for event_id in expired_ids:
            _insert_audit_event(setup_session, age_days=40, event_id=event_id)
        for event_id in young_ids:
            _insert_audit_event(setup_session, age_days=1, event_id=event_id)
        setup_session.close()

        barrier = threading.Barrier(4, timeout=_BARRIER_TIMEOUT_SECONDS)
        try:
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures = [
                    pool.submit(_broken_worker_run, database_url, i, barrier, expired_ids)
                    for i in range(4)
                ]
                results = [
                    future.result(timeout=_BARRIER_TIMEOUT_SECONDS + 5) for future in futures
                ]
        except threading.BrokenBarrierError as exc:
            pytest.fail(f"barrier failed to synchronize the negative control: {exc}")

        deleted_sets = [r["deleted_ids"] for r in results]
        union = set().union(*deleted_sets)
        total_deleted = sum(r["deleted_count"] for r in results)

        # The deterministic failure this negative control proves: only the
        # 3 oldest rows (ties broken by primary key, matching the real
        # retention job's own ORDER BY) are ever deleted; the other 8
        # expired rows are never selected by anyone, because every worker
        # observed the identical unlocked snapshot before any of them wrote.
        expected_only_deleted = set(expired_ids[:3])
        assert union == expected_only_deleted, (
            "the negative control must fail the SAME positive contract the real drill "
            f"satisfies -- got union={union!r}, expected exactly {expected_only_deleted!r}"
        )
        assert total_deleted == 3
        assert union != set(expired_ids)

        verify_session = sessionmaker(bind=engine)()
        try:
            remaining = verify_session.execute(
                text("SELECT count(*) FROM audit_events WHERE audit_id IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"ids": expired_ids},
            ).scalar_one()
            young_remaining = verify_session.execute(
                text("SELECT count(*) FROM audit_events WHERE audit_id IN :ids").bindparams(
                    bindparam("ids", expanding=True)
                ),
                {"ids": young_ids},
            ).scalar_one()
            assert remaining == 8  # the 8 rows the broken shape never even selected
            assert young_remaining == 2
        finally:
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
