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

export function monsterForTopic(topic) {
  const id = topic === 'boss' ? BOSS_MONSTER : TOPIC_MONSTER[topic];
  return MONSTERS[id] || MONSTERS.arrays;
}
