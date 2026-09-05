import React from 'react';

export const CompetencyVectorCard = ({
  dimension,
  isSelected,
  onSelect,
}) => {
  const { status, officerLevel, requiredLevel } = dimension;
  const progressPct = Math.min(100, Math.round((officerLevel / requiredLevel) * 100));

  // Determine styling based on status
  let iconBg = 'bg-[#dce1ff] text-[#00236f]';
  let barColor = 'bg-[#00236f]';
  let badgeClasses = 'bg-[#00236f] text-[#ffffff] font-semibold';

  if (status === 'critical') {
    iconBg = 'bg-[#ffdad6]/60 text-[#ba1a1a]';
    barColor = 'bg-[#ba1a1a]';
    badgeClasses = 'bg-[#ffdad6] text-[#93000a] font-bold border border-[#ba1a1a]/20';
  } else if (status === 'moderate') {
    iconBg = 'bg-[#ffdcc3] text-[#904d00]';
    barColor = 'bg-[#fe932c]';
    badgeClasses = 'bg-[#ffdcc3] text-[#904d00] font-bold border border-[#ffb77d]';
  } else if (status === 'unassessed') {
    // Deliberately distinct from "matched"/on-target navy -- no evidence
    // recorded yet is not the same claim as "meets the target level".
    iconBg = 'bg-[#eaedff] text-[#757682]';
    barColor = 'bg-[#c5c5d3]';
    badgeClasses = 'bg-[#f2f3ff] text-[#757682] font-semibold border border-[#c5c5d3]/60';
  }

  return (
    <div
      onClick={onSelect}
      className={`bg-[#ffffff] border rounded-xl p-3.5 shadow-sm transition-all cursor-pointer ${
        isSelected
          ? 'border-[#00236f] ring-2 ring-[#00236f]/15 bg-[#faf8ff]'
          : 'border-[#c5c5d3]/30 hover:border-[#757682]/50 hover:bg-[#faf8ff]/60'
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        {/* Left: Icon & Text */}
        <div className="flex items-center gap-3.5 flex-1 min-w-0">
          <div className={`w-9 h-9 rounded-lg flex items-center justify-center shrink-0 font-bold ${iconBg}`}>
            <dimension.icon size={24} />
          </div>
          <div className="truncate">
            <h4 className="font-sans text-sm text-[#131b2e] font-bold truncate">
              {dimension.name}
            </h4>
            <span className="font-mono text-xs text-[#757682] truncate block">
              {dimension.subtitle}
            </span>
          </div>
        </div>

        {/* Right: Level Progress & Status Badge */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="w-24 hidden sm:flex flex-col gap-1">
            <div className="flex justify-between font-mono text-[10px] text-[#757682]">
              <span className="font-bold text-[#00236f]">L{officerLevel}</span>
              <span>Req L{requiredLevel}</span>
            </div>
            <div className="w-full h-1.5 bg-[#eaedff] rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-300 ${barColor}`}
                style={{ width: `${progressPct}%` }}
              ></div>
            </div>
          </div>

          <span className={`px-2.5 py-0.5 rounded font-mono text-xs ${badgeClasses}`}>
            {dimension.gapText}
          </span>
        </div>
      </div>
    </div>
  );
};