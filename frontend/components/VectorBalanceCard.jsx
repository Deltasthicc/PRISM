import React from 'react';

export const VectorBalanceCard = ({
  dimensions,
  selectedFilter,
  onFilterChange,
}) => {
  const matchedCount = dimensions.filter(d => d.status === 'matched').length;
  const moderateCount = dimensions.filter(d => d.status === 'moderate').length;
  const criticalCount = dimensions.filter(d => d.status === 'critical').length;
  const unassessedCount = dimensions.filter(d => d.status === 'unassessed').length;

  // Calculate total gap levels: sum of (officerLevel - requiredLevel)
  const totalGap = dimensions.reduce((acc, d) => acc + (d.officerLevel - d.requiredLevel), 0);
  const gapText = totalGap === 0 ? 'Fully Aligned' : `${totalGap > 0 ? '+' : ''}${totalGap} Levels`;

  // Congruence percentage: ratio of total officer levels to total required levels
  const totalOfficer = dimensions.reduce((acc, d) => acc + d.officerLevel, 0);
  const totalReq = dimensions.reduce((acc, d) => acc + d.requiredLevel, 0);
  const congruencePct = totalReq > 0 ? ((totalOfficer / totalReq) * 100).toFixed(1) : '100.0';

  return (
    <div className="bg-[#f2f3ff] rounded-xl p-4 md:p-5 border border-[#c5c5d3]/30">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="font-mono text-[10px] text-[#757682] uppercase tracking-wider font-bold">
            Vector Congruence
          </span>
          <span className="px-2 py-0.5 rounded bg-[#1e3a8a] text-[#90a8ff] font-mono text-xs font-bold">
            {congruencePct}%
          </span>
        </div>
        <span className="font-mono text-xs text-[#757682]">
          Gap: {gapText}
        </span>
      </div>

      {/* Congruence Bar */}
      <div className="w-full h-1.5 bg-[#eaedff] rounded-full overflow-hidden mb-4">
        <div
          className="h-full bg-[#00236f] rounded-full transition-all duration-500"
          style={{ width: `${Math.min(100, parseFloat(congruencePct))}%` }}
        ></div>
      </div>

      {/* Status Filter Tiles */}
      <div className="grid grid-cols-4 gap-2 text-center">
        <button
          onClick={() => onFilterChange(selectedFilter === 'matched' ? 'all' : 'matched')}
          className={`py-2 px-2 rounded-lg border transition-all cursor-pointer shadow-sm ${
            selectedFilter === 'matched'
              ? 'bg-[#dce1ff] border-[#00236f] ring-2 ring-[#00236f]/30'
              : 'bg-[#ffffff] border-[#c5c5d3]/30 hover:bg-[#eaedff]'
          }`}
        >
          <span className="font-sans font-bold text-base text-[#00236f] block">
            {matchedCount}
          </span>
          <span className="font-mono text-[10px] text-[#00236f] uppercase font-bold tracking-wider">
            Matched
          </span>
        </button>

        <button
          onClick={() => onFilterChange(selectedFilter === 'moderate' ? 'all' : 'moderate')}
          className={`py-2 px-2 rounded-lg border transition-all cursor-pointer shadow-sm ${
            selectedFilter === 'moderate'
              ? 'bg-[#ffdcc3] border-[#904d00] ring-2 ring-[#904d00]/30'
              : 'bg-[#ffdcc3]/50 border-[#ffb77d] hover:bg-[#ffdcc3]/80'
          }`}
        >
          <span className="font-sans font-bold text-base text-[#904d00] block">
            {moderateCount}
          </span>
          <span className="font-mono text-[10px] text-[#904d00] uppercase font-bold tracking-wider">
            Moderate
          </span>
        </button>

        <button
          onClick={() => onFilterChange(selectedFilter === 'critical' ? 'all' : 'critical')}
          className={`py-2 px-2 rounded-lg border transition-all cursor-pointer shadow-sm ${
            selectedFilter === 'critical'
              ? 'bg-[#ffdad6] border-[#ba1a1a] ring-2 ring-[#ba1a1a]/30'
              : 'bg-[#ffdad6]/60 border-[#ba1a1a]/20 hover:bg-[#ffdad6]/90'
          }`}
        >
          <span className="font-sans font-bold text-base text-[#ba1a1a] block">
            {criticalCount}
          </span>
          <span className="font-mono text-[10px] text-[#ba1a1a] uppercase font-bold tracking-wider">
            Critical
          </span>
        </button>

        <button
          onClick={() => onFilterChange(selectedFilter === 'unassessed' ? 'all' : 'unassessed')}
          className={`py-2 px-2 rounded-lg border transition-all cursor-pointer shadow-sm ${
            selectedFilter === 'unassessed'
              ? 'bg-[#eaedff] border-[#757682] ring-2 ring-[#757682]/30'
              : 'bg-[#f2f3ff] border-[#c5c5d3]/40 hover:bg-[#eaedff]'
          }`}
        >
          <span className="font-sans font-bold text-base text-[#757682] block">
            {unassessedCount}
          </span>
          <span className="font-mono text-[10px] text-[#757682] uppercase font-bold tracking-wider">
            Unassessed
          </span>
        </button>
      </div>
    </div>
  );
};