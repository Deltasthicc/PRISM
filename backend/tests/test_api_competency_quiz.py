"""HTTP contract for the bounded, source-attributed demo competency quiz."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base, get_db
from main import app
from models.governance import AuditEvent, EvidenceRecord
from models.player import Player
from routes.competency_quiz import TOPICS
from services.hand_authored_questions import questions_for_competency

client = TestClient(app)
DIFFICULTY_ORDER = {"easy": 0, "medium": 1, "hard": 2}


def issue(topic_id: str, count: int = 5) -> dict:
    response = client.get(
        "/learning/competency-quiz/questions",
        params={"topic_id": topic_id, "count": count},
    )
    assert response.status_code == 200
    return response.json()


def answer_key(topic_id: str) -> dict[str, dict]:
    """Maps item_id -> the raw hand-authored item, so callers can branch on
    question_type rather than assuming every item is an MCQ."""
    return {
        item["item_id"]: item
        for competency_id in TOPICS[topic_id]["competency_ids"]
        for item in questions_for_competency(competency_id)
    }


def submit_payload(issued: dict, *, correct: bool, player_id: str | None = None) -> dict:
    key = answer_key(issued["topic_id"])
    answers = []
    for question in issued["questions"]:
        item = key[question["item_id"]]
        if item.get("question_type", "mcq") == "mcq":
            expected = item["answer_index"]
            answers.append(
                {
                    "item_id": question["item_id"],
                    "selected_index": expected if correct else (expected + 1) % 4,
                }
            )
        else:
            answer_text = item["accepted_answers"][0] if correct else "definitely-not-the-right-answer"
            answers.append({"item_id": question["item_id"], "answer_text": answer_text})
    return {
        "attempt_id": issued["attempt_id"],
        "topic_id": issued["topic_id"],
        "answers": answers,
        **({"player_id": player_id} if player_id else {}),
    }


def test_topics_are_honest_nonempty_bank_slices():
    response = client.get("/learning/competency-quiz/topics")
    assert response.status_code == 200
    topics = response.json()
    assert len(topics) == len(TOPICS)
    assert {topic["topic_id"] for topic in topics} == set(TOPICS)
    for topic in topics:
        assert topic["question_count"] >= 2
        assert all(
            questions_for_competency(competency_id)
            for competency_id in topic["competency_ids"]
        ), f"{topic['topic_id']} advertises a competency with no item"


def test_questions_are_bounded_balanced_ordered_and_do_not_leak_answers():
    data = issue("statistical_foundations", 5)
    assert data["assessment_status"] == "PROVISIONAL"
    assert len(data["questions"]) == 5
    assert {question["competency_id"] for question in data["questions"]} == {
        "os_statistical_foundations",
        "os_sampling_design",
    }
    difficulties = [DIFFICULTY_ORDER[question["difficulty"]] for question in data["questions"]]
    assert difficulties == sorted(difficulties)
    for question in data["questions"]:
        assert set(question) == {
            "item_id", "question", "question_type", "options", "competency_id", "competency_label",
            "difficulty", "doc_id", "locator", "item_status",
        }
        assert question["item_status"] == "DRAFT"
        assert question["question_type"] == "mcq"
        assert len(question["options"]) == 4


@pytest.mark.parametrize("count", [0, -1, 11, 100_000])
def test_question_count_is_strictly_bounded(count):
    response = client.get(
        "/learning/competency-quiz/questions",
        params={"topic_id": "statistical_foundations", "count": count},
    )
    assert response.status_code == 422


def test_unknown_topic_is_rejected():
    response = client.get(
        "/learning/competency-quiz/questions", params={"topic_id": "not-a-real-topic"}
    )
    assert response.status_code == 404


def test_submit_grades_and_ranks_without_calling_it_self_assessment():
    issued = issue("ai_policy", 5)
    response = client.post(
        "/learning/competency-quiz/submit", json=submit_payload(issued, correct=True)
    )
    assert response.status_code == 200
    body = response.json()
    assert body["correct"] == body["total"] == len(issued["questions"])
    assert body["score_percentage"] == 100
    assert body["assessment_status"] == "PROVISIONAL"
    assert "self_ratings" not in body
    assert set(body["diagnostic_scores"]) == {
        score["competency_id"] for score in body["competency_scores"]
    }
    assert [score["rank"] for score in body["competency_scores"]] == list(
        range(1, len(body["competency_scores"]) + 1)
    )
    assert all(score["confidence"] == "low" for score in body["competency_scores"])


def test_submit_requires_exact_issued_set_and_rejects_duplicate_and_cross_topic():
    issued = issue("data_quality", 2)
    payload = submit_payload(issued, correct=False)
    partial = {**payload, "answers": payload["answers"][:1]}
    assert client.post("/learning/competency-quiz/submit", json=partial).status_code == 422
    duplicate = {**payload, "answers": [payload["answers"][0], payload["answers"][0]]}
    assert client.post("/learning/competency-quiz/submit", json=duplicate).status_code == 422
    wrong_topic = {**payload, "topic_id": "price_statistics"}
    assert client.post("/learning/competency-quiz/submit", json=wrong_topic).status_code == 422


def test_attempt_is_single_use():
    issued = issue("data_privacy", 2)
    payload = submit_payload(issued, correct=False)
    assert client.post("/learning/competency-quiz/submit", json=payload).status_code == 200
    assert client.post("/learning/competency-quiz/submit", json=payload).status_code == 409


def test_submission_persists_separate_diagnostic_evidence_and_audit(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'quiz.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)
    db = TestSession()
    player = Player(username=f"quiz-{uuid.uuid4()}")
    db.add(player)
    db.commit()
    db.refresh(player)

    def override_db():
        session = TestSession()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    try:
        issued = issue("price_statistics", 2)
        response = client.post(
            "/learning/competency-quiz/submit",
            json=submit_payload(issued, correct=True, player_id=player.player_id),
        )
        assert response.status_code == 200
        body = response.json()
        assert body["persisted_as_diagnostic_evidence"] is True
        records = db.query(EvidenceRecord).filter_by(player_id=player.player_id).all()
        assert len(records) == len(body["competency_scores"])
        assert {record.evidence_type for record in records} == {"diagnostic"}
        assert all('\"provisional\":true' in record.detail for record in records)
        assert db.query(AuditEvent).filter_by(action="competency_quiz.submit").count() == 1
    finally:
        app.dependency_overrides.pop(get_db, None)
        db.close()
        engine.dispose()
