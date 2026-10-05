"""HTTP contract for admin announcements and the home feed (routes/announcements.py).

Follows test_cohorts.py's isolated-app + in-memory-SQLite +
require_principal-override pattern.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import pytest

from db.database import Base, get_db
from models.player import Player
from models.enums import DEFAULT_LEARNING_MODE  # noqa: F401
from models.accuracy_history import AccuracyHistory  # noqa: F401
from models.question import Question  # noqa: F401
from models.submission import AnswerSubmission  # noqa: F401
from models.guild import Guild  # noqa: F401
from models.dungeon import Dungeon, Room  # noqa: F401
from models.session import GameSession  # noqa: F401
from models.learning import LearnerProfile, CompetencyAssessment, LearningMaterial, GeneratedQuiz  # noqa: F401
from models.governance import EvidenceRecord, RoleTarget, SourceVersion, AuditEvent
from models.identity import IdentityBinding  # noqa: F401
from models.question_bank import QuestionBankItem, QuestionBankAttempt  # noqa: F401
from models.dsa_submission import DsaSubmission  # noqa: F401
from models.course import Course
from models.course_enrollment import CourseEnrollment  # noqa: F401
from models.certificate import Certificate
from models.feedback import CourseFeedback  # noqa: F401
from models.cohort import Cohort, CohortMembership  # noqa: F401
from models.announcement import Announcement
from routes.authorization import require_principal
from routes.announcements import feed_router, router as announcements_router
from security.rbac import BoundPrincipal


class _Subject:
    def __init__(self, subject_id: str, roles: frozenset[str]):
        self.issuer = "https://issuer.example/realm"
        self.subject_id = subject_id
        self.roles = roles


def _principal(player_id: str | None, roles: frozenset[str]) -> BoundPrincipal:
    return BoundPrincipal(
        subject=_Subject(player_id or "no-player", roles),
        binding_id="binding-1",
        player_id=player_id,
        roles=roles,
    )


def _db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _app(db, principal: BoundPrincipal | None) -> FastAPI:
    app = FastAPI()
    app.include_router(announcements_router)
    app.include_router(feed_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    if principal is not None:
        app.dependency_overrides[require_principal] = lambda: principal
    return app


def _make_player(db, *, username_prefix: str = "player") -> str:
    player_id = str(uuid.uuid4())
    db.add(Player(player_id=player_id, username=f"{username_prefix}-{player_id[:8]}"))
    db.commit()
    return player_id


ADMIN_ROLES = frozenset({"organization_admin"})


def _admin_client(db):
    admin_id = _make_player(db, username_prefix="admin")
    return TestClient(_app(db, _principal(admin_id, ADMIN_ROLES))), admin_id


def _feed_client(db, roles: frozenset[str]):
    player_id = _make_player(db, username_prefix="user")
    return TestClient(_app(db, _principal(player_id, roles))), player_id


def _create(client, **overrides):
    payload = {"title": "Maintenance window", "body": "Portal is read-only on Sunday.", **overrides}
    return client.post("/learning/announcements", json=payload)


def _feed(client, player_id):
    response = client.get("/learning/home/feed", params={"player_id": player_id})
    assert response.status_code == 200, response.text
    return response.json()


# --- admin CRUD -----------------------------------------------------------


def test_admin_creates_draft_publishes_unpublishes_and_lists_everything():
    db = _db()
    client, admin_id = _admin_client(db)

    created = _create(client)
    assert created.status_code == 200
    body = created.json()
    assert body["status"] == "draft"
    assert body["is_published"] is False
    assert body["published_at"] is None
    assert body["kind"] == "announcement" and body["audience"] == "all"
    announcement_id = body["announcement_id"]

    published = client.post(f"/learning/announcements/{announcement_id}/publish")
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["published_at"] is not None

    unpublished = client.post(f"/learning/announcements/{announcement_id}/unpublish")
    assert unpublished.status_code == 200
    assert unpublished.json()["status"] == "unpublished"
    # History is kept: the original publication time is not erased.
    assert unpublished.json()["published_at"] is not None

    listed = client.get("/learning/announcements")
    assert listed.status_code == 200
    assert [row["announcement_id"] for row in listed.json()] == [announcement_id]


def test_create_with_publish_true_publishes_immediately():
    db = _db()
    client, _ = _admin_client(db)
    body = _create(client, publish=True, kind="achievement", audience="trainer").json()
    assert body["status"] == "published"
    assert body["kind"] == "achievement" and body["audience"] == "trainer"


def test_admin_list_includes_drafts_and_expired():
    db = _db()
    client, _ = _admin_client(db)
    draft_id = _create(client, title="Draft").json()["announcement_id"]
    expired_id = _create(client, title="Old", publish=True).json()["announcement_id"]
    # Force expiry directly (the API refuses to create an already-expired row).
    row = db.query(Announcement).filter(Announcement.announcement_id == expired_id).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    db.commit()

    by_id = {row["announcement_id"]: row for row in client.get("/learning/announcements").json()}
    assert by_id[draft_id]["status"] == "draft"
    assert by_id[expired_id]["status"] == "expired"


def test_non_admin_cannot_create_list_publish_or_unpublish():
    db = _db()
    admin_client, _ = _admin_client(db)
    announcement_id = _create(admin_client).json()["announcement_id"]

    for roles in (frozenset({"learner"}), frozenset({"trainer"}), frozenset({"department_admin"})):
        client, _ = _feed_client(db, roles)
        assert _create(client).status_code == 403
        assert client.get("/learning/announcements").status_code == 403
        assert client.post(f"/learning/announcements/{announcement_id}/publish").status_code == 403
        assert client.post(f"/learning/announcements/{announcement_id}/unpublish").status_code == 403


def test_publish_and_unpublish_unknown_id_are_404():
    db = _db()
    client, _ = _admin_client(db)
    assert client.post("/learning/announcements/nope/publish").status_code == 404
    assert client.post("/learning/announcements/nope/unpublish").status_code == 404


def test_publish_and_unpublish_are_idempotent():
    db = _db()
    client, _ = _admin_client(db)
    announcement_id = _create(client).json()["announcement_id"]

    first = client.post(f"/learning/announcements/{announcement_id}/publish").json()
    second = client.post(f"/learning/announcements/{announcement_id}/publish")
    assert second.status_code == 200
    assert second.json()["published_at"] == first["published_at"]

    client.post(f"/learning/announcements/{announcement_id}/unpublish")
    again = client.post(f"/learning/announcements/{announcement_id}/unpublish")
    assert again.status_code == 200
    assert again.json()["status"] == "unpublished"

    # Only the transitions that changed state were audited: create, publish, unpublish.
    actions = [event.action for event in db.query(AuditEvent).order_by(AuditEvent.created_at).all()]
    assert sorted(actions) == ["announcement.create", "announcement.publish", "announcement.unpublish"]


def test_create_publish_unpublish_are_audited_with_the_acting_admin():
    db = _db()
    client, _ = _admin_client(db)
    announcement_id = _create(client).json()["announcement_id"]
    client.post(f"/learning/announcements/{announcement_id}/publish")
    client.post(f"/learning/announcements/{announcement_id}/unpublish")

    events = db.query(AuditEvent).all()
    assert {event.action for event in events} == {
        "announcement.create",
        "announcement.publish",
        "announcement.unpublish",
    }
    assert all(event.entity_type == "announcement" for event in events)
    assert all(event.entity_id == announcement_id for event in events)
    assert all("issuer.example" in event.actor for event in events)


# --- validation -----------------------------------------------------------


@pytest.mark.parametrize(
    "overrides",
    [
        {"kind": "alert"},
        {"audience": "everyone"},
        {"title": "   "},
        {"body": ""},
        {"body": "   \n "},
        {"title": "x" * 201},
        {"body": "x" * 4001},
    ],
)
def test_invalid_input_is_422(overrides):
    db = _db()
    client, _ = _admin_client(db)
    assert _create(client, **overrides).status_code == 422
    assert db.query(Announcement).count() == 0


def test_title_and_body_are_stripped():
    db = _db()
    client, _ = _admin_client(db)
    body = _create(client, title="  Hello  ", body="  World \n").json()
    assert body["title"] == "Hello" and body["body"] == "World"


def test_expires_at_in_the_past_is_rejected_at_create_and_publish():
    db = _db()
    client, _ = _admin_client(db)
    past = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    assert _create(client, expires_at=past).status_code == 422
    assert _create(client, expires_at=past, publish=True).status_code == 422

    # A draft that has since passed its expiry cannot be published either.
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    announcement_id = _create(client, expires_at=future).json()["announcement_id"]
    row = db.query(Announcement).filter(Announcement.announcement_id == announcement_id).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
    db.commit()
    assert client.post(f"/learning/announcements/{announcement_id}/publish").status_code == 422
    assert db.query(Announcement).one().is_published is False


def test_expires_at_in_the_future_is_accepted():
    db = _db()
    client, _ = _admin_client(db)
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    body = _create(client, expires_at=future, publish=True).json()
    assert body["status"] == "published"
    assert body["expires_at"] is not None


def test_database_rejects_values_outside_the_closed_vocabularies():
    db = _db()
    base = dict(title="t", body="b", created_by="a")
    db.add(Announcement(kind="bogus", audience="all", **base))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(Announcement(kind="announcement", audience="bogus", **base))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


# --- feed: announcements --------------------------------------------------


def test_feed_is_honestly_empty_when_nothing_exists():
    db = _db()
    client, player_id = _feed_client(db, frozenset({"learner"}))
    body = _feed(client, player_id)
    assert set(body) == {"announcements", "new_courses", "my_achievements", "generated_at"}
    assert body["announcements"] == []
    assert body["new_courses"] == []
    assert body["my_achievements"] == []
    assert body["generated_at"]


def test_draft_unpublished_and_expired_are_hidden_from_the_feed():
    db = _db()
    admin, _ = _admin_client(db)
    _create(admin, title="Draft only")
    unpublished_id = _create(admin, title="Retired", publish=True).json()["announcement_id"]
    admin.post(f"/learning/announcements/{unpublished_id}/unpublish")
    expired_id = _create(admin, title="Expired", publish=True).json()["announcement_id"]
    row = db.query(Announcement).filter(Announcement.announcement_id == expired_id).one()
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    _create(admin, title="Visible", publish=True)

    client, player_id = _feed_client(db, frozenset({"learner"}))
    titles = [item["title"] for item in _feed(client, player_id)["announcements"]]
    assert titles == ["Visible"]


def test_feed_announcements_are_newest_first_and_capped_at_20():
    db = _db()
    admin, _ = _admin_client(db)
    base = datetime.now(timezone.utc) - timedelta(days=1)
    for index in range(22):
        db.add(
            Announcement(
                title=f"n{index:02d}",
                body="b",
                created_by="a",
                is_published=True,
                published_at=base + timedelta(minutes=index),
            )
        )
    db.commit()
    client, player_id = _feed_client(db, frozenset({"learner"}))
    titles = [item["title"] for item in _feed(client, player_id)["announcements"]]
    assert len(titles) == 20
    assert titles[0] == "n21" and titles[-1] == "n02"


def test_audience_filtering_by_role():
    db = _db()
    admin, _ = _admin_client(db)
    _create(admin, title="For all", audience="all", publish=True)
    _create(admin, title="For learners", audience="learner", publish=True)
    _create(admin, title="For trainers", audience="trainer", publish=True)

    learner, learner_id = _feed_client(db, frozenset({"learner"}))
    assert {i["title"] for i in _feed(learner, learner_id)["announcements"]} == {"For all", "For learners"}

    trainer, trainer_id = _feed_client(db, frozenset({"trainer"}))
    assert {i["title"] for i in _feed(trainer, trainer_id)["announcements"]} == {"For all", "For trainers"}

    both, both_id = _feed_client(db, frozenset({"learner", "trainer"}))
    assert {i["title"] for i in _feed(both, both_id)["announcements"]} == {
        "For all",
        "For learners",
        "For trainers",
    }

    # No roles at all (the documented demo fallback) is treated as a learner.
    # Such a principal fails the permission check, so exercise the helper directly.
    from routes.announcements import _audiences_for

    assert _audiences_for(_principal("p", frozenset())) == ["all", "learner"]


def test_feed_response_shape_for_an_announcement_is_exact():
    db = _db()
    admin, _ = _admin_client(db)
    _create(admin, title="Shape", kind="new_content", publish=True)
    client, player_id = _feed_client(db, frozenset({"learner"}))
    item = _feed(client, player_id)["announcements"][0]
    assert set(item) == {
        "announcement_id",
        "title",
        "body",
        "kind",
        "audience",
        "published_at",
        "expires_at",
    }
    assert item["kind"] == "new_content"


# --- feed: courses --------------------------------------------------------


def _add_course(db, trainer_id, title, *, age_days, published=True):
    course = Course(
        trainer_id=trainer_id,
        title=title,
        description="d",
        competency_id="c1",
        is_published=published,
        created_at=datetime.now(timezone.utc) - timedelta(days=age_days),
    )
    db.add(course)
    db.commit()
    return course


def test_new_courses_window_boundary_published_only_newest_first():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    _add_course(db, trainer_id, "29 days old", age_days=29)
    _add_course(db, trainer_id, "31 days old", age_days=31)
    _add_course(db, trainer_id, "2 days old", age_days=2)
    _add_course(db, trainer_id, "unpublished new", age_days=1, published=False)

    client, player_id = _feed_client(db, frozenset({"learner"}))
    courses = _feed(client, player_id)["new_courses"]
    assert [c["title"] for c in courses] == ["2 days old", "29 days old"]
    assert set(courses[0]) == {"course_id", "title", "description", "created_at"}


def test_new_courses_capped_at_10():
    db = _db()
    trainer_id = _make_player(db, username_prefix="trainer")
    for index in range(12):
        _add_course(db, trainer_id, f"c{index}", age_days=1 + index * 0.1)
    client, player_id = _feed_client(db, frozenset({"learner"}))
    assert len(_feed(client, player_id)["new_courses"]) == 10


# --- feed: achievements ---------------------------------------------------


def _add_certificate(db, player_id, title, *, age_days, revoked=False):
    db.add(
        Certificate(
            player_id=player_id,
            course_id=f"course-{title}",
            title=title,
            issued_at=datetime.now(timezone.utc) - timedelta(days=age_days),
            revoked=revoked,
        )
    )
    db.commit()


def test_feed_shows_only_the_callers_own_recent_certificates():
    db = _db()
    client, player_id = _feed_client(db, frozenset({"learner"}))
    other_id = _make_player(db, username_prefix="other")
    _add_certificate(db, player_id, "mine recent", age_days=5)
    _add_certificate(db, player_id, "mine 89 days", age_days=89)
    _add_certificate(db, player_id, "mine 91 days", age_days=91)
    _add_certificate(db, player_id, "mine revoked", age_days=1, revoked=True)
    _add_certificate(db, other_id, "someone else", age_days=1)

    achievements = _feed(client, player_id)["my_achievements"]
    assert [a["title"] for a in achievements] == ["mine recent", "mine 89 days"]
    assert set(achievements[0]) == {"certificate_id", "title", "course_id", "issued_at"}
    assert "someone else" not in str(_feed(client, player_id))


def test_feed_rejects_another_players_id():
    db = _db()
    client, _ = _feed_client(db, frozenset({"learner"}))
    other_id = _make_player(db, username_prefix="other")
    _add_certificate(db, other_id, "private", age_days=1)

    # require_own_player maps an out-of-scope player_id to 403 ("Access denied").
    response = client.get("/learning/home/feed", params={"player_id": other_id})
    assert response.status_code == 403
    assert "private" not in response.text


def test_feed_unknown_player_is_404_and_player_id_is_required():
    db = _db()
    player_id = _make_player(db)
    client = TestClient(_app(db, _principal(player_id, frozenset({"learner"}))))
    assert client.get("/learning/home/feed").status_code == 422

    # A principal bound to a player row that no longer exists.
    ghost = "ghost-player"
    ghost_client = TestClient(_app(db, _principal(ghost, frozenset({"learner"}))))
    assert ghost_client.get("/learning/home/feed", params={"player_id": ghost}).status_code == 404


def test_feed_allowed_for_trainer_and_both_admin_roles_but_not_reviewer():
    db = _db()
    for roles in (frozenset({"trainer"}), frozenset({"organization_admin"}), frozenset({"department_admin"})):
        client, player_id = _feed_client(db, roles)
        assert client.get("/learning/home/feed", params={"player_id": player_id}).status_code == 200
    client, player_id = _feed_client(db, frozenset({"content_reviewer"}))
    assert client.get("/learning/home/feed", params={"player_id": player_id}).status_code == 403
