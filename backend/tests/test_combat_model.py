"""
Tests for the damage-based combat model (see routes/game.py's
_topic_damage_total, enter_room, submit_answer, and use_powerup) and the
powerup rework that manipulates the judge's continuous NLP score rather than
a discrete verdict tier.

Root bugs this guards against:
1. The villain HP bar used to be an arbitrary flat number tracked
   independently of the real win condition (correct answers >=
   room.enemy_count). These tests assert the bar (hits_required -
   hits_landed, now damage points) always reaches exactly zero in the same
   response that reports room_cleared.
2. Every room previously cleared at a flat "3 correct answers" regardless of
   the actual NLP score or the question's difficulty -- these tests assert
   damage_dealt == round(max_damage * score) (zero only for "incorrect"),
   so a harder question's higher max_damage ceiling and a better NLP score
   both genuinely matter.
3. Powerups (Titan's Smash / Valkyrie's Charge / Shadow Step) used to be
   irrelevant once the combat model moved off flat hit-counting -- these
   tests assert each one still measurably changes damage_dealt.

Builds a standalone FastAPI app around just routes.game's router (not
main:app) so this never touches the real skillquest.db or triggers demo
seeding, and monkeypatches the AI-service calls so no live Gemini/services
call is made.
"""
import sys

sys.path.insert(0, ".")

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from db.database import Base, get_db
from models.player import Player  # noqa: F401
from models.guild import Guild  # noqa: F401
from models.dungeon import Dungeon, Room
from models.session import GameSession  # noqa: F401
from models.question import Question  # noqa: F401
from models.submission import AnswerSubmission  # noqa: F401
from models.accuracy_history import AccuracyHistory  # noqa: F401
import routes.game as game_routes
from services.monsters import monster_name_for


@pytest.fixture
def client(monkeypatch):
    # StaticPool: a plain sqlite:///:memory: engine hands out a fresh, empty
    # in-memory database per connection checkout -- StaticPool pins it to a
    # single shared connection so the app's requests and this fixture's setup
    # actually see the same tables/rows.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(game_routes.router)
    app.dependency_overrides[get_db] = override_get_db

    # Deterministic stand-ins for the AI service calls -- these tests are
    # about the combat/powerup bookkeeping, not the LLM integration. Score
    # and verdict are set independently (unlike the old model, a "correct"
    # verdict no longer implies score == 1.0), matching how the real judge
    # returns a continuous NLP similarity score.
    verdict_box = {"verdict": "incorrect", "score": 0.0, "damage_multiplier": 0.0, "max_damage": 100}
    generate_calls = []
    question_counter = {"n": 0}

    async def fake_generate_question(player_id, topic, difficulty, domain, monster_name=None):
        generate_calls.append({"topic": topic, "difficulty": difficulty, "monster_name": monster_name})
        question_counter["n"] += 1
        return {
            "question_id": f"q-{topic}-{difficulty}-{question_counter['n']}",
            "question": f"Test question about {topic}",
            "expected_answer": "the correct answer",
            "hint": "a hint",
            "max_damage": verdict_box["max_damage"],
        }

    async def fake_judge_answer(question_id, player_answer, expected_answer):
        return {
            "score": verdict_box["score"],
            "damage_multiplier": verdict_box["damage_multiplier"],
            "verdict": verdict_box["verdict"],
            "feedback": "test feedback",
        }

    async def fake_next_difficulty(player_id, topic, accuracy_map):
        return {"difficulty": "easy"}

    monkeypatch.setattr(game_routes, "call_generate_question", fake_generate_question)
    monkeypatch.setattr(game_routes, "call_judge_answer", fake_judge_answer)
    monkeypatch.setattr(game_routes, "call_next_difficulty", fake_next_difficulty)

    test_client = TestClient(app)
    test_client.verdict_box = verdict_box
    test_client.generate_calls = generate_calls
    test_client._SessionLocal = TestingSessionLocal
    return test_client


def _make_dungeon_and_room(client, enemy_count=300):
    db = client._SessionLocal()
    dungeon = Dungeon(name="Test Dungeon", domain="DSA")
    db.add(dungeon)
    db.flush()
    room = Room(
        dungeon_id=dungeon.dungeon_id, topic="arrays", order_index=0,
        is_unlocked=True, enemy_count=enemy_count,
    )
    db.add(room)
    db.commit()
    dungeon_id, room_id = dungeon.dungeon_id, room.room_id
    db.close()
    return dungeon_id, room_id


def _register_and_start(client, username, dungeon_id):
    player_id = client.post("/game/player/create", json={"username": username}).json()["player_id"]
    session_id = client.post(
        "/game/session/start", json={"player_id": player_id, "dungeon_id": dungeon_id}
    ).json()["session_id"]
    return player_id, session_id


def _enter_and_submit(client, session_id, room_id, player_id, answer_text="my answer"):
    entered = client.post("/game/room/enter", json={"session_id": session_id, "room_id": room_id}).json()
    question_id = entered["question"]["question_id"]
    submitted = client.post(
        "/game/answer/submit",
        json={"player_id": player_id, "question_id": question_id, "player_answer": answer_text},
    ).json()
    return entered, submitted


def test_room_enter_reports_hits_required_matching_enemy_count(client):
    dungeon_id, room_id = _make_dungeon_and_room(client, enemy_count=300)
    player_id, session_id = _register_and_start(client, "alpha", dungeon_id)

    entered = client.post("/game/room/enter", json={"session_id": session_id, "room_id": room_id}).json()

    assert entered["hits_required"] == 300
    assert entered["hits_landed"] == 0


def test_room_enter_response_includes_max_damage(client):
    dungeon_id, room_id = _make_dungeon_and_room(client)
    player_id, session_id = _register_and_start(client, "alpha", dungeon_id)
    client.verdict_box["max_damage"] = 137

    entered = client.post("/game/room/enter", json={"session_id": session_id, "room_id": room_id}).json()

    assert entered["question"]["max_damage"] == 137


def test_question_generation_is_told_the_room_topics_monster(client):
    """Regression for the "minotaur in 5 different topics" bug: the AI call
    must always be told which single monster it's voicing for this room, so
    it can't wander into naming a different creature per question."""
    dungeon_id, room_id = _make_dungeon_and_room(client)
    player_id, session_id = _register_and_start(client, "alpha", dungeon_id)

    client.post("/game/room/enter", json={"session_id": session_id, "room_id": room_id})

    assert len(client.generate_calls) == 1
    assert client.generate_calls[0]["monster_name"] == monster_name_for("arrays")


def test_hp_bar_reaches_exactly_zero_when_room_actually_clears(client):
    """The core regression test: hits_landed must reach hits_required in the
    exact same response where room_cleared flips true -- never before, never
    after. A perfect (score 1.0) answer against a 100-damage-ceiling question
    deals exactly 100 damage per hit against a 300 HP boss."""
    dungeon_id, room_id = _make_dungeon_and_room(client, enemy_count=300)
    player_id, session_id = _register_and_start(client, "alpha", dungeon_id)
    client.verdict_box["verdict"] = "correct"
    client.verdict_box["score"] = 1.0
    client.verdict_box["max_damage"] = 100

    for expected_hits in (100, 200, 300):
        _, result = _enter_and_submit(client, session_id, room_id, player_id)
        assert result["damage_dealt"] == 100
        assert result["hits_landed"] == expected_hits
        assert result["hits_required"] == 300
        assert result["room_cleared"] == (expected_hits == 300)


def test_incorrect_answers_never_move_the_hp_bar(client):
    dungeon_id, room_id = _make_dungeon_and_room(client, enemy_count=300)
    player_id, session_id = _register_and_start(client, "alpha", dungeon_id)
    client.verdict_box["verdict"] = "incorrect"
    client.verdict_box["score"] = 0.1

    for _ in range(5):
        _, result = _enter_and_submit(client, session_id, room_id, player_id)
        assert result["damage_dealt"] == 0
        assert result["hits_landed"] == 0
        assert result["room_cleared"] is False


def test_damage_scales_with_score_not_just_verdict(client):
    """The heart of the rework: the same "partial" verdict at different NLP
    scores must deal proportionally different damage against the same
    question's max_damage ceiling -- not a flat per-tier amount."""
    dungeon_id, room_id = _make_dungeon_and_room(client, enemy_count=10_000)
    player_id, session_id = _register_and_start(client, "alpha", dungeon_id)
    client.verdict_box["max_damage"] = 100

    client.verdict_box["verdict"] = "partial"
    client.verdict_box["score"] = 0.5
    _, low = _enter_and_submit(client, session_id, room_id, player_id)
    assert low["damage_dealt"] == 50

    client.verdict_box["verdict"] = "correct"
    client.verdict_box["score"] = 0.91
    _, high = _enter_and_submit(client, session_id, room_id, player_id)
    assert high["damage_dealt"] == 91


def test_harder_question_outdamages_easier_one_at_the_same_score(client):
    """A perfect score on a high-ceiling (harder) question must deal more
    damage than a perfect score on a low-ceiling (easier) one -- the whole
    point of tying max_damage to difficulty."""
    dungeon_id, room_id = _make_dungeon_and_room(client, enemy_count=10_000)
    player_id, session_id = _register_and_start(client, "alpha", dungeon_id)
    client.verdict_box["verdict"] = "correct"
    client.verdict_box["score"] = 1.0

    client.verdict_box["max_damage"] = 50
    _, easy = _enter_and_submit(client, session_id, room_id, player_id)

    client.verdict_box["max_damage"] = 150
    _, hard = _enter_and_submit(client, session_id, room_id, player_id)

    assert hard["damage_dealt"] > easy["damage_dealt"]


def test_force_correct_powerup_deals_full_max_damage_regardless_of_judge(client):
    dungeon_id, room_id = _make_dungeon_and_room(client, enemy_count=10_000)
    player_id, session_id = _register_and_start(client, "alpha", dungeon_id)
    client.verdict_box["max_damage"] = 120

    hero_resp = client.post(f"/game/player/{player_id}/hero", json={"hero_id": "titan_warrior"})
    assert hero_resp.status_code == 200

    powerup_resp = client.post("/game/powerup/use", json={"player_id": player_id})
    assert powerup_resp.status_code == 200
    assert powerup_resp.json()["queued"] is True

    # Judge says a near-zero-score incorrect answer -- the queued
    # force_correct should override both the verdict and the score outright.
    client.verdict_box["verdict"] = "incorrect"
    client.verdict_box["score"] = 0.05
    _, result = _enter_and_submit(client, session_id, room_id, player_id, "definitely wrong")

    assert result["verdict"] == "correct"
    assert result["score"] == 1.0
    assert result["damage_dealt"] == 120


def test_powerup_cooldown_enforced_after_max_uses(client):
    dungeon_id, room_id = _make_dungeon_and_room(client, enemy_count=500)
    player_id, _session_id = _register_and_start(client, "alpha", dungeon_id)
    client.post(f"/game/player/{player_id}/hero", json={"hero_id": "titan_warrior"})

    for _ in range(3):
        resp = client.post("/game/powerup/use", json={"player_id": player_id})
        assert resp.status_code == 200

    fourth = client.post("/game/powerup/use", json={"player_id": player_id})
    assert fourth.status_code == 429


def test_unknown_hero_id_rejected(client):
    dungeon_id, _room_id = _make_dungeon_and_room(client)
    player_id, _session_id = _register_and_start(client, "alpha", dungeon_id)

    resp = client.post(f"/game/player/{player_id}/hero", json={"hero_id": "not_a_real_hero"})
    assert resp.status_code == 422


def test_hits_landed_never_exceeds_hits_required_even_with_stray_submissions(client):
    """Guards the min(boss_max_hp, cumulative_damage) clamp -- a player who
    somehow deals more cumulative damage to a topic than its boss's HP pool
    (e.g. replaying a room) should never show a negative or over-100% bar."""
    dungeon_id, room_id = _make_dungeon_and_room(client, enemy_count=50)
    player_id, session_id = _register_and_start(client, "alpha", dungeon_id)
    client.verdict_box["verdict"] = "correct"
    client.verdict_box["score"] = 1.0
    client.verdict_box["max_damage"] = 100  # deals more than the boss's whole HP pool in one hit

    _, first = _enter_and_submit(client, session_id, room_id, player_id)
    assert first["room_cleared"] is True
    assert first["hits_landed"] == 50
    assert first["damage_dealt"] == 100  # the raw hit itself is uncapped...

    # ...but re-entering an already-cleared room still reports a clamped,
    # sane HP-bar value (never over 100%).
    entered_again = client.post(
        "/game/room/enter", json={"session_id": session_id, "room_id": room_id}
    ).json()
    assert entered_again["hits_landed"] <= entered_again["hits_required"]


# ─── Audit: every one of the 6 hero powerups, end to end ───


def test_force_correct_heal_queues_a_full_damage_hit_and_heals_immediately(client):
    """Freya Ironheart -- the other force_correct-family powerup, plus the
    one immediate (non-queued) effect: heal_to_full."""
    dungeon_id, room_id = _make_dungeon_and_room(client, enemy_count=10_000)
    player_id, session_id = _register_and_start(client, "alpha", dungeon_id)
    client.verdict_box["max_damage"] = 90
    client.post(f"/game/player/{player_id}/hero", json={"hero_id": "valkyrie_warrior"})

    powerup_resp = client.post("/game/powerup/use", json={"player_id": player_id})
    assert powerup_resp.status_code == 200
    body = powerup_resp.json()
    assert body["queued"] is True
    assert body["heal_to_full"] is True

    client.verdict_box["verdict"] = "incorrect"
    client.verdict_box["score"] = 0.0
    _, result = _enter_and_submit(client, session_id, room_id, player_id, "wrong on purpose")
    assert result["verdict"] == "correct"
    assert result["damage_dealt"] == 90


def test_double_xp_next_exactly_doubles_the_next_answers_xp(client):
    """Zephyr the Sage -- compared against an identical control run with no
    powerup, rather than hand-deriving the XP formula's constants."""
    dungeon_id, room_id = _make_dungeon_and_room(client, enemy_count=10_000)
    control_id, control_session = _register_and_start(client, "control", dungeon_id)
    powered_id, powered_session = _register_and_start(client, "powered", dungeon_id)
    client.post(f"/game/player/{powered_id}/hero", json={"hero_id": "sage_mage"})

    client.verdict_box["verdict"] = "correct"
    client.verdict_box["score"] = 1.0

    # Control player never touches the powerup endpoint at all -- a clean,
    # unmodified baseline to compare against.
    powerup_resp = client.post("/game/powerup/use", json={"player_id": powered_id})
    assert powerup_resp.status_code == 200
    assert "queued" not in powerup_resp.json()  # immediate flag-set, not a queued hit

    _, control_result = _enter_and_submit(client, control_session, room_id, control_id)
    _, powered_result = _enter_and_submit(client, powered_session, room_id, powered_id)

    assert powered_result["xp_gained"] == control_result["xp_gained"] * 2


def test_score_boost_next_upgrades_incorrect_to_partial(client):
    """Kael Shadowstep -- a flat +0.3 score boost (not a discrete tier jump)
    can turn a below-partial-threshold score into a partial hit, and that
    hit still deals proportional damage off the boosted score."""
    dungeon_id, room_id = _make_dungeon_and_room(client, enemy_count=10_000)
    player_id, session_id = _register_and_start(client, "alpha", dungeon_id)
    client.verdict_box["max_damage"] = 100
    client.post(f"/game/player/{player_id}/hero", json={"hero_id": "shadow_rogue"})
    client.post("/game/powerup/use", json={"player_id": player_id})

    client.verdict_box["verdict"] = "incorrect"
    client.verdict_box["score"] = 0.1  # + 0.3 boost = 0.4 -> partial (>= 0.30, < 0.65)
    _, result = _enter_and_submit(client, session_id, room_id, player_id, "shaky answer")

    assert result["verdict"] == "partial"
    assert result["score"] == pytest.approx(0.4)
    assert result["damage_dealt"] == 40


def test_score_boost_next_can_upgrade_partial_to_correct(client):
    """The boost is real score math, not a capped one-tier jump -- a partial
    answer close enough to the correct threshold should cross it."""
    dungeon_id, room_id = _make_dungeon_and_room(client, enemy_count=10_000)
    player_id, session_id = _register_and_start(client, "alpha", dungeon_id)
    client.verdict_box["max_damage"] = 100
    client.post(f"/game/player/{player_id}/hero", json={"hero_id": "shadow_rogue"})
    client.post("/game/powerup/use", json={"player_id": player_id})

    client.verdict_box["verdict"] = "partial"
    client.verdict_box["score"] = 0.5  # + 0.3 boost = 0.8 -> correct (>= 0.65)
    _, result = _enter_and_submit(client, session_id, room_id, player_id, "closer answer")

    assert result["verdict"] == "correct"
    assert result["score"] == pytest.approx(0.8)
    assert result["damage_dealt"] == 80


def test_score_boost_next_caps_at_a_perfect_score(client):
    dungeon_id, room_id = _make_dungeon_and_room(client, enemy_count=10_000)
    player_id, session_id = _register_and_start(client, "alpha", dungeon_id)
    client.verdict_box["max_damage"] = 100
    client.post(f"/game/player/{player_id}/hero", json={"hero_id": "shadow_rogue"})
    client.post("/game/powerup/use", json={"player_id": player_id})

    client.verdict_box["verdict"] = "correct"
    client.verdict_box["score"] = 0.9  # + 0.3 would be 1.2, must cap at 1.0
    _, result = _enter_and_submit(client, session_id, room_id, player_id, "great answer")

    assert result["score"] == 1.0
    assert result["damage_dealt"] == 100


def test_free_hint_bonus_xp_reveals_hint_without_spending_a_token(client):
    """Lyra Mindweave -- awards XP and the real hint text, and must not cost
    a hint token the way /game/hint/use does."""
    dungeon_id, room_id = _make_dungeon_and_room(client)
    player_id, session_id = _register_and_start(client, "alpha", dungeon_id)
    client.post(f"/game/player/{player_id}/hero", json={"hero_id": "mindweave_mage"})

    before = client.get(f"/game/player/{player_id}").json()
    entered = client.post("/game/room/enter", json={"session_id": session_id, "room_id": room_id}).json()
    question_id = entered["question"]["question_id"]

    resp = client.post("/game/powerup/use", json={"player_id": player_id, "question_id": question_id})
    assert resp.status_code == 200
    body = resp.json()
    assert body["xp_awarded"] == 20
    assert body["hint_text"] == "a hint"  # matches fake_generate_question's fixed hint

    after = client.get(f"/game/player/{player_id}").json()
    assert after["hint_tokens"] == before["hint_tokens"]
    assert after["total_xp"] == before["total_xp"] + 20


def test_free_hint_bonus_xp_requires_a_question_id(client):
    dungeon_id, _room_id = _make_dungeon_and_room(client)
    player_id, _session_id = _register_and_start(client, "alpha", dungeon_id)
    client.post(f"/game/player/{player_id}/hero", json={"hero_id": "mindweave_mage"})

    resp = client.post("/game/powerup/use", json={"player_id": player_id})
    assert resp.status_code == 422


def test_refill_hints_restores_to_max_from_zero(client):
    """Nyx Quickblade -- restores hint_tokens to the configured max
    regardless of how depleted they were."""
    dungeon_id, _room_id = _make_dungeon_and_room(client)
    player_id, _session_id = _register_and_start(client, "alpha", dungeon_id)
    client.post(f"/game/player/{player_id}/hero", json={"hero_id": "quickblade_rogue"})

    db = client._SessionLocal()
    player = db.query(Player).filter(Player.player_id == player_id).first()
    player.hint_tokens = 0
    db.commit()
    db.close()

    resp = client.post("/game/powerup/use", json={"player_id": player_id})
    assert resp.status_code == 200
    assert resp.json()["hint_tokens"] == game_routes.MAX_HINT_TOKENS

    after = client.get(f"/game/player/{player_id}").json()
    assert after["hint_tokens"] == game_routes.MAX_HINT_TOKENS
