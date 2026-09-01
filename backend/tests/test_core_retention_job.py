"""Tests for scripts/retention_job.py -- Package P.

Two concerns are tested separately: (1) that the job is a provable no-op
against the REAL retention registry through the PUBLIC API, since no
category has a cited maximum retention today, and the public API can never
be redirected to a different registry; (2) that the deletion mechanism
itself actually works, proven by calling the PRIVATE
`_enforce_maximum_retention_core` directly with a synthetic, clearly
test-only policy/table mapping that is never merged into the real registry
and is never reachable from the public function.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.selectable import Select

from db.database import Base
from models import (  # noqa: F401 -- registers every model so FK/relationship resolution succeeds
    accuracy_history,
    dungeon,
    governance,
    guild,
    identity,
    learning,
    player,
    question,
    session,
    submission,
)
from models.governance import AuditEvent
from scripts.retention_job import (
    CATEGORY_TABLES,
    DEFAULT_BATCH_SIZE,
    RetentionJobError,
    _enforce_maximum_retention_core,
    enforce_maximum_retention,
)
from security.retention import RETENTION_POLICIES, RetentionPolicy


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()


def _insert_audit_event(db, *, age_days: float, event_id: str) -> None:
    created_at = datetime.now(timezone.utc) - timedelta(days=age_days)
    db.add(
        AuditEvent(
            audit_id=event_id,
            actor="test",
            action="synthetic.event",
            entity_type="test",
            created_at=created_at,
        )
    )
    db.commit()


# ---------------------------------------------------------------------------
# 1. Public API: fixed to the real registry, provable no-op today, and
# provably NOT redirectable to a synthetic/uncited policy.
# ---------------------------------------------------------------------------


def test_real_registry_has_no_category_with_a_cited_maximum():
    # If this ever fails, a real maximum was added to RETENTION_POLICIES --
    # which is fine, but it means the "always a no-op today" claim below
    # (and in this module's own docstring) needs to be re-verified, not
    # silently left stale.
    assert all(p.maximum_retention_days is None for p in RETENTION_POLICIES.values())


def test_enforce_maximum_retention_is_a_noop_against_the_real_registry(db):
    _insert_audit_event(db, age_days=100_000, event_id="ancient-event")
    result = enforce_maximum_retention(
        db, "retain_append_only_security_log_duration_policy_pending", apply=True
    )
    assert result.candidate_count == 0
    assert result.deleted_count == 0
    assert "no cited maximum retention" in result.reason
    # Nothing was touched -- the ancient row is still there.
    assert db.query(AuditEvent).filter_by(audit_id="ancient-event").count() == 1


def test_enforce_maximum_retention_rejects_an_unknown_category(db):
    with pytest.raises(RetentionJobError, match="unknown retention category"):
        enforce_maximum_retention(db, "not_a_real_category")


def test_public_api_cannot_be_redirected_to_a_synthetic_registry(db):
    # This is the exact production-registry-bypass finding: an earlier
    # version of enforce_maximum_retention() accepted policies=/table_map=
    # kwargs and defaulted them to the real registries, which meant any
    # ordinary caller could override them with an uncited ceiling and
    # delete real rows through the PUBLIC function. It must not accept
    # those kwargs at all now.
    synthetic_policies = {
        "retain_append_only_security_log_duration_policy_pending": RetentionPolicy(
            category="retain_append_only_security_log_duration_policy_pending",
            minimum_retention_days=None,
            minimum_retention_source=None,
            maximum_retention_days=1,
            maximum_retention_source="an attacker-supplied, uncited ceiling",
            notes="must never be reachable through the public API",
        ),
    }
    with pytest.raises(TypeError):
        enforce_maximum_retention(
            db,
            "retain_append_only_security_log_duration_policy_pending",
            apply=True,
            policies=synthetic_policies,  # type: ignore[call-arg]
        )
    with pytest.raises(TypeError):
        enforce_maximum_retention(
            db,
            "retain_append_only_security_log_duration_policy_pending",
            apply=True,
            table_map=CATEGORY_TABLES,  # type: ignore[call-arg]
        )


def test_enforce_maximum_retention_rejects_an_invalid_batch_size(db):
    with pytest.raises(RetentionJobError, match="positive non-boolean integer"):
        enforce_maximum_retention(
            db, "retain_append_only_security_log_duration_policy_pending", batch_size=0
        )
    with pytest.raises(RetentionJobError, match="positive non-boolean integer"):
        enforce_maximum_retention(
            db, "retain_append_only_security_log_duration_policy_pending", batch_size=-5
        )
    with pytest.raises(RetentionJobError, match="positive non-boolean integer"):
        enforce_maximum_retention(
            db, "retain_append_only_security_log_duration_policy_pending", batch_size=True
        )


def test_enforce_maximum_retention_rejects_an_absurdly_large_batch_size(db):
    # A positive integer alone is not a safe operational bound -- an
    # unreasonably large batch_size must be rejected even though the real
    # registry's current no-op means it would never actually touch a row.
    with pytest.raises(RetentionJobError, match="at most"):
        enforce_maximum_retention(
            db,
            "retain_append_only_security_log_duration_policy_pending",
            batch_size=1_000_000_000,
        )


def test_migration_gate_runs_even_when_the_real_policy_is_a_noop(db, monkeypatch):
    # The destructive-path migration-head gate must fire before the
    # "no cited maximum -- nothing to enforce" early return, not after it --
    # otherwise a genuinely unmigrated PostgreSQL database behind today's
    # no-op real registry would silently look like a clean, checked run.
    _monkeypatch_bind_to_fake_postgresql(db, monkeypatch)
    checked = []
    monkeypatch.setattr(
        "scripts.retention_job.require_database_at_migration_head",
        lambda bind: checked.append(bind),
    )

    result = enforce_maximum_retention(
        db, "retain_append_only_security_log_duration_policy_pending", apply=True
    )

    assert len(checked) == 1
    assert result.deleted_count == 0
    assert result.reason and "no cited maximum" in result.reason


def test_total_race_loss_reports_zero_and_writes_no_audit_event(db, monkeypatch):
    # If every originally-selected candidate is already gone by the time
    # this call's own DELETE ... RETURNING runs (a total race loss against
    # a concurrent deleter), the result must report zero across the board
    # -- not the stale pre-race candidate count -- and no audit event
    # describing a deletion that did not happen may be written.
    _insert_audit_event(db, age_days=40, event_id="old-event")

    def _fake_returning_nothing(*args, **kwargs):
        class _Empty:
            @staticmethod
            def all():
                return []

        return _Empty()

    real_execute = db.execute

    def _wrapped_execute(statement, *args, **kwargs):
        from sqlalchemy.sql.dml import Delete

        if isinstance(statement, Delete):
            return _fake_returning_nothing()
        return real_execute(statement, *args, **kwargs)

    db.execute = _wrapped_execute
    audit_calls = []
    monkeypatch.setattr(
        "scripts.retention_job.record_audit_event",
        lambda *a, **k: audit_calls.append((a, k)),
    )
    try:
        result = _core(db, apply=True)
    finally:
        db.execute = real_execute

    assert result.candidate_count == 0
    assert result.deleted_count == 0
    assert result.deleted_ids == ()
    assert audit_calls == []
    # The fake completely replaces the DELETE's execution (never calling the
    # real one), so the row is never actually removed -- this test exercises
    # only the reporting/audit contract for a RETURNING-empty result, not a
    # real deletion outcome.
    assert db.query(AuditEvent).filter_by(audit_id="old-event").count() == 1


# ---------------------------------------------------------------------------
# 2. Private core: proves the deletion mechanism itself is correct, called
# directly with a synthetic, clearly test-only policy/table mapping. This
# maximum (30 days) is a TEST FIXTURE ONLY -- it is never added to the real
# security.retention.RETENTION_POLICIES registry, and this synthetic path is
# never reachable from the public enforce_maximum_retention().
# ---------------------------------------------------------------------------

_SYNTHETIC_CATEGORY = "retain_append_only_security_log_duration_policy_pending"
_SYNTHETIC_POLICIES = {
    _SYNTHETIC_CATEGORY: RetentionPolicy(
        category=_SYNTHETIC_CATEGORY,
        minimum_retention_days=None,
        minimum_retention_source=None,
        maximum_retention_days=30,
        maximum_retention_source="synthetic test-only source, not a real citation",
        notes="test only",
    ),
}


def _core(db, *, apply, batch_size=DEFAULT_BATCH_SIZE, now=None, actor="test"):
    return _enforce_maximum_retention_core(
        db,
        _SYNTHETIC_CATEGORY,
        apply=apply,
        policies=_SYNTHETIC_POLICIES,
        table_map=CATEGORY_TABLES,
        batch_size=batch_size,
        now=now,
        actor=actor,
    )


def test_enforce_maximum_retention_refuses_a_category_with_no_table_mapping(db):
    synthetic_policies = {
        "delete_with_verified_subject_request": RetentionPolicy(
            category="delete_with_verified_subject_request",
            minimum_retention_days=None,
            minimum_retention_source=None,
            maximum_retention_days=30,
            maximum_retention_source="synthetic test-only source",
            notes="test only",
        ),
    }
    with pytest.raises(RetentionJobError, match="no registered table mapping"):
        _enforce_maximum_retention_core(
            db,
            "delete_with_verified_subject_request",
            apply=True,
            policies=synthetic_policies,
            table_map=CATEGORY_TABLES,
            batch_size=DEFAULT_BATCH_SIZE,
            now=None,
            actor="test",
        )


def test_dry_run_reports_candidates_without_deleting(db):
    _insert_audit_event(db, age_days=40, event_id="old-event")
    _insert_audit_event(db, age_days=10, event_id="young-event")

    result = _core(db, apply=False)

    assert result.dry_run is True
    assert result.candidate_count == 1
    assert result.deleted_count == 0
    assert result.deleted_ids == ("old-event",)
    # Dry run must not have deleted anything.
    assert db.query(AuditEvent).count() == 2


def test_apply_deletes_only_rows_older_than_the_maximum(db):
    _insert_audit_event(db, age_days=40, event_id="old-event")
    _insert_audit_event(db, age_days=29, event_id="just-under-event")
    _insert_audit_event(db, age_days=10, event_id="young-event")

    result = _core(db, apply=True)

    assert result.dry_run is False
    assert result.candidate_count == 1
    assert result.deleted_count == 1
    assert result.deleted_ids == ("old-event",)

    remaining_ids = {row.audit_id for row in db.query(AuditEvent).all()}
    assert "old-event" not in remaining_ids
    assert "just-under-event" in remaining_ids
    assert "young-event" in remaining_ids


def test_delete_rechecks_the_age_condition_not_just_the_selected_pk(db):
    # If a candidate's timestamp is corrected (updated) to no longer be
    # expired between the SELECT and this call's own DELETE, the DELETE
    # must not remove it just because it was a candidate a moment ago --
    # PK membership alone is stale evidence; the age condition must be
    # rechecked in the DELETE predicate itself.
    _insert_audit_event(db, age_days=40, event_id="corrected-event")
    real_execute = db.execute
    seen = {"select": False}

    def _wrapped_execute(statement, *args, **kwargs):
        result = real_execute(statement, *args, **kwargs)
        if not seen["select"] and isinstance(statement, Select):
            seen["select"] = True
            real_execute(
                text("UPDATE audit_events SET created_at = :now WHERE audit_id = :id"),
                {"now": datetime.now(timezone.utc), "id": "corrected-event"},
            )
        return result

    db.execute = _wrapped_execute
    try:
        result = _core(db, apply=True)
    finally:
        db.execute = real_execute

    assert result.deleted_count == 0
    assert db.query(AuditEvent).filter_by(audit_id="corrected-event").count() == 1


def test_apply_writes_exactly_one_audit_event_describing_the_deletion(db):
    _insert_audit_event(db, age_days=40, event_id="old-event")

    _core(db, apply=True)

    events = db.query(AuditEvent).filter_by(action="retention_job.enforce_maximum").all()
    assert len(events) == 1
    event = events[0]
    assert event.entity_type == _SYNTHETIC_CATEGORY
    assert event.details["deleted_count"] == 1
    assert event.details["candidate_count"] == 1
    assert event.details["maximum_retention_days"] == 30
    assert "synthetic test-only source" in event.details["maximum_retention_source"]


def test_apply_with_zero_candidates_deletes_nothing_and_writes_no_audit_event(db):
    _insert_audit_event(db, age_days=5, event_id="young-event")

    result = _core(db, apply=True)

    assert result.candidate_count == 0
    assert result.deleted_count == 0
    assert db.query(AuditEvent).filter_by(action="retention_job.enforce_maximum").count() == 0
    assert db.query(AuditEvent).filter_by(audit_id="young-event").count() == 1


def test_category_tables_only_registers_the_retain_only_category():
    # delete_with_verified_subject_request / scrub_with_verified_subject_request
    # must never be eligible for age-based automated deletion -- they are
    # deleted/scrubbed only on a verified subject request.
    assert set(CATEGORY_TABLES) == {"retain_append_only_security_log_duration_policy_pending"}


# ---------------------------------------------------------------------------
# 3. Bounded batch size + deterministic ordering.
# ---------------------------------------------------------------------------


def test_batch_size_bounds_a_single_run_and_reports_more_remain(db):
    # 5 candidates, oldest to newest 50, 49, 48, 47, 46 days old; batch_size=2
    # must process exactly the two OLDEST rows and report more remain.
    for offset, days in enumerate([50, 49, 48, 47, 46]):
        _insert_audit_event(db, age_days=days, event_id=f"event-{offset}")

    result = _core(db, apply=True, batch_size=2)

    assert result.candidate_count == 2
    assert result.deleted_count == 2
    assert set(result.deleted_ids) == {"event-0", "event-1"}  # the two oldest
    assert result.more_remain is True
    # 5 originals - 2 deleted + 1 new audit event describing this deletion.
    assert db.query(AuditEvent).count() == 4


def test_batch_size_reports_no_more_remain_once_the_last_batch_clears(db):
    for offset, days in enumerate([50, 49]):
        _insert_audit_event(db, age_days=days, event_id=f"event-{offset}")

    result = _core(db, apply=True, batch_size=10)

    assert result.candidate_count == 2
    assert result.deleted_count == 2
    assert result.more_remain is False


def test_batch_size_ordering_is_deterministic_oldest_first(db):
    # Insert out of chronological order; the batch must still process the
    # oldest rows first regardless of insertion order.
    _insert_audit_event(db, age_days=45, event_id="middle")
    _insert_audit_event(db, age_days=60, event_id="oldest")
    _insert_audit_event(db, age_days=40, event_id="youngest-of-the-old")

    result = _core(db, apply=True, batch_size=1)

    assert result.deleted_ids == ("oldest",)


def test_core_rejects_an_invalid_batch_size_before_touching_the_database(db):
    _insert_audit_event(db, age_days=40, event_id="old-event")
    with pytest.raises(RetentionJobError, match="positive non-boolean integer"):
        _core(db, apply=True, batch_size=0)
    # Nothing was touched.
    assert db.query(AuditEvent).filter_by(audit_id="old-event").count() == 1


# ---------------------------------------------------------------------------
# 4. Concurrent-rerun evidence: deleted_ids/deleted_count must reflect what
# THIS call actually deleted (via RETURNING), not merely what it selected as
# candidates, even if another process deletes a candidate in between.
# ---------------------------------------------------------------------------


def test_apply_reports_only_rows_actually_deleted_by_this_call(db):
    _insert_audit_event(db, age_days=40, event_id="old-event-a")
    _insert_audit_event(db, age_days=40, event_id="old-event-b")

    real_execute = db.execute
    state = {"select_seen": False}

    def _wrapped_execute(statement, *args, **kwargs):
        result = real_execute(statement, *args, **kwargs)
        if not state["select_seen"] and isinstance(statement, Select):
            state["select_seen"] = True
            # Simulate a row disappearing between this call's own SELECT
            # (which sees both rows as candidates) and its DELETE -- e.g. a
            # concurrent process winning the race and deleting it first.
            # Issued through the same session/connection so the test stays
            # deterministic and free of real cross-connection SQLite file
            # locking; the property under test -- deleted_ids/deleted_count
            # must reflect this call's own DELETE ... RETURNING, not the
            # earlier candidate set -- does not depend on *how* the row
            # disappeared, only on whether the code trusts stale evidence.
            real_execute(text("DELETE FROM audit_events WHERE audit_id = 'old-event-a'"))
        return result

    db.execute = _wrapped_execute
    try:
        result = _enforce_maximum_retention_core(
            db,
            _SYNTHETIC_CATEGORY,
            apply=True,
            policies=_SYNTHETIC_POLICIES,
            table_map=CATEGORY_TABLES,
            batch_size=DEFAULT_BATCH_SIZE,
            now=None,
            actor="test",
        )
    finally:
        db.execute = real_execute

    # The SELECT saw both rows as candidates -- candidate_count reflects
    # that -- but only old-event-b was actually removed by THIS call's own
    # DELETE ... RETURNING; old-event-a was already gone by then.
    assert result.candidate_count == 2
    assert result.deleted_count == 1
    assert result.deleted_ids == ("old-event-b",)


# ---------------------------------------------------------------------------
# 5. Destructive PostgreSQL migration-head gate (SQLite demo profile exempt).
# ---------------------------------------------------------------------------


def test_apply_is_not_gated_by_migration_head_on_sqlite(db):
    # SQLite is the documented zero-setup demo profile and is never
    # Alembic-managed -- this fixture's in-memory engine has no
    # alembic_version table at all, so if the gate applied here, every
    # SQLite-backed apply would fail outright, which is wrong.
    _insert_audit_event(db, age_days=40, event_id="old-event")
    result = _core(db, apply=True)
    assert result.deleted_count == 1


def _monkeypatch_bind_to_fake_postgresql(db, monkeypatch):
    # db.get_bind() is called two ways: our own job code calls it with no
    # arguments to check the dialect; SQLAlchemy's ORM session machinery
    # calls it internally with keyword arguments (e.g. clause=...) for
    # every query it executes. Only fake the former -- delegating the
    # latter to the real method -- or every query through this session
    # breaks, not just the dialect check.
    real_get_bind = db.get_bind

    class _FakeDialect:
        name = "postgresql"

    class _FakeBind:
        dialect = _FakeDialect()

    def _fake_get_bind(*args, **kwargs):
        if not args and not kwargs:
            return _FakeBind()
        return real_get_bind(*args, **kwargs)

    monkeypatch.setattr(db, "get_bind", _fake_get_bind)


def test_apply_is_gated_by_migration_head_on_postgresql(db, monkeypatch):
    _insert_audit_event(db, age_days=40, event_id="old-event")
    _monkeypatch_bind_to_fake_postgresql(db, monkeypatch)
    monkeypatch.setattr(
        "scripts.retention_job.require_database_at_migration_head",
        lambda bind: (_ for _ in ()).throw(RuntimeError("current=unversioned, required=abc123")),
    )

    with pytest.raises(RetentionJobError, match="database revision check failed"):
        _core(db, apply=True)
    # Refused before touching any row.
    assert db.query(AuditEvent).filter_by(audit_id="old-event").count() == 1


def test_dry_run_is_not_gated_by_migration_head_on_postgresql(db, monkeypatch):
    # A report-only dry run deletes nothing, so it must not be blocked by
    # the destructive-path migration gate even when pointed at a
    # (simulated) not-at-head PostgreSQL database.
    _insert_audit_event(db, age_days=40, event_id="old-event")
    _monkeypatch_bind_to_fake_postgresql(db, monkeypatch)

    def _explode(bind):
        raise AssertionError("migration-head must not be checked for a dry run")

    monkeypatch.setattr("scripts.retention_job.require_database_at_migration_head", _explode)

    result = _core(db, apply=False)
    assert result.candidate_count == 1
