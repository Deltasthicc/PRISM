"""Adversarial tests for the one-time identity-binding bootstrap."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from db.database import Base, migration_head_revision
from models.governance import AuditEvent
from models.identity import IdentityBinding
from models.player import Player
from security.identity_bootstrap import (
    IdentityBootstrapConflict,
    IdentityBootstrapError,
    IdentityBootstrapValidationError,
    bootstrap_initial_organization_admin,
    expected_bootstrap_confirmation,
    main as bootstrap_main,
)


ISSUER = "https://identity.example.test/realms/sih"
SUBJECT_ID = "first-admin-external-subject"


@pytest.fixture
def migrated_session_factory(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'bootstrap.db'}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    Base.metadata.create_all(
        engine,
        tables=[Player.__table__, IdentityBinding.__table__, AuditEvent.__table__],
    )
    with engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        )
        connection.execute(
            text("INSERT INTO alembic_version (version_num) VALUES (:revision)"),
            {"revision": migration_head_revision()},
        )
    factory = sessionmaker(bind=engine)
    yield factory
    engine.dispose()


def _arguments(*, subject_id: str = SUBJECT_ID) -> dict[str, str]:
    return {
        "issuer": ISSUER,
        "subject_id": subject_id,
        "operator_reference": "approved-change-CR-26101",
        "reason": "initial controlled administrator bootstrap",
        "confirmation": expected_bootstrap_confirmation(ISSUER, subject_id),
    }


def test_bootstrap_creates_only_first_binding_and_atomic_audit(migrated_session_factory):
    db = migrated_session_factory()
    binding = bootstrap_initial_organization_admin(db, **_arguments())

    assert binding.issuer == ISSUER
    assert binding.subject_id == SUBJECT_ID
    assert binding.player_id is None
    assert binding.active is True
    event = db.query(AuditEvent).filter_by(action="identity_binding.bootstrap").one()
    assert event.entity_id == binding.binding_id
    assert event.actor == "out-of-band-bootstrap:approved-change-CR-26101"
    assert event.details == {
        "reason": "initial controlled administrator bootstrap",
        "expected_runtime_role": "organization_admin",
        "operator_reference_is_verified_oidc_identity": False,
    }
    db.close()


def test_wrong_confirmation_writes_nothing(migrated_session_factory):
    db = migrated_session_factory()
    arguments = _arguments()
    arguments["confirmation"] = "yes"

    with pytest.raises(IdentityBootstrapValidationError, match="exactly match"):
        bootstrap_initial_organization_admin(db, **arguments)

    assert db.query(IdentityBinding).count() == 0
    assert db.query(AuditEvent).count() == 0
    db.close()


def test_bootstrap_refuses_when_any_binding_already_exists(migrated_session_factory):
    first = migrated_session_factory()
    bootstrap_initial_organization_admin(first, **_arguments())
    first.close()

    second = migrated_session_factory()
    with pytest.raises(IdentityBootstrapConflict, match="already exists"):
        bootstrap_initial_organization_admin(
            second, **_arguments(subject_id="second-admin-subject")
        )
    assert second.query(IdentityBinding).count() == 1
    assert second.query(AuditEvent).count() == 1
    second.close()


def test_bootstrap_requires_database_at_migration_head(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'unversioned.db'}")
    Base.metadata.create_all(
        engine,
        tables=[Player.__table__, IdentityBinding.__table__, AuditEvent.__table__],
    )
    db = sessionmaker(bind=engine)()

    with pytest.raises(RuntimeError, match="current=unversioned"):
        bootstrap_initial_organization_admin(db, **_arguments())

    assert db.query(IdentityBinding).count() == 0
    db.close()
    engine.dispose()


def test_bootstrap_requires_a_fresh_session(migrated_session_factory):
    db = migrated_session_factory()
    db.execute(text("SELECT 1"))

    with pytest.raises(IdentityBootstrapError, match="fresh database session"):
        bootstrap_initial_organization_admin(db, **_arguments())

    db.rollback()
    assert db.query(IdentityBinding).count() == 0
    db.close()


def test_failed_commit_rolls_back_binding_and_audit(migrated_session_factory, monkeypatch):
    db = migrated_session_factory()

    def _fail_commit():
        raise RuntimeError("synthetic bootstrap commit failure")

    monkeypatch.setattr(db, "commit", _fail_commit)
    with pytest.raises(RuntimeError, match="synthetic bootstrap commit failure"):
        bootstrap_initial_organization_admin(db, **_arguments())
    db.close()

    observer = migrated_session_factory()
    assert observer.query(IdentityBinding).count() == 0
    assert observer.query(AuditEvent).count() == 0
    observer.close()


def test_concurrent_bootstrap_attempts_create_exactly_one_binding(
    migrated_session_factory,
):
    barrier = Barrier(2)

    def _attempt(subject_id: str) -> str:
        db = migrated_session_factory()
        try:
            barrier.wait(timeout=5)
            bootstrap_initial_organization_admin(
                db, **_arguments(subject_id=subject_id)
            )
            return "created"
        except IdentityBootstrapConflict:
            return "conflict"
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(
            executor.map(_attempt, ["concurrent-admin-a", "concurrent-admin-b"])
        )

    assert sorted(outcomes) == ["conflict", "created"]
    observer = migrated_session_factory()
    assert observer.query(IdentityBinding).count() == 1
    assert observer.query(AuditEvent).filter_by(action="identity_binding.bootstrap").count() == 1
    observer.close()


def test_cli_never_accepts_token_or_password_and_reports_success(
    migrated_session_factory, monkeypatch, capsys
):
    monkeypatch.setattr(
        "security.identity_bootstrap.SessionLocal", migrated_session_factory
    )
    confirmation = expected_bootstrap_confirmation(ISSUER, SUBJECT_ID)
    result = bootstrap_main(
        [
            "--issuer",
            ISSUER,
            "--subject-id",
            SUBJECT_ID,
            "--operator-reference",
            "approved-change-CR-26101",
            "--reason",
            "initial controlled administrator bootstrap",
            "--confirmation",
            confirmation,
        ]
    )

    captured = capsys.readouterr()
    assert result == 0
    assert "Runtime access still requires" in captured.out
    assert "token" not in captured.out.lower()
    assert captured.err == ""


@pytest.mark.parametrize(
    ("issuer", "subject_id"),
    [
        ("http://identity.example.test/realm", SUBJECT_ID),
        (ISSUER, ""),
        (ISSUER, " subject"),
        (ISSUER, "subject\x00id"),
    ],
)
def test_expected_confirmation_rejects_unsafe_identity_keys(issuer, subject_id):
    with pytest.raises(IdentityBootstrapValidationError):
        expected_bootstrap_confirmation(issuer, subject_id)
