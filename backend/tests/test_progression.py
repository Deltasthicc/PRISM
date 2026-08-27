from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.database import Base
from models.accuracy_history import AccuracyHistory
from models.dungeon import Dungeon, Room
from models.guild import Guild  # noqa: F401
from models.player import Player
from models.question import Question  # noqa: F401
from models.session import GameSession  # noqa: F401
from models.submission import AnswerSubmission  # noqa: F401
from routes.game import _is_room_unlocked_for_player
from services.game_logic import check_room_clear
from services.knowledge_graph import TOPIC_GRAPH


def build_world():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    dungeon = Dungeon(name="Test Dungeon", domain="DSA")
    alpha = Player(username="alpha")
    beta = Player(username="beta")
    db.add_all([dungeon, alpha, beta])
    db.flush()

    rooms = {}
    for index, topic in enumerate(TOPIC_GRAPH):
        rooms[topic] = Room(
            dungeon_id=dungeon.dungeon_id,
            topic=topic,
            order_index=index,
            is_unlocked=topic == "arrays",
        )
        db.add(rooms[topic])
    rooms["boss"] = Room(
        dungeon_id=dungeon.dungeon_id,
        topic="boss",
        order_index=len(TOPIC_GRAPH),
        is_boss=True,
    )
    db.add(rooms["boss"])
    db.commit()
    return db, dungeon, alpha, beta, rooms


def set_accuracy(db, player, topic, value):
    db.add(
        AccuracyHistory(
            player_id=player.player_id,
            topic=topic,
            recent_accuracy=value,
        )
    )
    db.commit()


def test_unlocks_are_player_specific_and_prerequisite_based():
    db, dungeon, alpha, beta, rooms = build_world()
    try:
        assert _is_room_unlocked_for_player(
            db, alpha.player_id, rooms["arrays"], dungeon.dungeon_id
        )
        assert not _is_room_unlocked_for_player(
            db, alpha.player_id, rooms["linked_lists"], dungeon.dungeon_id
        )

        set_accuracy(db, alpha, "arrays", 0.8)
        assert _is_room_unlocked_for_player(
            db, alpha.player_id, rooms["linked_lists"], dungeon.dungeon_id
        )
        assert not _is_room_unlocked_for_player(
            db, beta.player_id, rooms["linked_lists"], dungeon.dungeon_id
        )
        assert not _is_room_unlocked_for_player(
            db, alpha.player_id, rooms["dynamic_programming"], dungeon.dungeon_id
        )

        set_accuracy(db, alpha, "recursion", 0.7)
        assert _is_room_unlocked_for_player(
            db, alpha.player_id, rooms["dynamic_programming"], dungeon.dungeon_id
        )
    finally:
        db.close()


def test_boss_requires_mastery_of_every_topic_room():
    db, dungeon, alpha, _beta, rooms = build_world()
    try:
        for topic in TOPIC_GRAPH:
            set_accuracy(db, alpha, topic, 0.7)
        assert _is_room_unlocked_for_player(
            db, alpha.player_id, rooms["boss"], dungeon.dungeon_id
        )

        history = db.query(AccuracyHistory).filter_by(
            player_id=alpha.player_id, topic="graphs"
        ).one()
        history.recent_accuracy = 0.65
        db.commit()
        assert not _is_room_unlocked_for_player(
            db, alpha.player_id, rooms["boss"], dungeon.dungeon_id
        )
    finally:
        db.close()


def test_room_clear_requires_the_configured_number_of_answers():
    assert not check_room_clear(2, 3)
    assert check_room_clear(3, 3)


def test_unlock_does_not_regress_after_a_later_accuracy_dip():
    """The core fix for the 'unlocking feels glitchy' report: recent_accuracy
    is a rolling last-5-answers window and can legitimately dip back below
    the threshold later. Once `mastered` has been set, a room a player
    already opened must never re-lock behind them because of it."""
    db, dungeon, alpha, _beta, rooms = build_world()
    try:
        set_accuracy(db, alpha, "arrays", 0.8)
        assert _is_room_unlocked_for_player(
            db, alpha.player_id, rooms["linked_lists"], dungeon.dungeon_id
        )

        history = db.query(AccuracyHistory).filter_by(
            player_id=alpha.player_id, topic="arrays"
        ).one()
        history.mastered = True
        history.recent_accuracy = 0.2  # a bad run drags the rolling window down
        db.commit()

        assert _is_room_unlocked_for_player(
            db, alpha.player_id, rooms["linked_lists"], dungeon.dungeon_id
        )
    finally:
        db.close()


def test_clearing_a_room_unlocks_downstream_topics_even_at_low_accuracy():
    """Reported as 'I finished recursion but the dungeon still shows 60% and
    downstream rooms stayed locked.' recent_accuracy is a last-5-answers
    rolling window, not the room-clear measure -- a player can deal enough
    cumulative damage to drop recursion's boss (enemy_count, now its HP pool)
    to 0 while sitting at only 60% rolling accuracy, well under the 65%
    unlock threshold. A player who beat the room's villain has earned the
    unlock regardless."""
    db, dungeon, alpha, _beta, rooms = build_world()
    try:
        assert rooms["recursion"].enemy_count == 3  # default from the Room model

        db.add(AccuracyHistory(
            player_id=alpha.player_id, topic="recursion",
            damage_dealt=3, attempts=5, recent_accuracy=0.6,
        ))
        db.commit()

        # trees needs both linked_lists and recursion -- linked_lists isn't
        # proven yet, so trees should still be locked on that alone.
        assert not _is_room_unlocked_for_player(
            db, alpha.player_id, rooms["trees"], dungeon.dungeon_id
        )

        set_accuracy(db, alpha, "linked_lists", 0.8)
        # Now that linked_lists is proven too, trees should unlock purely
        # from recursion being cleared -- not from recursion's 60% accuracy.
        assert _is_room_unlocked_for_player(
            db, alpha.player_id, rooms["trees"], dungeon.dungeon_id
        )
    finally:
        db.close()
