'use client';

import { useMemo } from 'react';

// Native asset is ~3 links across a 2172x724 strip -- used to size each
// repeated tile so individual links read at a consistent, realistic size
// regardless of how thick the caller renders the chain.
const CHAIN_ASSET_ASPECT = 2172 / 724;

/**
 * A real rusted-iron chain (ChatGPT-generated, background-removed) tiled
 * along a straight segment between two points, replacing the earlier
 * procedurally-drawn oval-link SVG. Use inside any <svg> you already
 * control the coordinate space for (e.g. the dungeon map's own SVG, or a
 * ReactFlow viewport-driven overlay -- see MLDashboard.jsx's
 * GraphChainOverlay, which exists because ReactFlow 11's own custom-edge
 * rendering path doesn't work under this project's React 19).
 */
export default function ChainLink({ x1, y1, x2, y2, thickness = 20 }) {
  const { tiles, angle } = useMemo(() => {
    const dx = x2 - x1;
    const dy = y2 - y1;
    const dist = Math.sqrt(dx * dx + dy * dy);
    const angle = (Math.atan2(dy, dx) * 180) / Math.PI;

    const tileWidth = thickness * CHAIN_ASSET_ASPECT;
    const count = Math.max(1, Math.round(dist / tileWidth));
    // Slight overlap between tiles hides the seam between repeats.
    const actualWidth = (dist / count) * 1.08;

    const tiles = [];
    for (let i = 0; i < count; i++) {
      const t = (i + 0.5) / count;
      tiles.push({ cx: x1 + dx * t, cy: y1 + dy * t, width: actualWidth });
    }
    return { tiles, angle };
  }, [x1, y1, x2, y2, thickness]);

  return (
    <g className="pointer-events-none" opacity={0.95}>
      {tiles.map((tile, i) => (
        <image
          key={i}
          href="/sprites/chain/segment.png"
          x={-tile.width / 2}
          y={-thickness / 2}
          width={tile.width}
          height={thickness}
          preserveAspectRatio="none"
          transform={`translate(${tile.cx} ${tile.cy}) rotate(${angle})`}
        />
      ))}
    </g>
  );
}
