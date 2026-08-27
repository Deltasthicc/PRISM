'use client';

import { useMemo } from 'react';

/**
 * Renders a sprite two possible ways:
 *  - `src` given: a real raster PNG (the ChatGPT-generated art under
 *    public/sprites/), drawn with image-rendering:pixelated so it stays
 *    crisp at any display size despite being a raster asset.
 *  - no `src`: the original hand-authored pixel grid (array of equal-length
 *    strings, each character a key into `palette`, '.' for transparent),
 *    rendered as inline SVG rects.
 *
 * Every hero/monster/bat sprite definition (frontend/lib/sprites/) can carry
 * either or both -- `src` takes priority when present.
 */
export default function PixelSprite({ src, grid, palette, size = 64, className, style, title }) {
  // Always called (rules of hooks) -- harmless no-op work when `src` is set
  // and grid/palette are absent, since the memo is simply never read below.
  const { cols, rows, rects } = useMemo(() => {
    if (!grid || !palette) return { cols: 0, rows: 0, rects: [] };
    const rows = grid.length;
    const cols = grid.reduce((max, row) => Math.max(max, row.length), 0);
    const rects = [];
    for (let y = 0; y < rows; y++) {
      const row = grid[y];
      for (let x = 0; x < cols; x++) {
        const key = row[x];
        if (!key || key === '.') continue;
        const color = palette[key];
        if (!color) continue;
        rects.push({ x, y, color, id: `${x}-${y}` });
      }
    }
    return { cols, rows, rects };
  }, [grid, palette]);

  if (src) {
    return (
      // Fixed-size local pixel-art asset; next/image's re-encoding pipeline
      // would fight the crisp/pixelated rendering these sprites need.
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={src}
        alt={title || ''}
        className={className}
        style={{ width: size, height: size, objectFit: 'contain', imageRendering: 'pixelated', ...style }}
      />
    );
  }

  return (
    <svg
      viewBox={`0 0 ${cols} ${rows}`}
      width={size}
      height={size}
      shapeRendering="crispEdges"
      className={className}
      style={style}
      role="img"
      aria-label={title || ''}
    >
      {rects.map((r) => (
        <rect key={r.id} x={r.x} y={r.y} width={1} height={1} fill={r.color} />
      ))}
    </svg>
  );
}
