import React, { useState } from 'react';

export const RadarChart = ({
  dimensions,
  selectedDimensionId,
  onSelectDimension,
}) => {
  const [hoveredId, setHoveredId] = useState(null);

  // SVG center and radius configuration
  const cx = 170;
  const cy = 170;
  const maxR = 120;
  const maxLevel = 5;

  // Compute 6 vertex positions
  const axisOrder = ['nsso', 'econo', 'pyspark', 'ethics', 'dml', 'dsa'];
  const orderedDimensions = axisOrder
    .map(id => dimensions.find(d => d.id === id))
    .filter(Boolean);

  // Helper to get coordinates for a given level (0-5) at index (0-5)
  const getPoint = (level, index) => {
    const angleRad = (Math.PI / 3) * index - Math.PI / 2; // Start from top (-90 deg)
    const r = (level / maxLevel) * maxR;
    const x = cx + r * Math.cos(angleRad);
    const y = cy + r * Math.sin(angleRad);
    return { x, y };
  };

  // Concentric polygon points for grid rings 1..4
  const gridRings = [1, 2, 3, 4, 5].map(lvl => {
    const pts = [0, 1, 2, 3, 4, 5].map(idx => {
      const p = getPoint(lvl, idx);
      return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
    });
    return pts.join(' ');
  });

  // Target Benchmark Polygon Points
  const targetPoints = orderedDimensions.map((d, idx) => {
    const p = getPoint(d.requiredLevel, idx);
    return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
  }).join(' ');

  // Officer Level Polygon Points
  const officerPoints = orderedDimensions.map((d, idx) => {
    const p = getPoint(d.officerLevel, idx);
    return `${p.x.toFixed(1)},${p.y.toFixed(1)}`;
  }).join(' ');

  // Label coordinates and offsets
  const labelConfigs = [
    { id: 'nsso', text: 'NSSO Sampling', x: 170, y: 36, anchor: 'middle', alignY: 'baseline' },
    { id: 'econo', text: 'Econometrics', x: 282, y: 108, anchor: 'start', alignY: 'middle' },
    { id: 'pyspark', text: 'PySpark / SQL', x: 282, y: 235, anchor: 'start', alignY: 'middle' },
    { id: 'ethics', text: 'Sovereign Cloud', x: 170, y: 306, anchor: 'middle', alignY: 'hanging' },
    { id: 'dml', text: 'Dist. ML', x: 58, y: 235, anchor: 'end', alignY: 'middle' },
    { id: 'dsa', text: 'DSA Core', x: 58, y: 108, anchor: 'end', alignY: 'middle' },
  ];

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
          6 Dimensions
        </span>
      </div>

      {/* Radar Canvas SVG */}
      <div className="relative w-full flex items-center justify-center py-2">
        <svg
          className="w-full max-w-[340px] aspect-square overflow-visible"
          viewBox="0 0 340 340"
        >
          {/* Hexagonal Background Grid Rings */}
          <polygon
            points={gridRings[4]}
            fill="none"
            className="text-[#c5c5d3]/40"
            stroke="currentColor"
            strokeWidth="1"
          />
          <polygon
            points={gridRings[3]}
            fill="none"
            className="text-[#c5c5d3]/30"
            stroke="currentColor"
            strokeWidth="1"
          />
          <polygon
            points={gridRings[2]}
            fill="none"
            className="text-[#c5c5d3]/20"
            stroke="currentColor"
            strokeWidth="1"
          />
          <polygon
            points={gridRings[1]}
            fill="none"
            className="text-[#c5c5d3]/15"
            stroke="currentColor"
            strokeWidth="1"
          />
          <polygon
            points={gridRings[0]}
            fill="none"
            className="text-[#c5c5d3]/10"
            stroke="currentColor"
            strokeWidth="1"
          />

          {/* Radial Spokes / Axes */}
          {[0, 1, 2, 3, 4, 5].map(idx => {
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

          {/* Target Benchmark Area (Orange Dashed) */}
          <polygon
            points={targetPoints}
            fill="#ffdcc3"
            fillOpacity="0.4"
            stroke="#fe932c"
            strokeWidth="2"
            strokeDasharray="4 3"
            className="transition-all duration-300"
          />

          {/* Officer Verified Area (Navy Blue Solid) */}
          <polygon
            points={officerPoints}
            fill="#dce1ff"
            fillOpacity="0.6"
            stroke="#00236f"
            strokeWidth="2.5"
            className="transition-all duration-300"
          />

          {/* Target Vertex Circles */}
          {orderedDimensions.map((d, idx) => {
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

          {/* Officer Vertex Circles */}
          {orderedDimensions.map((d, idx) => {
            const p = getPoint(d.officerLevel, idx);
            const isSelected = selectedDimensionId === d.id;
            const isHovered = hoveredId === d.id;
            return (
              <g
                key={`officer-pt-${d.id}`}
                className="cursor-pointer"
                onClick={() => onSelectDimension(d.id)}
                onMouseEnter={() => setHoveredId(d.id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={isSelected || isHovered ? "6.5" : "4"}
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

          {/* Dimension Text Labels */}
          {labelConfigs.map((cfg) => {
            const d = dimensions.find(dim => dim.id === cfg.id);
            const isSelected = selectedDimensionId === cfg.id;
            const isHovered = hoveredId === cfg.id;
            const isMatched = d?.status === 'matched';
            
            return (
              <text
                key={`label-${cfg.id}`}
                x={cfg.x}
                y={cfg.y}
                textAnchor={cfg.anchor}
                className={`font-mono transition-all duration-200 cursor-pointer select-none ${
                  isSelected || isHovered
                    ? 'fill-[#00236f] font-bold text-[11px] underline'
                    : isMatched
                    ? 'fill-[#00236f] font-bold text-[11px]'
                    : 'fill-[#131b2e] font-semibold text-[10px]'
                }`}
                onClick={() => onSelectDimension(cfg.id)}
                onMouseEnter={() => setHoveredId(cfg.id)}
                onMouseLeave={() => setHoveredId(null)}
              >
                {cfg.text}
              </text>
            );
          })}
        </svg>
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-6 pt-3 border-t border-[#eaedff]">
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-sm bg-[#00236f] inline-block shadow-sm"></span>
          <span className="font-sans text-xs text-[#131b2e] font-medium">
            Verified Level (Officer)
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3 h-3 rounded-sm bg-[#fe932c] inline-block shadow-sm"></span>
          <span className="font-sans text-xs text-[#444651] font-medium">
            Cadre Target Benchmark
          </span>
        </div>
      </div>
    </div>
  );
};