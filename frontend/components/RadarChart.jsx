import React, { useState } from 'react';

// Generic N-gon radar -- any real curriculum can have a different number of
// tracked competencies (dsa-fundamentals has 11, official-statistics has
// 20+), so this computes its axes from whatever `dimensions` it's given
// instead of assuming a fixed set of 6. Callers should cap `dimensions` to a
// readable count (e.g. the top 6-8 by gap) before passing them in --
// crowding more than ~8 labels around the circle stops being legible.
export const RadarChart = ({
  dimensions,
  selectedDimensionId,
  onSelectDimension,
}) => {
  const [hoveredId, setHoveredId] = useState(null);

  const cx = 170;
  const cy = 170;
  const maxR = 120;
  const maxLevel = 5; // real backend proficiency scale is 0-5 (method.scale)
  const axisCount = dimensions.length;

  const getPoint = (level, index) => {
    const angleRad = ((2 * Math.PI) / axisCount) * index - Math.PI / 2;
    const r = (level / maxLevel) * maxR;
    return { x: cx + r * Math.cos(angleRad), y: cy + r * Math.sin(angleRad) };
  };

  const getLabelPoint = (index) => {
    const angleRad = ((2 * Math.PI) / axisCount) * index - Math.PI / 2;
    const r = maxR + 26;
    return { x: cx + r * Math.cos(angleRad), y: cy + r * Math.sin(angleRad) };
  };

  const labelAnchor = (index) => {
    const angleRad = ((2 * Math.PI) / axisCount) * index - Math.PI / 2;
    const cos = Math.cos(angleRad);
    if (cos > 0.3) return 'start';
    if (cos < -0.3) return 'end';
    return 'middle';
  };

  const gridRings = [1, 2, 3, 4, 5].map((lvl) =>
    Array.from({ length: axisCount }, (_, idx) => {
      const p = getPoint(lvl, idx);
      return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
    }).join(' ')
  );

  const targetPoints = dimensions
    .map((d, idx) => getPoint(d.requiredLevel, idx))
    .map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(' ');

  const observedPoints = dimensions
    .map((d, idx) => getPoint(d.officerLevel, idx))
    .map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`)
    .join(' ');

  return (
    <div className="bg-[#ffffff] rounded-xl p-4 md:p-6 shadow-sm border border-[#c5c5d3]/30">
      <div className="flex items-center justify-between mb-2">
        <div>
          <span className="font-mono text-[10px] text-[#757682] uppercase tracking-wider font-semibold">
            Multi-Dimensional Mapping
          </span>
          <h3 className="font-sans font-semibold text-lg text-[#131b2e]">
            Skill Vector Divergence
          </h3>
        </div>
        <span className="font-mono text-xs px-2 py-0.5 rounded bg-[#f2f3ff] text-[#444651] font-medium border border-[#c5c5d3]/30">
          {axisCount} {axisCount === 1 ? 'Dimension' : 'Dimensions'}
        </span>
      </div>

      <div className="relative w-full flex items-center justify-center py-2">
        <svg className="w-full max-w-[340px] aspect-square overflow-visible" viewBox="0 0 340 340">
          {gridRings.map((ring, idx) => (
            <polygon
              key={`ring-${idx}`}
              points={ring}
              fill="none"
              className={`text-[#c5c5d3]/${[10, 15, 20, 30, 40][idx]}`}
              stroke="currentColor"
              strokeWidth="1"
            />
          ))}

          {Array.from({ length: axisCount }, (_, idx) => {
            const edge = getPoint(5, idx);
            return (
              <line
                key={`spoke-${idx}`}
                x1={cx}
                y1={cy}
                x2={edge.x}
                y2={edge.y}
                stroke="currentColor"
                strokeDasharray="2 2"
                strokeWidth="1"
                className="text-[#c5c5d3]/40"
              />
            );
          })}

          <polygon
            points={targetPoints}
            fill="#ffdcc3"
            fillOpacity="0.4"
            stroke="#fe932c"
            strokeWidth="2"
            strokeDasharray="4 3"
            className="transition-all duration-300"
          />

          <polygon
            points={observedPoints}
            fill="#dce1ff"
            fillOpacity="0.6"
            stroke="#00236f"
            strokeWidth="2.5"
            className="transition-all duration-300"
          />

          {dimensions.map((d, idx) => {
            const p = getPoint(d.requiredLevel, idx);
            return (
              <circle
                key={`target-pt-${d.id}`}
                cx={p.x}
                cy={p.y}
                r="4.5"
                className="fill-[#fe932c] transition-all duration-200 cursor-pointer"
                onClick={() => onSelectDimension(d.id)}
              />
            );
          })}

          {dimensions.map((d, idx) => {
            const p = getPoint(d.officerLevel, idx);
            const isSelected = selectedDimensionId === d.id;
            const isHovered = hoveredId === d.id;
            return (
              <g
                key={`observed-pt-${d.id}`}
                className="cursor-pointer"
                onClick={() => onSelectDimension(d.id)}
                onMouseEnter={() => setHoveredId(d.id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={isSelected || isHovered ? '6.5' : '4'}
                  className="fill-[#00236f] transition-all duration-200"
                />
                {(isSelected || isHovered) && (
                  <circle
                    cx={p.x}
                    cy={p.y}
                    r="9"
                    fill="none"
                    stroke="#00236f"
                    strokeWidth="1.5"
                    strokeDasharray="2 2"
                  />
                )}
              </g>
            );
          })}

          {dimensions.map((d, idx) => {
            const p = getLabelPoint(idx);
            const anchor = labelAnchor(idx);
            const isSelected = selectedDimensionId === d.id;
            const isHovered = hoveredId === d.id;
            return (
              <text
                key={`label-${d.id}`}
                x={p.x}
                y={p.y}
                textAnchor={anchor}
                className={`font-mono transition-all duration-200 cursor-pointer select-none ${
                  isSelected || isHovered
                    ? 'fill-[#00236f] font-bold text-[10px] underline'
                    : 'fill-[#131b2e] font-semibold text-[9px]'
                }`}
                onClick={() => onSelectDimension(d.id)}
                onMouseEnter={() => setHoveredId(d.id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                {d.name.length > 18 ? `${d.name.slice(0, 17)}…` : d.name}
              </text>
            );
          })}
        </svg>
      </div>

      <div className="flex items-center justify-center gap-6 pt-3 border-t border-[#eaedff]">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-sm bg-[#00236f] inline-block shadow-sm"></span>
          <span className="font-sans text-xs text-[#131b2e] font-medium">Observed level</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-sm bg-[#fe932c] inline-block shadow-sm"></span>
          <span className="font-sans text-xs text-[#444651] font-medium">Pathway target</span>
        </div>
      </div>
    </div>
  );
};
