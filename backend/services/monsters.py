"""
Canonical topic -> villain name map.

IMPORTANT: these strings must exactly match
frontend/lib/sprites/monsterSprites.js's MONSTERS dict (`name` field for
each entry). This is the backend's copy, used to tell the AI question
generator which specific character it's writing dialogue for -- without it,
Gemini invents a new monster persona per question (a different name every
time, e.g. "the Minotaur" showing up across five unrelated topics) instead
of staying in character as the one villain the player actually sees on
screen for that topic.
"""

MONSTER_NAMES = {
    "arrays": "The Index Wraith",
    "linked_lists": "The Chain Ghast",
    "stacks_queues": "The Twin Warden",
    "binary_search": "The Halving Oracle",
    "recursion": "The Mirror Wyrm",
    "trees": "The Root Warden",
    "binary_search_tree": "The Sorted Sentinel",
    "heaps": "The Apex Behemoth",
    "graphs": "The Webweaver",
    "dynamic_programming": "The Memory Golem",
    "sorting_algorithms": "The Arbiter of Order",
    "boss": "The Big-O Devourer",
}


def monster_name_for(topic: str) -> str:
    return MONSTER_NAMES.get(topic, "the dungeon's guardian")
