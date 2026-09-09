import { TOPIC_GRAPH } from './statMap';

// Depth = longest prerequisite chain leading to this topic. Used to lay the
// graph out in rows (entrance at the top, hardest concepts deepest down) —
// the same layout function powers the literal dungeon map (any curriculum's
// prerequisite graph, from services/curricula.py via GET /learning/pathway)
// and the ML dashboard's DSA-only knowledge-graph view (which still defaults
// to the legacy TOPIC_GRAPH), on purpose: they are the same layout math.
export function computeDepths(graph = TOPIC_GRAPH) {
  const depth = {};
  function getDepth(topic) {
    if (depth[topic] !== undefined) return depth[topic];
    const prereqs = graph[topic] || [];
    const d = prereqs.length === 0 ? 0 : 1 + Math.max(...prereqs.map(getDepth));
    depth[topic] = d;
    return d;
  }
  Object.keys(graph).forEach(getDepth);
  return depth;
}

export function layoutGraph({ graph = TOPIC_GRAPH, colWidth = 200, rowHeight = 130 } = {}) {
  const depth = computeDepths(graph);
  const byDepth = {};
  Object.entries(depth).forEach(([topic, d]) => {
    byDepth[d] = byDepth[d] || [];
    byDepth[d].push(topic);
  });

  const positions = {};
  Object.entries(byDepth).forEach(([d, topics]) => {
    const n = topics.length;
    topics.forEach((topic, i) => {
      positions[topic] = {
        x: (i - (n - 1) / 2) * colWidth,
        y: Number(d) * rowHeight,
      };
    });
  });
  return positions;
}
