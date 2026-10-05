"""Trainer-to-subject matching (services/trainer_matching.py, GET
/learning/trainers/match). Pure-policy tests use hand-calculated scores; the
HTTP tests prove the stored facts feeding the policy are the right ones
(published only, distinct completers, ratings gated at 3, own activity
excluded)."""
from __future__ import annotations

import uuid

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
from models.feedback import CourseFeedback
from models.cohort import Cohort, CohortMembership  # noqa: F401
from models.trainer_expertise import TrainerExpertise
from routes.authorization import require_principal
from routes.trainer_expertise import router as trainer_expertise_router
from security.rbac import BoundPrincipal, Permission, ROLE_PERMISSIONS
from services.trainer_matching import (
    MATCH_POLICY_VERSION,
    DeclaredExpertise,
    TrainerFacts,
    rank_trainers,
    score_trainer,
)

COMPETENCY = "arrays"
OTHER_COMPETENCY = "linked_lists"


# ---------------------------------------------------------------- pure policy


def _declared(level=4, basis="degree", years=5):
    return DeclaredExpertise(level=level, basis=basis, basis_detail="", years_teaching=years)


def test_policy_version_constant():
    assert MATCH_POLICY_VERSION == "trainer-match-v1"


def test_declared_only_score_is_hand_calculated_and_capped_below_activity():
    # level 4/5 * 35 = 28; degree 1.0 * 10 = 10; 5y/10 * 10 = 5  -> 43
    result = score_trainer(TrainerFacts("t1", declared=_declared()))
    assert result["evidence_level"] == "DECLARED_ONLY"
    assert result["score"] == 43.0
    by_key = {c["key"]: c for c in result["components"]}
    assert by_key["declared_level"]["points"] == 28.0
    assert by_key["declared_basis"]["points"] == 10.0
    assert by_key["declared_years"]["points"] == 5.0
    assert by_key["published_courses"]["points"] == 0.0
    assert by_key["mean_rating"]["available"] is False
    assert by_key["mean_rating"]["points"] == 0.0
    # the maximum a declaration alone can ever earn
    best = score_trainer(TrainerFacts("t2", declared=_declared(level=5, years=40)))
    assert best["score"] == 55.0


def test_declared_and_activity_score_is_hand_calculated():
    # 43 declared + courses 2/3*15 = 10 + completions 4/20*20 = 4 = 57; no rating
    facts = TrainerFacts("t1", declared=_declared(), published_courses=2, learners_completed=4)
    result = score_trainer(facts)
    assert result["evidence_level"] == "DECLARED_AND_ACTIVITY"
    assert result["score"] == 57.0
    # three ratings 5,4,3 -> mean 4.0 -> (4-1)/4 * 10 = 7.5
    rated = score_trainer(
        TrainerFacts(
            "t1", declared=_declared(), published_courses=2, learners_completed=4,
            rating_count=3, rating_sum=12,
        )
    )
    assert rated["score"] == 64.5
    assert rated["facts"]["mean_rating"] == 4.0
    assert rated["facts"]["mean_rating_reason"] is None


def test_activity_only_trainer_is_scored_and_labelled():
    # 1 course: 1/3*15 = 5; 0 completions
    result = score_trainer(TrainerFacts("t1", published_courses=1))
    assert result["evidence_level"] == "ACTIVITY_ONLY"
    assert result["score"] == 5.0
    assert result["facts"]["declared"] is None


def test_corroborated_declaration_outranks_identical_uncorroborated_one():
    ranked = rank_trainers(
        [
            TrainerFacts("a-declared", declared=_declared()),
            TrainerFacts("b-both", declared=_declared(), published_courses=1),
        ]
    )
    assert [r["trainer_id"] for r in ranked] == ["b-both", "a-declared"]
    assert [r["rank"] for r in ranked] == [1, 2]


def test_no_evidence_trainer_has_null_score_is_listed_last_and_not_hidden():
    ranked = rank_trainers(
        [
            TrainerFacts("a-nothing"),
            TrainerFacts("z-weak", declared=_declared(level=1, basis="other", years=0)),
        ]
    )
    assert [r["trainer_id"] for r in ranked] == ["z-weak", "a-nothing"]
    nothing = ranked[1]
    assert nothing["evidence_level"] == "NO_EVIDENCE"
    assert nothing["score"] is None
    assert nothing["rank"] is None
    assert nothing["components"] == []
    assert "not a low score" in nothing["rationale"][0]
    # even the weakest real evidence outranks no evidence, and is a real number
    assert ranked[0]["score"] is not None and ranked[0]["score"] > 0


def test_rating_withheld_below_three_ratings():
    for count in (0, 1, 2):
        result = score_trainer(
            TrainerFacts("t1", declared=_declared(), published_courses=1,
                         rating_count=count, rating_sum=5 * count)
        )
        assert result["facts"]["mean_rating"] is None
        assert result["facts"]["mean_rating_reason"] == "fewer than 3 ratings"
        rating = {c["key"]: c for c in result["components"]}["mean_rating"]
        assert rating["available"] is False
        assert rating["raw_value"] is None


def test_ties_break_by_trainer_id_regardless_of_input_order():
    facts = [TrainerFacts(tid, declared=_declared()) for tid in ("c", "a", "b")]
    forward = [r["trainer_id"] for r in rank_trainers(facts)]
    backward = [r["trainer_id"] for r in rank_trainers(list(reversed(facts)))]
    assert forward == backward == ["a", "b", "c"]


def test_scoring_is_reproducible():
    facts = TrainerFacts("t1", declared=_declared(), published_courses=3, learners_completed=7,
                         rating_count=4, rating_sum=17)
    assert score_trainer(facts) == score_trainer(facts)


def test_every_scored_result_explains_itself():
    result = score_trainer(TrainerFacts("t1", declared=_declared(), published_courses=1))
    assert result["rationale"]
    assert any("unverified" in line for line in result["rationale"])
    assert sum(c["weight"] for c in result["components"]) == 100.0


# ----------------------------------------------------------------- HTTP / DB


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


def _client(db, principal: BoundPrincipal) -> TestClient:
    app = FastAPI()
    app.include_router(trainer_expertise_router)

    def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[require_principal] = lambda: principal
    return TestClient(app)


def _player(db, prefix="p") -> str:
    player_id = str(uuid.uuid4())
    db.add(Player(player_id=player_id, username=f"{prefix}-{player_id[:8]}"))
    db.commit()
    return player_id


def _admin_client(db) -> TestClient:
    return _client(db, _principal(_player(db, "admin"), frozenset({"organization_admin"})))


def _declare(db, trainer_id, competency=COMPETENCY, level=4, basis="degree", years=5):
    db.add(TrainerExpertise(trainer_id=trainer_id, competency_id=competency, declared_level=level,
                            basis=basis, basis_detail="", years_teaching=years))
    db.commit()


def _course(db, trainer_id, competency=COMPETENCY, published=True) -> str:
    course = Course(trainer_id=trainer_id, title="C", description="", competency_id=competency,
                    is_published=published)
    db.add(course)
    db.commit()
    return course.course_id


def _complete(db, course_id, player_id):
    db.add(CourseEnrollment(player_id=player_id, course_id=f"internal::{course_id}", provider="internal",
                            competency_id=COMPETENCY, title="C", status="completed"))
    db.commit()


def _rate(db, course_id, player_id, rating):
    db.add(CourseFeedback(player_id=player_id, course_id=course_id, rating=rating))
    db.commit()


def _by_id(body):
    return {t["trainer_id"]: t for t in body["trainers"]}


def test_policy_version_and_self_declared_notice_in_response():
    db = _db()
    body = _admin_client(db).get("/learning/trainers/match", params={"competency_id": COMPETENCY}).json()
    assert body["policy_version"] == "trainer-match-v1"
    assert body["competency_id"] == COMPETENCY
    assert "self-declared" in body["notice"] and "not been verified" in body["notice"]
    assert body["trainers"] == []


def test_unknown_competency_is_422_and_missing_param_is_422():
    db = _db()
    client = _admin_client(db)
    assert client.get("/learning/trainers/match", params={"competency_id": "nope"}).status_code == 422
    assert client.get("/learning/trainers/match").status_code == 422


@pytest.mark.parametrize("roles", [{"learner"}, {"trainer"}, {"department_admin"}, {"auditor"}])
def test_only_organization_admin_can_match(roles):
    db = _db()
    client = _client(db, _principal(_player(db), frozenset(roles)))
    assert client.get("/learning/trainers/match", params={"competency_id": COMPETENCY}).status_code == 403


def test_permission_grants_are_exactly_as_documented():
    assert Permission.TRAINER_MATCH_READ in ROLE_PERMISSIONS["organization_admin"]
    assert Permission.TRAINER_MATCH_READ not in ROLE_PERMISSIONS["trainer"]
    assert Permission.TRAINER_MATCH_READ not in ROLE_PERMISSIONS["learner"]
    assert Permission.TRAINER_EXPERTISE_MANAGE in ROLE_PERMISSIONS["trainer"]
    assert Permission.TRAINER_EXPERTISE_MANAGE not in ROLE_PERMISSIONS["learner"]


def test_trainer_with_no_data_for_competency_is_no_evidence_listed_last():
    db = _db()
    scored = _player(db, "scored")
    empty_for_this = _player(db, "other-topic")  # only has expertise in a different competency
    _declare(db, scored)
    _declare(db, empty_for_this, competency=OTHER_COMPETENCY)
    body = _admin_client(db).get("/learning/trainers/match", params={"competency_id": COMPETENCY}).json()
    assert [t["trainer_id"] for t in body["trainers"]] == [scored, empty_for_this]
    last = body["trainers"][-1]
    assert last["evidence_level"] == "NO_EVIDENCE"
    assert last["score"] is None and last["rank"] is None
    assert body["trainers"][0]["rank"] == 1


def test_a_player_with_no_trainer_activity_at_all_is_not_listed():
    db = _db()
    _player(db, "plain-learner")
    body = _admin_client(db).get("/learning/trainers/match", params={"competency_id": COMPETENCY}).json()
    assert body["trainers"] == []


def test_declared_only_vs_declared_and_activity_ordering_and_exact_scores():
    db = _db()
    declared_only = _player(db, "a")
    corroborated = _player(db, "b")
    learners = [_player(db, "l") for _ in range(4)]
    _declare(db, declared_only)
    _declare(db, corroborated)
    c1, c2 = _course(db, corroborated), _course(db, corroborated)
    for learner in learners:
        _complete(db, c1, learner)
    body = _admin_client(db).get("/learning/trainers/match", params={"competency_id": COMPETENCY}).json()
    trainers = _by_id(body)
    assert trainers[declared_only]["score"] == 43.0
    assert trainers[declared_only]["evidence_level"] == "DECLARED_ONLY"
    # 43 + 2/3*15 (10) + 4/20*20 (4) = 57
    assert trainers[corroborated]["score"] == 57.0
    assert trainers[corroborated]["evidence_level"] == "DECLARED_AND_ACTIVITY"
    assert [t["trainer_id"] for t in body["trainers"]] == [corroborated, declared_only]
    assert trainers[corroborated]["facts"]["published_courses"] == 2
    assert trainers[corroborated]["facts"]["learners_completed"] == 4


def test_unpublished_course_is_not_activity():
    db = _db()
    only_draft = _player(db, "draft")
    declared_and_draft = _player(db, "declared")
    _course(db, only_draft, published=False)
    _declare(db, declared_and_draft)
    _course(db, declared_and_draft, published=False)
    trainers = _by_id(
        _admin_client(db).get("/learning/trainers/match", params={"competency_id": COMPETENCY}).json()
    )
    assert trainers[only_draft]["evidence_level"] == "NO_EVIDENCE"
    assert trainers[only_draft]["score"] is None
    assert trainers[declared_and_draft]["evidence_level"] == "DECLARED_ONLY"
    assert trainers[declared_and_draft]["facts"]["published_courses"] == 0


def test_course_on_another_competency_is_not_activity_here():
    db = _db()
    trainer = _player(db)
    _course(db, trainer, competency=OTHER_COMPETENCY)
    trainers = _by_id(
        _admin_client(db).get("/learning/trainers/match", params={"competency_id": COMPETENCY}).json()
    )
    assert trainers[trainer]["evidence_level"] == "NO_EVIDENCE"


def test_activity_only_trainer_without_declaration():
    db = _db()
    trainer = _player(db)
    _course(db, trainer)
    row = _by_id(
        _admin_client(db).get("/learning/trainers/match", params={"competency_id": COMPETENCY}).json()
    )[trainer]
    assert row["evidence_level"] == "ACTIVITY_ONLY"
    assert row["score"] == 5.0


def test_mean_rating_only_reported_with_at_least_three_ratings():
    db = _db()
    trainer = _player(db)
    _declare(db, trainer)
    course = _course(db, trainer)
    raters = [_player(db, "r") for _ in range(3)]
    client = _admin_client(db)

    _rate(db, course, raters[0], 5)
    _rate(db, course, raters[1], 5)
    facts = _by_id(client.get("/learning/trainers/match", params={"competency_id": COMPETENCY}).json())[trainer]["facts"]
    assert facts["rating_count"] == 2
    assert facts["mean_rating"] is None
    assert facts["mean_rating_reason"] == "fewer than 3 ratings"

    _rate(db, course, raters[2], 2)
    row = _by_id(client.get("/learning/trainers/match", params={"competency_id": COMPETENCY}).json())[trainer]
    assert row["facts"]["rating_count"] == 3
    assert row["facts"]["mean_rating"] == 4.0  # (5+5+2)/3
    rating = {c["key"]: c for c in row["components"]}["mean_rating"]
    assert rating["available"] is True
    assert rating["points"] == 7.5


def test_trainers_own_enrolment_and_rating_do_not_count():
    db = _db()
    trainer = _player(db)
    course = _course(db, trainer)
    _complete(db, course, trainer)
    _rate(db, course, trainer, 5)
    facts = _by_id(
        _admin_client(db).get("/learning/trainers/match", params={"competency_id": COMPETENCY}).json()
    )[trainer]["facts"]
    assert facts["learners_completed"] == 0
    assert facts["rating_count"] == 0


def test_learners_completing_several_courses_count_once():
    db = _db()
    trainer = _player(db)
    c1, c2 = _course(db, trainer), _course(db, trainer)
    learner = _player(db, "l")
    _complete(db, c1, learner)
    _complete(db, c2, learner)
    facts = _by_id(
        _admin_client(db).get("/learning/trainers/match", params={"competency_id": COMPETENCY}).json()
    )[trainer]["facts"]
    assert facts["learners_completed"] == 1


def test_only_completed_internal_enrolments_count():
    db = _db()
    trainer = _player(db)
    course = _course(db, trainer)
    enrolled_only, external = _player(db, "e"), _player(db, "x")
    db.add(CourseEnrollment(player_id=enrolled_only, course_id=f"internal::{course}", provider="internal",
                            competency_id=COMPETENCY, title="C", status="enrolled"))
    db.add(CourseEnrollment(player_id=external, course_id=f"igot::{course}", provider="igot",
                            competency_id=COMPETENCY, title="C", status="completed"))
    db.commit()
    facts = _by_id(
        _admin_client(db).get("/learning/trainers/match", params={"competency_id": COMPETENCY}).json()
    )[trainer]["facts"]
    assert facts["learners_completed"] == 0


def test_equal_scores_are_ordered_by_trainer_id():
    db = _db()
    ids = sorted(_player(db, "t") for _ in range(3))
    for trainer in reversed(ids):
        _declare(db, trainer)
    body = _admin_client(db).get("/learning/trainers/match", params={"competency_id": COMPETENCY}).json()
    assert [t["trainer_id"] for t in body["trainers"]] == ids
    assert len({t["score"] for t in body["trainers"]}) == 1


def test_response_shape_for_a_scored_trainer_is_exact():
    db = _db()
    trainer = _player(db, "shape")
    db.add(LearnerProfile(player_id=trainer, full_name="Asha Rao"))
    _declare(db, trainer)
    row = _by_id(
        _admin_client(db).get("/learning/trainers/match", params={"competency_id": COMPETENCY}).json()
    )[trainer]
    assert set(row) == {
        "rank", "trainer_id", "username", "full_name", "evidence_level", "score",
        "components", "facts", "rationale",
    }
    assert row["full_name"] == "Asha Rao"
    assert [c["key"] for c in row["components"]] == [
        "declared_level", "declared_basis", "declared_years",
        "published_courses", "learners_completed", "mean_rating",
    ]
    assert set(row["components"][0]) == {
        "key", "label", "weight", "raw_value", "fraction", "points", "available", "note",
    }
    assert row["facts"]["declared"]["verified"] is False
    assert row["facts"]["declared"]["self_declared"] is True
