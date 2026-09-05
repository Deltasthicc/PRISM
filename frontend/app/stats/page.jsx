'use client';

import React, { useState } from 'react';

import { RadarChart } from '../../components/RadarChart';
import { VectorBalanceCard } from '../../components/VectorBalanceCard';
import { CompetencyVectorCard } from '../../components/CompetencyVectorCard';
import { InferenceRationaleCard } from '../../components/InferenceRationaleCard';
import { RecalibrateModal } from '../../components/RecalibrateModal';
import { BarChart3, TrendingUp, Server, Gavel, Brain, Code } from 'lucide-react';

const CompetencyGapView = ({
  officer,
  dimensions,
  benchmarks,
  selectedBenchmarkId,
  onBenchmarkChange,
  onViewLearningPathway,
  onRecalibrateLevel,
  searchFilter,
}) => {
  const [selectedDimId, setSelectedDimId] = useState('dml');
  const [statusFilter, setStatusFilter] = useState('all');
  const [isRecalibrateOpen, setIsRecalibrateOpen] = useState(false);

  const currentBenchmark =
    benchmarks.find((b) => b.id === selectedBenchmarkId) || benchmarks[0];

  const selectedDimension =
    dimensions.find((d) => d.id === selectedDimId) || dimensions[0];

  // Filter dimensions according to status filter and search query
  const filteredDimensions = dimensions.filter((d) => {
    const matchesStatus =
      statusFilter === 'all' || d.status === statusFilter;

    const matchesSearch =
      !searchFilter ||
      d.name.toLowerCase().includes(searchFilter.toLowerCase()) ||
      d.subtitle.toLowerCase().includes(searchFilter.toLowerCase()) ||
      d.category.toLowerCase().includes(searchFilter.toLowerCase());

    return matchesStatus && matchesSearch;
  });

  return (
    <div className="flex flex-col w-full">

      {/* Top Sovereign Status Strip */}
      {/*<div className="flex items-center justify-between py-1.5 px-3 md:px-4 bg-[#f2f3ff] rounded-lg mb-4 border border-[#c5c5d3]/30 text-xs">
        <div className="flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full bg-[#904d00]"></span>

          <span className="font-mono text-xs text-[#444651] font-medium">
            INFERENCE ENGINE: NSO-XAI-v4.2
          </span>

          <span className="text-[#c5c5d3] text-xs">•</span>

          <span className="font-mono text-[10px] uppercase text-[#757682] font-semibold">
            Calibration: NSSO-PLFS 2023-24
          </span>
        </div>

        <div className="flex items-center gap-1.5 text-xs text-[#444651]">
          <span className="material-symbols-outlined text-[#757682] text-[16px]">
            verified
          </span>

          <span className="font-mono text-xs">
            Attested by Cadre Cell (CSO-HQ)
          </span>
        </div>
      </div> */}

      {/* Officer Profile & Benchmark Target Selector Header */}
      <div className="bg-[#ffffff] border border-[#c5c5d3]/30 rounded-xl p-3.5 md:p-4 mb-5 shadow-sm">
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">

          <div className="flex items-center gap-3.5">
            <div className="w-11 h-11 rounded-xl bg-[#00236f] text-white flex items-center justify-center font-bold text-base shrink-0 shadow-sm">
              RS
            </div>

            <div className="flex flex-col">
              <div className="flex items-center gap-2 flex-wrap">

                <h2 className="font-sans text-base text-[#00236f] font-bold">
                  {officer.username}
                </h2>

                <span className="px-2 py-0.5 rounded bg-[#dce1ff] text-[#00164e] font-mono text-xs font-semibold border border-[#b6c4ff]">
                  {officer.cadre}
                </span>

                <span className="font-mono text-xs text-[#757682]">
                  {officer.officerCode}
                </span>

              </div>

              <span className="font-sans text-xs text-[#444651] mt-0.5">
                {officer.designation} · {officer.division}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-3 flex-wrap">

            <div className="flex items-center gap-2 bg-[#f2f3ff] px-3 py-1.5 rounded-lg border border-[#c5c5d3]/30">
              <span className="font-mono text-xs text-[#757682]">
                Target:
              </span>

              <select
                value={selectedBenchmarkId}
                onChange={(e) => onBenchmarkChange(e.target.value)}
                className="bg-transparent text-[#00236f] font-mono text-xs font-semibold outline-none cursor-pointer pr-1"
              >
                {benchmarks.map((b) => (
                  <option
                    key={b.id}
                    value={b.id}
                    className="text-[#131b2e]"
                  >
                    {b.title}
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={() => setIsRecalibrateOpen(true)}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-[#ffdcc3] text-[#904d00] font-mono text-xs font-bold border border-[#ffb77d] hover:bg-[#fe932c] hover:text-white transition-colors shadow-sm cursor-pointer"
            >
              <span className="material-symbols-outlined text-[16px]">
                tune
              </span>

              <span>Recalibrate</span>
            </button>

          </div>
        </div>
      </div>

      {/* Primary Content Grid: Radar Vector Projection + Domain Gap Vectors */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 mb-5 items-start">

        {/* Left Column: Vector Projection Radar & Benchmark Breakdown */}
        <div className="lg:col-span-5 flex flex-col gap-4">

          <RadarChart
            dimensions={dimensions}
            selectedDimensionId={selectedDimId}
            onSelectDimension={setSelectedDimId}
          />

          <VectorBalanceCard
            dimensions={dimensions}
            selectedFilter={statusFilter}
            onFilterChange={setStatusFilter}
          />

        </div>

        {/* Right Column: Streamlined Domain Gap Vector Cards */}
        <div className="lg:col-span-7 flex flex-col gap-3">

          <div className="flex items-center justify-between px-1">

            <div>
              <span className="font-mono text-[10px] text-[#757682] uppercase font-bold tracking-wider">
                Target Competency Vectors
              </span>

              <h2 className="font-sans text-base text-[#131b2e] font-bold">
                {dimensions.length} Evaluated Dimensions
              </h2>
            </div>

            <div className="flex items-center gap-2">

              <span className="font-mono text-xs text-[#757682]">
                Target: {currentBenchmark.band}
              </span>

              {statusFilter !== 'all' && (
                <button
                  onClick={() => setStatusFilter('all')}
                  className="text-xs font-mono text-[#00236f] hover:underline cursor-pointer"
                >
                  Clear filter
                </button>
              )}

            </div>
          </div>

          <div className="flex flex-col gap-2.5">

            {filteredDimensions.map((dim) => (
              <CompetencyVectorCard
                key={dim.id}
                dimension={dim}
                isSelected={selectedDimId === dim.id}
                onSelect={() => setSelectedDimId(dim.id)}
              />
            ))}

            {filteredDimensions.length === 0 && (
              <div className="p-8 text-center bg-white rounded-xl border border-[#c5c5d3]/30 text-[#757682] font-sans text-sm">
                No competencies found matching &qout;
                {searchFilter || statusFilter}
                &quot;.
              </div>
            )}

          </div>
        </div>
      </div>

      {/* Bottom Section: Algorithmic Evidence & Model Rationale Card */}
      <InferenceRationaleCard
        dimension={selectedDimension}
        onViewLearningPathway={onViewLearningPathway}
      />

      {/* Recalibrate Modal */}
      <RecalibrateModal
        isOpen={isRecalibrateOpen}
        onClose={() => setIsRecalibrateOpen(false)}
        dimensions={dimensions}
        currentBenchmark={currentBenchmark}
        onApplyRecalibration={onRecalibrateLevel}
      />

    </div>
  );
}