// Villain art -- one fully unique monster per topic (ChatGPT-generated,
// background-removed, quantized) plus a dedicated final boss. Each entry is
// a { name, image } consumed by <PixelSprite src={...}>.
//
// TO ADD OR SWAP A MONSTER: drop a new PNG in public/sprites/monsters/ and
// point `image` at it (or add a new MONSTERS key + TOPIC_MONSTER mapping).
// No other file needs to change -- everything that renders a villain
// (dungeon map tiles, combat/boss screens, the AI dashboard graph) reads
// through TOPIC_MONSTER / BOSS_MONSTER / monsterForTopic().

export const MONSTERS = {
  arrays: { name: 'The Index Wraith', image: '/sprites/monsters/arrays.png' },
  linked_lists: { name: 'The Chain Ghast', image: '/sprites/monsters/linked_lists.png' },
  stacks_queues: { name: 'The Twin Warden', image: '/sprites/monsters/stacks_queues.png' },
  binary_search: { name: 'The Halving Oracle', image: '/sprites/monsters/binary_search.png' },
  recursion: { name: 'The Mirror Wyrm', image: '/sprites/monsters/recursion.png' },
  trees: { name: 'The Root Warden', image: '/sprites/monsters/trees.png' },
  binary_search_tree: { name: 'The Sorted Sentinel', image: '/sprites/monsters/binary_search_tree.png' },
  heaps: { name: 'The Apex Behemoth', image: '/sprites/monsters/heaps.png' },
  graphs: { name: 'The Webweaver', image: '/sprites/monsters/graphs.png' },
  dynamic_programming: { name: 'The Memory Golem', image: '/sprites/monsters/dynamic_programming.png' },
  sorting_algorithms: { name: 'The Arbiter of Order', image: '/sprites/monsters/sorting_algorithms.png' },
  dragon: { name: 'The Big-O Devourer', image: '/sprites/monsters/dragon.png' },
};

// One fixed, UNIQUE villain per topic -- the fight is the whole room (every
// question in it), not a new monster per question, and no two topics share
// a design.
export const TOPIC_MONSTER = {
  arrays: 'arrays',
  linked_lists: 'linked_lists',
  stacks_queues: 'stacks_queues',
  binary_search: 'binary_search',
  recursion: 'recursion',
  trees: 'trees',
  binary_search_tree: 'binary_search_tree',
  heaps: 'heaps',
  graphs: 'graphs',
  dynamic_programming: 'dynamic_programming',
  sorting_algorithms: 'sorting_algorithms',
};

export const BOSS_MONSTER = 'dragon';

const NON_DSA_MONSTER_POOL = Object.keys(TOPIC_MONSTER);

// Non-DSA curricula (official-statistics, public-policy, digital-literacy)
// have no hand-drawn villain of their own -- rather than always reusing the
// same "Index Wraith" for every one of their rooms, pick a deterministic
// (same topic -> same monster, every load) reuse from the 11 existing DSA
// designs, purely for visual variety. This is flavor only; it carries no
// competency-data meaning, unlike everything else on the dungeon map.
function fallbackMonsterId(topic) {
  let hash = 0;
  for (let i = 0; i < topic.length; i += 1) hash = (hash * 31 + topic.charCodeAt(i)) >>> 0;
  return NON_DSA_MONSTER_POOL[hash % NON_DSA_MONSTER_POOL.length];
}

export function monsterForTopic(topic) {
  if (topic === 'boss' || topic.startsWith('boss::')) return MONSTERS[BOSS_MONSTER];
  const id = TOPIC_MONSTER[topic] || fallbackMonsterId(topic);
  return MONSTERS[id] || MONSTERS.arrays;
}
