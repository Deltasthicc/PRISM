"""SIH26075 CC-01/CC-10: self-service registration + admin approval.

Follows the exact SQLite in-memory fixture pattern established in
tests/test_core_rbac.py so this suite exercises the real ORM models/
constraints (including the two new CHECK constraints on
`identity_bindings`), not a mock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from db.database import Base
from models.accuracy_history import AccuracyHistory  # noqa: F401
from models.dungeon import Dungeon, Room  # noqa: F401
from models.governance import AuditEvent
from models.guild import Guild  # noqa: F401
from models.identity import IdentityBinding
from models.learning import (  # noqa: F401
    CompetencyAssessment,
    GeneratedQuiz,
    LearnerProfile,
    LearningMaterial,
)
from models.player import Player
from models.question import Question  # noqa: F401
from models.session import GameSession  # noqa: F401
from models.submission import AnswerSubmission  # noqa: F401
from security.rbac import (
    AuthorizationError,
    IdentityBindingConflict,
    PrincipalBindingError,
    create_self_service_registration,
    decide_self_registration,
    list_pending_registrations,
    resolve_bound_principal,
)

ISSUER = "https://identity.example.test/realms/sih"


@dataclass(frozen=True)
class SyntheticSubject:
    subject_id: str
    issuer: str = ISSUER
    roles: frozenset[str] = frozenset()
    username: str | None = None
    expires_at: datetime = datetime(2030, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


def _admin_principal(db):
    binding = IdentityBinding(
        binding_id="binding-admin",
        issuer=ISSUER,
        subject_id="admin-subject",
        player_id=None,
        active=True,
    )
    db.add(binding)
    db.commit()
    return resolve_bound_principal(
        db, SyntheticSubject(subject_id="admin-subject", roles=frozenset({"organization_admin"}))
    )


def test_self_registration_creates_inactive_binding_player_and_profile(db):
    binding = create_self_service_registration(
        db,
        subject=SyntheticSubject(subject_id="new-trainer"),
        username="new_trainer",
        requested_role="trainer",
        full_name="New Trainer",
        designation="Training Officer",
        department="IMD",
        notes="I run onboarding for coastal stations",
    )
    assert binding.active is False
    assert binding.requested_role == "trainer"
    assert binding.registration_decision is None
    assert binding.player_id is not None

    player = db.query(Player).filter(Player.player_id == binding.player_id).one()
    assert player.username == "new_trainer"
    profile = db.query(LearnerProfile).filter(LearnerProfile.player_id == player.player_id).one()
    assert profile.full_name == "New Trainer"
    assert profile.department == "IMD"


@pytest.mark.parametrize("elevated_role", ["organization_admin", "department_admin", "content_reviewer", "auditor"])
def test_self_registration_rejects_elevated_roles(db, elevated_role):
    with pytest.raises(AuthorizationError):
        create_self_service_registration(
            db,
            subject=SyntheticSubject(subject_id="wannabe-admin"),
            username="wannabe_admin",
            requested_role=elevated_role,
            full_name="Wannabe Admin",
        )
    # No half-created row leaked through despite the rejection.
    assert db.query(IdentityBinding).count() == 0
    assert db.query(Player).count() == 0


def test_self_registration_rejects_duplicate_identity(db):
    create_self_service_registration(
        db,
        subject=SyntheticSubject(subject_id="dup-subject"),
        username="first_username",
        requested_role="learner",
        full_name="First Attempt",
    )
    with pytest.raises(IdentityBindingConflict):
        create_self_service_registration(
            db,
            subject=SyntheticSubject(subject_id="dup-subject"),
            username="second_username",
            requested_role="learner",
            full_name="Second Attempt",
        )


def test_self_registration_rejects_duplicate_username(db):
    create_self_service_registration(
        db,
        subject=SyntheticSubject(subject_id="subject-a"),
        username="shared_name",
        requested_role="learner",
        full_name="A",
    )
    with pytest.raises(IdentityBindingConflict):
        create_self_service_registration(
            db,
            subject=SyntheticSubject(subject_id="subject-b"),
            username="shared_name",
            requested_role="learner",
            full_name="B",
        )


def test_pending_registrations_requires_identity_binding_manage_permission(db):
    create_self_service_registration(
        db,
        subject=SyntheticSubject(subject_id="pending-subject"),
        username="pending_user",
        requested_role="trainer",
        full_name="Pending Person",
    )
    learner_binding = IdentityBinding(
        binding_id="binding-learner",
        issuer=ISSUER,
        subject_id="plain-learner",
        player_id=None,
        active=True,
    )
    db.add(learner_binding)
    db.commit()
    learner_principal = resolve_bound_principal(
        db, SyntheticSubject(subject_id="plain-learner", roles=frozenset({"learner"}))
    )
    with pytest.raises(AuthorizationError):
        list_pending_registrations(db, actor=learner_principal)


def test_admin_sees_pending_and_approve_activates_binding(db):
    admin = _admin_principal(db)
    binding = create_self_service_registration(
        db,
        subject=SyntheticSubject(subject_id="approve-me"),
        username="approve_me",
        requested_role="trainer",
        full_name="Approve Me",
    )

    pending = list_pending_registrations(db, actor=admin)
    assert [row.binding_id for row in pending] == [binding.binding_id]

    decided = decide_self_registration(
        db, actor=admin, binding_id=binding.binding_id, decision="approved", notes="looks right"
    )
    assert decided.active is True
    assert decided.registration_decision == "approved"
    assert decided.registration_reviewed_by == admin.audit_actor

    # Resolved now, so it drops out of the pending queue.
    assert list_pending_registrations(db, actor=admin) == []

    audit_actions = [row.action for row in db.query(AuditEvent).all()]
    assert "identity_binding.self_register" in audit_actions
    assert "identity_binding.registration_decided" in audit_actions


def test_admin_reject_leaves_binding_inactive(db):
    admin = _admin_principal(db)
    binding = create_self_service_registration(
        db,
        subject=SyntheticSubject(subject_id="reject-me"),
        username="reject_me",
        requested_role="learner",
        full_name="Reject Me",
    )
    decided = decide_self_registration(
        db, actor=admin, binding_id=binding.binding_id, decision="rejected", notes="duplicate account"
    )
    assert decided.active is False
    assert decided.registration_decision == "rejected"
    assert list_pending_registrations(db, actor=admin) == []


def test_deciding_already_decided_registration_raises_not_found(db):
    admin = _admin_principal(db)
    binding = create_self_service_registration(
        db,
        subject=SyntheticSubject(subject_id="twice-decided"),
        username="twice_decided",
        requested_role="learner",
        full_name="Twice Decided",
    )
    decide_self_registration(db, actor=admin, binding_id=binding.binding_id, decision="approved")
    with pytest.raises(PrincipalBindingError):
        decide_self_registration(db, actor=admin, binding_id=binding.binding_id, decision="rejected")


def test_deciding_unknown_binding_raises_not_found(db):
    admin = _admin_principal(db)
    with pytest.raises(PrincipalBindingError):
        decide_self_registration(db, actor=admin, binding_id="does-not-exist", decision="approved")


def test_invalid_decision_value_rejected(db):
    admin = _admin_principal(db)
    binding = create_self_service_registration(
        db,
        subject=SyntheticSubject(subject_id="bad-decision"),
        username="bad_decision",
        requested_role="learner",
        full_name="Bad Decision",
    )
    with pytest.raises(AuthorizationError):
        decide_self_registration(db, actor=admin, binding_id=binding.binding_id, decision="maybe")
