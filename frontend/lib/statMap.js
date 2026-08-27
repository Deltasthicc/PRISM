// Maps each DSA topic (room) to an RPG stat name + flavor text for StatSheet.jsx.
// Keep keys identical to the backend's TOPIC_GRAPH keys — they're the join key
// for accuracy_history everywhere in the app.

export const STAT_MAP = {
  arrays: { stat: 'Strength', flavor: 'Raw power over contiguous memory.' },
  linked_lists: { stat: 'Agility', flavor: 'Quick to hop from node to node.' },
  stacks_queues: { stat: 'Dexterity', flavor: 'Precise control of order.' },
  binary_search: { stat: 'Perception', flavor: 'Cuts straight to what matters.' },
  recursion: { stat: 'Wisdom', flavor: 'Understands itself, repeatedly.' },
  trees: { stat: 'Intellect', flavor: 'Branches of structured thought.' },
  binary_search_tree: { stat: 'Insight', flavor: 'Knows which way to look.' },
  heaps: { stat: 'Vitality', flavor: 'Always keeps the priority alive.' },
  graphs: { stat: 'Charisma', flavor: 'Connected to everything, everywhere.' },
  dynamic_programming: { stat: 'Intelligence', flavor: 'Never solves the same problem twice.' },
  sorting_algorithms: { stat: 'Discipline', flavor: 'Brings order to chaos.' },
};

export const TOPIC_LABELS = {
  arrays: 'Arrays',
  linked_lists: 'Linked Lists',
  stacks_queues: 'Stacks & Queues',
  binary_search: 'Binary Search',
  recursion: 'Recursion',
  trees: 'Trees',
  binary_search_tree: 'Binary Search Trees',
  heaps: 'Heaps',
  graphs: 'Graphs',
  dynamic_programming: 'Dynamic Programming',
  sorting_algorithms: 'Sorting Algorithms',
};

// Mirrors the backend's static TOPIC_GRAPH from the README exactly.
// P3 owns the source of truth server-side; this copy only drives
// client-side layout (room positions, locked/unlocked rendering)
// before/without a live /game/dungeon response.
export const TOPIC_GRAPH = {
  arrays: [],
  linked_lists: ['arrays'],
  stacks_queues: ['arrays'],
  binary_search: ['arrays'],
  recursion: ['arrays'],
  trees: ['linked_lists', 'recursion'],
  binary_search_tree: ['trees', 'binary_search'],
  heaps: ['trees'],
  graphs: ['trees'],
  dynamic_programming: ['recursion', 'arrays'],
  sorting_algorithms: ['arrays', 'recursion'],
};
