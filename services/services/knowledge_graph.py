"""
Knowledge Graph (README section 4.4).

Pure sync logic, no API calls. TOPIC_GRAPH is a static dict for the hackathon
MVP -- per the README, easily replaceable with a real graph DB later.
"""

import config

TOPIC_GRAPH = {
    "arrays": [],
    "linked_lists": ["arrays"],
    "stacks_queues": ["arrays"],
    "binary_search": ["arrays"],
    "recursion": ["arrays"],
    "trees": ["linked_lists", "recursion"],
    "binary_search_tree": ["trees", "binary_search"],
    "heaps": ["trees"],
    "graphs": ["trees"],
    "dynamic_programming": ["recursion", "arrays"],
    "sorting_algorithms": ["arrays", "recursion"],
}

UNLOCK_THRESHOLD = 0.65
WEAK_SCORE_THRESHOLD = 0.5

ROOT_TOPIC = "arrays"  # the only topic with no prerequisites


def _prereq_accuracy(topic: str, accuracy_history: dict) -> float:
    """
    Accuracy to use when checking whether `topic` satisfies a prerequisite.

    DESIGN NOTE (not explicitly in the README -- resolved here for
    consistency): a prerequisite that the player has never attempted has NOT
    been proven, so it must NOT silently unlock dependents. This intentionally
    differs from _scoring_accuracy below, which assumes mastery for
    never-attempted topics. Same "missing entry" case, two different
    questions being asked of it:
      - "has this prereq been proven?"      -> default 0.0 (not proven)
      - "how weak is this unlocked topic?"  -> default 1.0 (decision below)
    """
    if topic not in accuracy_history:
        return 0.0
    return accuracy_history[topic]["recent_accuracy"]


def _scoring_accuracy(topic: str, accuracy_history: dict) -> float:
    """
    Accuracy to use when scoring an already-unlocked topic for weakness.

    DECISION (locked with user): a topic with no accuracy_history entry is
    treated as recent_accuracy = 1.0 (assumed mastered until proven
    otherwise), so brand-new-but-unlocked topics are not prioritized over
    topics the player has actually started struggling with.
    """
    if topic not in accuracy_history:
        return 1.0
    return accuracy_history[topic]["recent_accuracy"]


# INTEGRATION POINT: accuracy_history is sent by the main backend in the
# request body. In production this reflects the player's real performance
# across all dungeon rooms they have played. Mock locally with mocks/mock_data.py.
def get_next_topic(player_id: str, accuracy_history: dict) -> dict:
    """
    Route the player toward their weakest unlocked topic.

    Inputs:
        player_id: str -- accepted to match the README's request contract;
            not used by the routing logic itself (TOPIC_GRAPH is global,
            not per-player).
        accuracy_history: dict -- README schema, keyed by topic name.

    Output:
        dict matching the POST /ai/graph/next-topic response contract, plus
        internal fields for the ML dashboard:
        { next_topic, weak_topics, _unlocked_topics, _locked_topics }

    Backend dependency: accuracy_history must come from the main backend's
    DB in production (see INTEGRATION POINT above). Fully testable solo with
    mocked accuracy_history dicts.

    Edge case: empty accuracy_history (brand new player) -- "arrays" has no
    prerequisites, so it is always unlocked and is returned as next_topic;
    every other topic is locked.
    """
    unlocked_topics = []
    locked_topics = []
    for topic, prereqs in TOPIC_GRAPH.items():
        is_unlocked = all(_prereq_accuracy(p, accuracy_history) > UNLOCK_THRESHOLD for p in prereqs)
        (unlocked_topics if is_unlocked else locked_topics).append(topic)

    scores = {topic: 1 - _scoring_accuracy(topic, accuracy_history) for topic in unlocked_topics}

    weak_topics = [topic for topic, score in scores.items() if score > WEAK_SCORE_THRESHOLD]
    next_topic = max(scores, key=scores.get) if scores else ROOT_TOPIC

    return {
        "next_topic": next_topic,
        "weak_topics": weak_topics,
        "_unlocked_topics": unlocked_topics,
        "_locked_topics": locked_topics,
    }
