"""HTTP contract for trainer-authored questionnaires (routes/questionnaires.py).

Follows test_cohorts.py's isolated-app + in-memory-SQLite +
require_principal-override pattern. Time is controlled through the module's
single injectable `utcnow()` so the deadline boundary is tested exactly.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

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
from models.governance import EvidenceRecord, RoleTarget, SourceVersion, AuditEvent  # noqa: F401
from models.identity import IdentityBinding  # noqa: F401
from models.question_bank import QuestionBankItem, QuestionBankAttempt  # noqa: F401
from models.dsa_submission import DsaSubmission  # noqa: F401
from models.course import Course
from models.course_enrollment import CourseEnrollment
from models.certificate import Certificate  # noqa: F401
from models.feedback import CourseFeedback  # noqa: F401
from models.cohort import Cohort, CohortMembership
from models.questionnaire import Questionnaire, QuestionnaireAttempt, QuestionnaireQuestion
import routes.questionnaires as questionnaires_module
from routes.authorization import require_principal
from routes.questionnaires import router as questionnaires_router
from security.rbac import BoundPrincipal

T0 = datetime(2026, 10, 5, 12, 0, 0, tzinfo=timezone.utc)
DUE = T0 + timedelta(days=1)


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


TRAINER_ROLES = frozenset({"trainer"})
LEARNER_ROLES = frozenset({"learner"})


class Clock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def clock(monkeypatch) -> Clock:
    c = Clock(T0)
    monkeypatch.setattr(questionnaires_module, "utcnow", c)
    return c


def _db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _client(db, principal: BoundPrincipal) -> TestClient:
    app = FastAPI()
    app.include_router(questionnaires_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_principal] = lambda: principal
    return TestClient(app)


def _make_player(db, prefix: str = "player") -> str:
    player_id = str(uuid.uuid4())
    db.add(Player(player_id=player_id, username=f"{prefix}-{player_id[:8]}"))
    db.commit()
    return player_id


def _make_cohort(db, trainer_id: str, members: list[str] | None = None) -> str:
    cohort = Cohort(name="Test Cohort", trainer_id=trainer_id)
    db.add(cohort)
    db.commit()
    for member in members or []:
        db.add(CohortMembership(cohort_id=cohort.cohort_id, player_id=member))
    db.commit()
    return cohort.cohort_id


def _make_course(db, trainer_id: str, enrolled: list[str] | None = None) -> str:
    course = Course(trainer_id=trainer_id, title="Course", description="", competency_id="os_gis")
    db.add(course)
    db.commit()
    for member in enrolled or []:
        db.add(
            CourseEnrollment(
                player_id=member,
                course_id=f"internal::{course.course_id}",
                provider="internal",
                competency_id="os_gis",
                title="Course",
            )
        )
    db.commit()
    return course.course_id


def _questions() -> list[dict]:
    return [
        {"prompt": "2 + 2?", "options": ["3", "4", "5"], "correct_index": 1},
        {"prompt": "Capital of India?", "options": ["Delhi", "Pune"], "correct_index": 0},
    ]


def _payload(trainer_id: str, audience_type: str, audience_id: str, **overrides) -> dict:
    body = {
        "trainer_id": trainer_id,
        "title": "Week 1 check",
        "description": "Short quiz",
        "audience_type": audience_type,
        "audience_id": audience_id,
        "due_at": DUE.isoformat(),
        "questions": _questions(),
    }
    body.update(overrides)
    return body


class World:
    """A trainer with a cohort of two trainees, plus an outsider."""

    def __init__(self):
        self.db = _db()
        self.trainer = _make_player(self.db, "trainer")
        self.trainee = _make_player(self.db, "trainee")
        self.trainee2 = _make_player(self.db, "trainee")
        self.outsider = _make_player(self.db, "outsider")
        self.other_trainer = _make_player(self.db, "trainer")
        self.cohort = _make_cohort(self.db, self.trainer, [self.trainee, self.trainee2])

    def trainer_client(self, who: str | None = None) -> TestClient:
        return _client(self.db, _principal(who or self.trainer, TRAINER_ROLES))

    def learner_client(self, who: str) -> TestClient:
        return _client(self.db, _principal(who, LEARNER_ROLES))

    def create(self, **overrides) -> dict:
        response = self.trainer_client().post(
            "/learning/questionnaires", json=_payload(self.trainer, "cohort", self.cohort, **overrides)
        )
        assert response.status_code == 200, response.text
        return response.json()

    def publish(self, questionnaire_id: str) -> dict:
        response = self.trainer_client().post(
            f"/learning/questionnaires/{questionnaire_id}/publish", json={"trainer_id": self.trainer}
        )
        assert response.status_code == 200, response.text
        return response.json()

    def published(self, **overrides) -> dict:
        created = self.create(**overrides)
        return self.publish(created["questionnaire_id"])

    def answers(self, questionnaire: dict, picks: list[int]) -> dict:
        return {q["question_id"]: pick for q, pick in zip(questionnaire["questions"], picks)}

    def submit(self, who: str, questionnaire: dict, picks: list[int], **kwargs):
        return self.learner_client(who).post(
            f"/learning/questionnaires/{questionnaire['questionnaire_id']}/submit",
            json={"player_id": who, "answers": self.answers(questionnaire, picks)},
            **kwargs,
        )


@pytest.fixture
def world(clock) -> World:
    return World()


# ---------------------------------------------------------------------------
# Create + validation
# ---------------------------------------------------------------------------


def test_trainer_creates_a_draft_with_questions(world):
    body = world.create()
    assert body["is_published"] is False
    assert body["attempt_count"] == 0
    assert [q["position"] for q in body["questions"]] == [0, 1]
    assert body["questions"][0]["correct_index"] == 1
    assert body["due_at"].startswith("2026-10-06T12:00:00")


def test_course_audience_is_accepted_for_an_owned_course(world):
    course_id = _make_course(world.db, world.trainer, [world.trainee])
    response = world.trainer_client().post(
        "/learning/questionnaires", json=_payload(world.trainer, "course", course_id)
    )
    assert response.status_code == 200
    assert response.json()["audience_type"] == "course"


@pytest.mark.parametrize(
    "override",
    [
        {"questions": []},
        {"questions": [{"prompt": "x", "options": ["only one"], "correct_index": 0}]},
        {"questions": [{"prompt": "x", "options": list("abcdefg"), "correct_index": 0}]},
        {"questions": [{"prompt": "x", "options": ["a", "b"], "correct_index": 2}]},
        {"questions": [{"prompt": "x", "options": ["a", "  "], "correct_index": 0}]},
        {"questions": [{"prompt": "  ", "options": ["a", "b"], "correct_index": 0}]},
        {"title": "   "},
        {"title": "t" * 201},
        {"description": "d" * 2001},
        {"due_at": "2026-10-06T12:00:00"},  # naive timestamp
        {"opens_at": (DUE + timedelta(hours=1)).isoformat()},  # opens after due
        {"opens_at": DUE.isoformat()},  # opens exactly at due
        {"audience_type": "everyone"},
    ],
)
def test_invalid_payloads_are_rejected_with_422(world, override):
    body = _payload(world.trainer, "cohort", world.cohort)
    body.update(override)
    response = world.trainer_client().post("/learning/questionnaires", json=body)
    assert response.status_code == 422


def test_more_than_fifty_questions_is_rejected(world):
    many = [{"prompt": f"q{i}", "options": ["a", "b"], "correct_index": 0} for i in range(51)]
    response = world.trainer_client().post(
        "/learning/questionnaires", json=_payload(world.trainer, "cohort", world.cohort, questions=many)
    )
    assert response.status_code == 422
    fifty = many[:50]
    ok = world.trainer_client().post(
        "/learning/questionnaires", json=_payload(world.trainer, "cohort", world.cohort, questions=fifty)
    )
    assert ok.status_code == 200


def test_draft_with_a_past_deadline_can_be_created_but_not_published(world, clock):
    past = (T0 - timedelta(hours=1)).isoformat()
    created = world.create(due_at=past)

    response = world.trainer_client().post(
        f"/learning/questionnaires/{created['questionnaire_id']}/publish",
        json={"trainer_id": world.trainer},
    )
    assert response.status_code == 409
    assert "deadline" in response.json()["detail"].lower()
    assert world.db.query(Questionnaire).one().is_published is False


def test_publishing_with_deadline_exactly_now_is_rejected(world, clock):
    created = world.create(due_at=T0.isoformat())
    response = world.trainer_client().post(
        f"/learning/questionnaires/{created['questionnaire_id']}/publish",
        json={"trainer_id": world.trainer},
    )
    assert response.status_code == 409


def test_learner_cannot_create(world):
    response = world.learner_client(world.trainee).post(
        "/learning/questionnaires", json=_payload(world.trainee, "cohort", world.cohort)
    )
    assert response.status_code == 403


def test_trainer_cannot_use_another_trainers_player_id(world):
    response = world.trainer_client(world.trainer).post(
        "/learning/questionnaires", json=_payload(world.other_trainer, "cohort", world.cohort)
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Audience ownership
# ---------------------------------------------------------------------------


def test_cannot_target_another_trainers_cohort(world):
    other_cohort = _make_cohort(world.db, world.other_trainer, [world.outsider])
    response = world.trainer_client().post(
        "/learning/questionnaires", json=_payload(world.trainer, "cohort", other_cohort)
    )
    assert response.status_code == 404
    assert world.db.query(Questionnaire).count() == 0


def test_cannot_target_another_trainers_course(world):
    other_course = _make_course(world.db, world.other_trainer)
    response = world.trainer_client().post(
        "/learning/questionnaires", json=_payload(world.trainer, "course", other_course)
    )
    assert response.status_code == 404


def test_nonexistent_audience_is_a_404_identical_to_not_owned(world):
    missing = world.trainer_client().post(
        "/learning/questionnaires", json=_payload(world.trainer, "cohort", str(uuid.uuid4()))
    )
    other_cohort = _make_cohort(world.db, world.other_trainer)
    foreign = world.trainer_client().post(
        "/learning/questionnaires", json=_payload(world.trainer, "cohort", other_cohort)
    )
    assert missing.status_code == foreign.status_code == 404
    assert missing.json() == foreign.json()


def test_cohort_id_is_not_accepted_as_a_course_audience(world):
    response = world.trainer_client().post(
        "/learning/questionnaires", json=_payload(world.trainer, "course", world.cohort)
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Freeze rules
# ---------------------------------------------------------------------------


def test_draft_can_be_edited_while_unpublished_with_no_attempts(world):
    created = world.create()
    body = _payload(
        world.trainer,
        "cohort",
        world.cohort,
        title="Renamed",
        questions=[{"prompt": "Only", "options": ["a", "b"], "correct_index": 1}],
    )
    response = world.trainer_client().put(f"/learning/questionnaires/{created['questionnaire_id']}", json=body)
    assert response.status_code == 200
    assert response.json()["title"] == "Renamed"
    assert len(response.json()["questions"]) == 1
    assert world.db.query(QuestionnaireQuestion).count() == 1


def test_published_questionnaire_is_frozen(world):
    published = world.published()
    response = world.trainer_client().put(
        f"/learning/questionnaires/{published['questionnaire_id']}",
        json=_payload(world.trainer, "cohort", world.cohort, title="Changed"),
    )
    assert response.status_code == 409
    assert world.db.query(Questionnaire).one().title == "Week 1 check"


def test_unpublished_but_attempted_questionnaire_is_still_frozen(world):
    published = world.published()
    assert world.submit(world.trainee, published, [1, 0]).status_code == 200
    unpublished = world.trainer_client().post(
        f"/learning/questionnaires/{published['questionnaire_id']}/unpublish",
        json={"trainer_id": world.trainer},
    )
    assert unpublished.status_code == 200
    assert unpublished.json()["is_published"] is False
    assert unpublished.json()["attempt_count"] == 1

    response = world.trainer_client().put(
        f"/learning/questionnaires/{published['questionnaire_id']}",
        json=_payload(world.trainer, "cohort", world.cohort, title="Changed"),
    )
    assert response.status_code == 409
    assert "attempts" in response.json()["detail"].lower()


def test_unpublished_draft_without_attempts_can_be_edited_again(world):
    published = world.published()
    world.trainer_client().post(
        f"/learning/questionnaires/{published['questionnaire_id']}/unpublish",
        json={"trainer_id": world.trainer},
    )
    response = world.trainer_client().put(
        f"/learning/questionnaires/{published['questionnaire_id']}",
        json=_payload(world.trainer, "cohort", world.cohort, title="Changed"),
    )
    assert response.status_code == 200


def test_edit_cannot_retarget_to_an_unowned_audience(world):
    created = world.create()
    other_cohort = _make_cohort(world.db, world.other_trainer)
    response = world.trainer_client().put(
        f"/learning/questionnaires/{created['questionnaire_id']}",
        json=_payload(world.trainer, "cohort", other_cohort),
    )
    assert response.status_code == 404


def test_extend_deadline_moves_forward_on_a_published_questionnaire(world):
    published = world.published()
    new_due = DUE + timedelta(days=2)
    response = world.trainer_client().post(
        f"/learning/questionnaires/{published['questionnaire_id']}/extend-deadline",
        json={"trainer_id": world.trainer, "due_at": new_due.isoformat()},
    )
    assert response.status_code == 200
    assert response.json()["due_at"].startswith("2026-10-08T12:00:00")
    assert response.json()["is_published"] is True


@pytest.mark.parametrize("delta", [timedelta(0), timedelta(hours=-1)])
def test_extend_deadline_is_forward_only(world, delta):
    published = world.published()
    response = world.trainer_client().post(
        f"/learning/questionnaires/{published['questionnaire_id']}/extend-deadline",
        json={"trainer_id": world.trainer, "due_at": (DUE + delta).isoformat()},
    )
    assert response.status_code == 422
    assert world.db.query(Questionnaire).one().due_at.replace(tzinfo=timezone.utc) == DUE


def test_extend_deadline_reopens_a_lapsed_questionnaire_only_into_the_future(world, clock):
    published = world.published()
    clock.now = DUE + timedelta(days=1)
    in_the_past = world.trainer_client().post(
        f"/learning/questionnaires/{published['questionnaire_id']}/extend-deadline",
        json={"trainer_id": world.trainer, "due_at": (DUE + timedelta(hours=1)).isoformat()},
    )
    assert in_the_past.status_code == 422
    reopened = world.trainer_client().post(
        f"/learning/questionnaires/{published['questionnaire_id']}/extend-deadline",
        json={"trainer_id": world.trainer, "due_at": (clock.now + timedelta(hours=1)).isoformat()},
    )
    assert reopened.status_code == 200
    assert world.submit(world.trainee, published, [1, 0]).status_code == 200


def test_other_trainer_cannot_mutate_my_questionnaire(world):
    published = world.published()
    qid = published["questionnaire_id"]
    other = world.trainer_client(world.other_trainer)
    body = {"trainer_id": world.other_trainer}
    assert other.post(f"/learning/questionnaires/{qid}/publish", json=body).status_code == 404
    assert other.post(f"/learning/questionnaires/{qid}/unpublish", json=body).status_code == 404
    assert (
        other.post(
            f"/learning/questionnaires/{qid}/extend-deadline",
            json={**body, "due_at": (DUE + timedelta(days=1)).isoformat()},
        ).status_code
        == 404
    )
    assert (
        other.put(
            f"/learning/questionnaires/{qid}",
            json=_payload(world.other_trainer, "cohort", _make_cohort(world.db, world.other_trainer)),
        ).status_code
        == 404
    )


def test_mine_lists_only_my_questionnaires(world):
    world.create()
    other_cohort = _make_cohort(world.db, world.other_trainer)
    world.trainer_client(world.other_trainer).post(
        "/learning/questionnaires", json=_payload(world.other_trainer, "cohort", other_cohort)
    )
    mine = world.trainer_client().get("/learning/questionnaires/mine", params={"trainer_id": world.trainer})
    assert mine.status_code == 200
    assert len(mine.json()) == 1
    spoof = world.trainer_client().get(
        "/learning/questionnaires/mine", params={"trainer_id": world.other_trainer}
    )
    assert spoof.status_code == 403


# ---------------------------------------------------------------------------
# Trainee visibility
# ---------------------------------------------------------------------------


def test_trainee_sees_only_published_audience_matched_questionnaires(world):
    published = world.published(title="Visible")
    world.create(title="Draft")  # unpublished
    other_cohort = _make_cohort(world.db, world.other_trainer, [world.outsider])
    other = world.trainer_client(world.other_trainer)
    foreign = other.post(
        "/learning/questionnaires", json=_payload(world.other_trainer, "cohort", other_cohort)
    ).json()
    other.post(
        f"/learning/questionnaires/{foreign['questionnaire_id']}/publish",
        json={"trainer_id": world.other_trainer},
    )

    mine = world.learner_client(world.trainee).get(
        "/learning/questionnaires/available", params={"player_id": world.trainee}
    )
    assert mine.status_code == 200
    assert [r["title"] for r in mine.json()] == ["Visible"]
    assert mine.json()[0]["questionnaire_id"] == published["questionnaire_id"]
    assert mine.json()[0]["status"] == "not_started"
    assert mine.json()[0]["is_open"] is True
    assert mine.json()[0]["question_count"] == 2

    outsider = world.learner_client(world.outsider).get(
        "/learning/questionnaires/available", params={"player_id": world.outsider}
    )
    assert [r["questionnaire_id"] for r in outsider.json()] == [foreign["questionnaire_id"]]


def test_course_audience_uses_internal_enrollment(world):
    course_id = _make_course(world.db, world.trainer, [world.trainee])
    created = world.trainer_client().post(
        "/learning/questionnaires", json=_payload(world.trainer, "course", course_id)
    ).json()
    world.publish(created["questionnaire_id"])

    enrolled = world.learner_client(world.trainee).get(
        "/learning/questionnaires/available", params={"player_id": world.trainee}
    )
    assert [r["questionnaire_id"] for r in enrolled.json()] == [created["questionnaire_id"]]
    not_enrolled = world.learner_client(world.outsider).get(
        "/learning/questionnaires/available", params={"player_id": world.outsider}
    )
    assert not_enrolled.json() == []


def test_question_payload_never_contains_the_answer_key_before_submit(world):
    published = world.published()
    qid = published["questionnaire_id"]
    client = world.learner_client(world.trainee)

    listing = client.get("/learning/questionnaires/available", params={"player_id": world.trainee})
    detail = client.get(f"/learning/questionnaires/{qid}", params={"player_id": world.trainee})

    assert detail.status_code == 200
    assert "correct" not in listing.text.lower()
    assert "correct" not in detail.text.lower()
    assert len(detail.json()["questions"]) == 2
    assert detail.json()["attempt"] is None


def test_detail_is_404_for_non_audience_or_unpublished(world):
    created = world.create()
    qid = created["questionnaire_id"]
    # Unpublished -> not visible even to an audience member.
    assert (
        world.learner_client(world.trainee)
        .get(f"/learning/questionnaires/{qid}", params={"player_id": world.trainee})
        .status_code
        == 404
    )
    world.publish(qid)
    # Published but not in the audience.
    assert (
        world.learner_client(world.outsider)
        .get(f"/learning/questionnaires/{qid}", params={"player_id": world.outsider})
        .status_code
        == 404
    )
    assert (
        world.learner_client(world.outsider)
        .post(
            f"/learning/questionnaires/{qid}/submit",
            json={"player_id": world.outsider, "answers": {}},
        )
        .status_code
        == 404
    )


def test_trainee_cannot_act_as_another_player(world):
    published = world.published()
    qid = published["questionnaire_id"]
    client = world.learner_client(world.trainee)
    assert (
        client.get(f"/learning/questionnaires/{qid}", params={"player_id": world.trainee2}).status_code == 403
    )
    assert (
        client.get("/learning/questionnaires/available", params={"player_id": world.trainee2}).status_code
        == 403
    )
    assert (
        client.post(
            f"/learning/questionnaires/{qid}/submit",
            json={"player_id": world.trainee2, "answers": world.answers(published, [1, 0])},
        ).status_code
        == 403
    )


def test_trainer_role_alone_cannot_attempt(world):
    published = world.published()
    response = world.trainer_client().get(
        f"/learning/questionnaires/{published['questionnaire_id']}", params={"player_id": world.trainer}
    )
    assert response.status_code == 403


def test_detail_before_opens_at_is_409(world, clock):
    published = world.published(opens_at=(T0 + timedelta(hours=2)).isoformat())
    response = world.learner_client(world.trainee).get(
        f"/learning/questionnaires/{published['questionnaire_id']}", params={"player_id": world.trainee}
    )
    assert response.status_code == 409
    listing = world.learner_client(world.trainee).get(
        "/learning/questionnaires/available", params={"player_id": world.trainee}
    )
    assert listing.json()[0]["is_open"] is False


# ---------------------------------------------------------------------------
# Submission
# ---------------------------------------------------------------------------


def test_on_time_submit_scores_server_side_and_reveals_the_key(world):
    published = world.published()
    response = world.submit(world.trainee, published, [1, 1])  # first right, second wrong
    assert response.status_code == 200
    body = response.json()
    assert (body["score"], body["max_score"]) == (1, 2)
    assert body["is_late"] is False
    assert [q["is_correct"] for q in body["questions"]] == [True, False]
    assert [q["correct_index"] for q in body["questions"]] == [1, 0]
    assert [q["selected_index"] for q in body["questions"]] == [1, 1]
    assert body["submitted_at"].startswith("2026-10-05T12:00:00")

    detail = world.learner_client(world.trainee).get(
        f"/learning/questionnaires/{published['questionnaire_id']}", params={"player_id": world.trainee}
    )
    assert detail.json()["status"] == "submitted"
    assert detail.json()["attempt"]["score"] == 1
    assert detail.json()["questions"] == []


def test_client_supplied_timestamps_are_ignored(world, clock):
    published = world.published()
    clock.now = T0 + timedelta(hours=3)
    response = world.learner_client(world.trainee).post(
        f"/learning/questionnaires/{published['questionnaire_id']}/submit",
        json={
            "player_id": world.trainee,
            "answers": world.answers(published, [1, 0]),
            "submitted_at": "2000-01-01T00:00:00+00:00",
        },
    )
    assert response.status_code == 200
    assert response.json()["submitted_at"].startswith("2026-10-05T15:00:00")


def test_submit_exactly_at_the_deadline_is_accepted(world, clock):
    published = world.published()
    clock.now = DUE
    assert world.submit(world.trainee, published, [1, 0]).status_code == 200


def test_submit_one_microsecond_after_the_deadline_is_rejected_and_writes_nothing(world, clock):
    published = world.published()
    clock.now = DUE + timedelta(microseconds=1)
    response = world.submit(world.trainee, published, [1, 0])
    assert response.status_code == 409
    assert "deadline" in response.json()["detail"].lower()
    assert world.db.query(QuestionnaireAttempt).count() == 0


def test_submit_before_opens_at_is_409(world, clock):
    published = world.published(opens_at=(T0 + timedelta(hours=1)).isoformat())
    response = world.submit(world.trainee, published, [1, 0])
    assert response.status_code == 409
    assert world.db.query(QuestionnaireAttempt).count() == 0
    clock.now = T0 + timedelta(hours=1)  # opens_at is inclusive
    assert world.submit(world.trainee, published, [1, 0]).status_code == 200


def test_double_submit_is_idempotent_and_returns_the_original(world):
    published = world.published()
    first = world.submit(world.trainee, published, [1, 0])
    second = world.submit(world.trainee, published, [0, 1])  # different answers ignored
    assert first.status_code == second.status_code == 200
    assert second.json() == first.json()
    assert second.json()["score"] == 2
    assert world.db.query(QuestionnaireAttempt).count() == 1


def test_repeat_submit_after_the_deadline_still_returns_the_recorded_attempt(world, clock):
    published = world.published()
    first = world.submit(world.trainee, published, [1, 0])
    clock.now = DUE + timedelta(days=1)
    again = world.submit(world.trainee, published, [1, 0])
    assert again.status_code == 200
    assert again.json()["attempt_id"] == first.json()["attempt_id"]


def test_concurrent_duplicate_insert_returns_the_winner_not_a_500(world, monkeypatch):
    """Two submits both pass the "already attempted?" check; the UNIQUE
    constraint rejects the second insert, which must come back as the
    winner's attempt, not an unhandled IntegrityError."""
    published = world.published()
    winner = world.submit(world.trainee, published, [1, 0]).json()

    real_find = questionnaires_module._find_attempt
    calls = {"n": 0}

    def stale_first_lookup(session, questionnaire_id, player_id):
        calls["n"] += 1
        return None if calls["n"] == 1 else real_find(session, questionnaire_id, player_id)

    monkeypatch.setattr(questionnaires_module, "_find_attempt", stale_first_lookup)
    loser = world.submit(world.trainee, published, [0, 1])

    assert loser.status_code == 200
    assert loser.json()["attempt_id"] == winner["attempt_id"]
    assert loser.json()["score"] == winner["score"] == 2
    assert world.db.query(QuestionnaireAttempt).count() == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda answers: {},  # nothing answered
        lambda answers: dict(list(answers.items())[:1]),  # one missing
        lambda answers: {**answers, "unknown-question": 0},  # extra key
        lambda answers: {k: 9 for k in answers},  # out of range
        lambda answers: {k: -1 for k in answers},  # negative
    ],
)
def test_incomplete_or_out_of_range_answers_are_422_and_write_nothing(world, mutate):
    published = world.published()
    answers = mutate(world.answers(published, [1, 0]))
    response = world.learner_client(world.trainee).post(
        f"/learning/questionnaires/{published['questionnaire_id']}/submit",
        json={"player_id": world.trainee, "answers": answers},
    )
    assert response.status_code == 422
    assert world.db.query(QuestionnaireAttempt).count() == 0


def test_non_integer_answer_is_422(world):
    published = world.published()
    answers = {q["question_id"]: "one" for q in published["questions"]}
    response = world.learner_client(world.trainee).post(
        f"/learning/questionnaires/{published['questionnaire_id']}/submit",
        json={"player_id": world.trainee, "answers": answers},
    )
    assert response.status_code == 422


def test_closed_missed_status_and_no_questions_after_the_deadline(world, clock):
    published = world.published()
    clock.now = DUE + timedelta(seconds=1)
    client = world.learner_client(world.trainee)
    listing = client.get("/learning/questionnaires/available", params={"player_id": world.trainee})
    assert listing.json()[0]["status"] == "closed_missed"
    assert listing.json()[0]["is_open"] is False
    detail = client.get(
        f"/learning/questionnaires/{published['questionnaire_id']}", params={"player_id": world.trainee}
    )
    assert detail.status_code == 200
    assert detail.json()["status"] == "closed_missed"
    assert detail.json()["questions"] == []


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------


def _results(world, questionnaire_id: str, who: str | None = None):
    who = who or world.trainer
    return world.trainer_client(who).get(
        f"/learning/questionnaires/{questionnaire_id}/results", params={"trainer_id": who}
    )


def test_results_show_submitted_and_not_submitted_before_the_deadline(world):
    published = world.published()
    world.submit(world.trainee, published, [1, 0])

    response = _results(world, published["questionnaire_id"])
    assert response.status_code == 200
    body = response.json()
    assert body["deadline_passed"] is False
    assert body["aggregates"] == {
        "audience_size": 2,
        "submitted_count": 1,
        "mean_score": 2.0,
        "max_score": 2,
    }
    by_id = {row["player_id"]: row for row in body["rows"]}
    assert by_id[world.trainee]["status"] == "submitted"
    assert by_id[world.trainee]["score"] == 2
    assert by_id[world.trainee2]["status"] == "not_submitted"
    assert by_id[world.trainee2]["score"] is None
    assert world.outsider not in by_id


def test_results_show_missed_deadline_exactly_after_the_boundary(world, clock):
    published = world.published()
    clock.now = DUE
    at_boundary = _results(world, published["questionnaire_id"]).json()
    assert at_boundary["deadline_passed"] is False
    assert {r["status"] for r in at_boundary["rows"]} == {"not_submitted"}

    clock.now = DUE + timedelta(microseconds=1)
    after = _results(world, published["questionnaire_id"]).json()
    assert after["deadline_passed"] is True
    assert {r["status"] for r in after["rows"]} == {"missed_deadline"}
    assert after["aggregates"]["mean_score"] is None
    assert after["aggregates"]["submitted_count"] == 0


def test_results_mean_score_aggregates_submissions(world):
    published = world.published()
    world.submit(world.trainee, published, [1, 0])  # 2
    world.submit(world.trainee2, published, [0, 1])  # 0
    aggregates = _results(world, published["questionnaire_id"]).json()["aggregates"]
    assert aggregates["submitted_count"] == 2
    assert aggregates["mean_score"] == 1.0


def test_results_exclude_submitters_no_longer_in_the_audience(world):
    published = world.published()
    world.submit(world.trainee, published, [1, 0])
    world.db.query(CohortMembership).filter_by(player_id=world.trainee).delete()
    world.db.commit()
    body = _results(world, published["questionnaire_id"]).json()
    assert [r["player_id"] for r in body["rows"]] == [world.trainee2]


def test_other_trainers_results_are_404(world):
    published = world.published()
    response = _results(world, published["questionnaire_id"], who=world.other_trainer)
    assert response.status_code == 404
    missing = _results(world, str(uuid.uuid4()))
    assert missing.status_code == 404
    assert missing.json() == response.json()


def test_learner_cannot_read_results(world):
    published = world.published()
    response = world.learner_client(world.trainee).get(
        f"/learning/questionnaires/{published['questionnaire_id']}/results",
        params={"trainer_id": world.trainee},
    )
    assert response.status_code == 403


def test_questionnaire_attempts_write_no_competency_evidence(world):
    published = world.published()
    world.submit(world.trainee, published, [1, 0])
    assert world.db.query(EvidenceRecord).count() == 0


def test_database_rejects_a_second_attempt_row(world):
    from sqlalchemy.exc import IntegrityError

    published = world.published()
    world.submit(world.trainee, published, [1, 0])
    world.db.add(
        QuestionnaireAttempt(
            questionnaire_id=published["questionnaire_id"],
            player_id=world.trainee,
            answers={},
            score=0,
            max_score=2,
            submitted_at=T0,
        )
    )
    with pytest.raises(IntegrityError):
        world.db.commit()
    world.db.rollback()
