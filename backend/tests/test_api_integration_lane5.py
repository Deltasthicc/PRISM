"""Lane 5 API, authorization, provider and analytics contract tests."""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base, get_db
from models.accuracy_history import AccuracyHistory  # noqa: F401 -- mapper registration
from models.dungeon import Dungeon, Room  # noqa: F401 -- mapper/FK registration
from models.guild import Guild  # noqa: F401 -- mapper/FK registration
from models.learning import CompetencyAssessment
from models.player import Player
from models.question import Question  # noqa: F401 -- mapper/FK registration
from models.session import GameSession  # noqa: F401 -- mapper registration
from models.submission import AnswerSubmission  # noqa: F401 -- mapper registration
from routes.learning import admin_overview, latest_assessment, router as learning_router
from routes.authorization import require_permission_dependency, require_principal
from security.identity import AuthenticationError
from security.rbac import BoundPrincipal, Permission
from integrations.provider import SimulatedIGOTAdapter


class Subject:
    issuer = "https://issuer.example/realm"
    subject_id = "subject-1"
    roles = frozenset({"organization_admin", "learner"})


def make_db():
    # TestClient executes sync dependencies/handlers in a worker thread. Match
    # the application's SQLite profile so this isolated route contract proves
    # authorization rather than failing at sqlite3's default thread guard.
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def make_principal(player_id=None):
    return BoundPrincipal(
        subject=Subject(),
        binding_id="binding-1",
        player_id=player_id,
        roles=Subject.roles,
    )


def test_admin_analytics_count_latest_assessment_stream_once():
    db = make_db()
    player = Player(username="learner-1")
    db.add(player)
    db.flush()
    db.add_all([
        CompetencyAssessment(
            assessment_id="old",
            player_id=player.player_id,
            curriculum_slug="official-statistics",
            skill_gaps=[{"label": "Old gap", "priority": "high"}],
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        CompetencyAssessment(
            assessment_id="new",
            player_id=player.player_id,
            curriculum_slug="official-statistics",
            skill_gaps=[{"label": "Current gap", "priority": "medium"}],
            created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        ),
    ])
    db.commit()

    result = __import__("asyncio").run(admin_overview(db, make_principal()))

    assert result["assessments_completed"] == 1
    assert result["top_skill_gaps"] == [{"competency": "Current gap", "learner_count": 1}]
    assert result["gap_priorities"] == {"medium": 1}


def test_latest_assessment_returns_latest_stream():
    db = make_db()
    player = Player(username="learner-2")
    db.add(player)
    db.flush()
    db.add_all([
        CompetencyAssessment(
            assessment_id="old",
            player_id=player.player_id,
            curriculum_slug="official-statistics",
            self_ratings={"old": 1},
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
        CompetencyAssessment(
            assessment_id="new",
            player_id=player.player_id,
            curriculum_slug="official-statistics",
            self_ratings={"new": 4},
            created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        ),
    ])
    db.commit()

    result = __import__("asyncio").run(
        latest_assessment(
            player.player_id,
            "official-statistics",
            db,
            make_principal(player.player_id),
        )
    )

    assert result["assessment"]["assessment_id"] == "new"
    assert result["assessment"]["self_ratings"] == {"new": 4}


def test_latest_assessment_route_uses_composed_own_player_scope():
    db = make_db()
    player = Player(username="route-scope-learner")
    db.add(player)
    db.flush()
    db.add(
        CompetencyAssessment(
            assessment_id="route-scope-assessment",
            player_id=player.player_id,
            curriculum_slug="official-statistics",
            created_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
    )
    db.commit()

    app = FastAPI()
    app.include_router(learning_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_principal] = lambda: make_principal(
        player.player_id
    )
    client = TestClient(app)

    own = client.get(
        f"/learning/assessment/{player.player_id}/latest",
        params={"curriculum_slug": "official-statistics"},
    )
    cross_player = client.get(
        "/learning/assessment/another-player/latest",
        params={"curriculum_slug": "official-statistics"},
    )

    assert own.status_code == 200
    assert own.json()["assessment"]["assessment_id"] == "route-scope-assessment"
    assert cross_player.status_code == 403
    assert cross_player.json() == {"detail": "Access denied"}


def test_simulated_igot_never_claims_live_capability():
    adapter = SimulatedIGOTAdapter()

    result = adapter.health_check()

    assert result.status == "SIMULATED"
    assert result.data == {"capabilities": []}
    assert adapter.request_enrolment("course-1", idempotency_key="request-1").data["accepted"] is False


def test_route_auth_adapter_returns_401_for_missing_or_invalid_bearer(monkeypatch):
    def reject(_header):
        raise AuthenticationError("invalid")

    monkeypatch.setattr("routes.authorization.get_current_subject", reject)

    with pytest.raises(HTTPException) as error:
        require_principal(None, make_db())

    assert error.value.status_code == 401
    assert error.value.headers == {"WWW-Authenticate": "Bearer"}


def test_route_auth_adapter_returns_403_for_missing_permission():
    dependency = require_permission_dependency(Permission.ORGANIZATION_ANALYTICS_READ)

    with pytest.raises(HTTPException) as error:
        dependency(make_principal("player-1").__class__(
            subject=Subject(), binding_id="binding-1", player_id="player-1", roles=frozenset({"learner"})
        ))

    assert error.value.status_code == 403


@pytest.mark.parametrize("permission", [Permission.ASSESSMENT_SELF_READ, Permission.ORGANIZATION_ANALYTICS_READ])
def test_lane5_permissions_are_explicit(permission):
    assert permission.value
