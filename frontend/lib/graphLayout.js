import { TOPIC_GRAPH } from './statMap';

// Depth = longest prerequisite chain leading to this topic. Used to lay the
// graph out in rows (entrance at the top, hardest concepts deepest down) —
// the same layout function powers both the literal dungeon map and the
// ML dashboard's knowledge-graph view, on purpose: they are the same graph.
export function computeDepths() {
  const depth = {};
  function getDepth(topic) {
    if (depth[topic] !== undefined) return depth[topic];
    const prereqs = TOPIC_GRAPH[topic] || [];
    const d = prereqs.length === 0 ? 0 : 1 + Math.max(...prereqs.map(getDepth));
    depth[topic] = d;
    return d;
  }
  Object.keys(TOPIC_GRAPH).forEach(getDepth);
  return depth;
}

export function layoutGraph({ colWidth = 200, rowHeight = 130 } = {}) {
  const depth = computeDepths();
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
