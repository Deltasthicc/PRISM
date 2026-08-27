"""
Knowledge graph — static topic dependency graph for DSA domain.
"""

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

# Ordered list of all topics (topological order)
ALL_TOPICS = list(TOPIC_GRAPH.keys())


def get_unlocked_topics(accuracy_history: dict) -> list:
    """Return topics whose prerequisites all have recent_accuracy > 0.65."""
    unlocked = []
    for topic, prereqs in TOPIC_GRAPH.items():
        if not prereqs:
            unlocked.append(topic)
        elif all(accuracy_history.get(p, 0) > 0.65 for p in prereqs):
            unlocked.append(topic)
    return unlocked


def get_next_topic(accuracy_history: dict) -> str:
    """Return the weakest unlocked topic."""
    unlocked = get_unlocked_topics(accuracy_history)
    if not unlocked:
        return "arrays"
    # Score each as (1 - accuracy), highest score = weakest
    scored = [(t, 1 - accuracy_history.get(t, 0)) for t in unlocked]
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[0][0]


def get_weak_topics(accuracy_history: dict) -> list:
    """Return all unlocked topics with score > 0.5 (accuracy < 0.5)."""
    unlocked = get_unlocked_topics(accuracy_history)
    return [t for t in unlocked if accuracy_history.get(t, 0) < 0.5]
