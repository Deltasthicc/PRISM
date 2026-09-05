import React from 'react';

export const InferenceRationaleCard = ({
  dimension,
  onViewLearningPathway,
}) => {
  const { rationale, name } = dimension;

  return (
    <div className="bg-[#ffffff] border border-[#c5c5d3]/30 rounded-xl p-4 md:p-6 shadow-sm mb-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 pb-3 border-b border-[#eaedff] mb-4">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="material-symbols-outlined text-[#00236f] text-[20px]">account_tree</span>
          <h3 className="font-sans text-base text-[#00236f] font-bold">
            Inference Rationale: {name}
          </h3>
          <span className="px-2 py-0.5 rounded bg-[#e2e7ff] text-[#00236f] font-mono text-[11px] font-semibold border border-[#00236f]/15">
            {rationale.model}
          </span>
        </div>
        <span className="font-mono text-xs text-[#757682]">
          Weighted Attribution Model
        </span>
      </div>

      {/* 4 Attribution Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        {/* Survey History */}
        <div className="bg-[#dce1ff]/30 border border-[#b6c4ff] p-3 rounded-lg">
          <span className="font-sans text-lg text-[#00236f] font-bold block">
            +{rationale.surveyHistory.pct}%
          </span>
          <p className="font-sans text-xs text-[#131b2e] font-semibold mt-0.5">
            Survey History
          </p>
          <span className="font-mono text-xs text-[#757682] block mt-1">
            {rationale.surveyHistory.detail}
          </span>
        </div>

        {/* Proctored Quiz */}
        <div className="bg-[#e2e7ff]/60 border border-[#c5c5d3]/40 p-3 rounded-lg">
          <span className="font-sans text-lg text-[#904d00] font-bold block">
            +{rationale.proctoredQuiz.pct}%
          </span>
          <p className="font-sans text-xs text-[#131b2e] font-semibold mt-0.5">
            Proctored Quiz
          </p>
          <span className="font-mono text-xs text-[#757682] block mt-1">
            {rationale.proctoredQuiz.detail}
          </span>
        </div>

        {/* DSA Practice */}
        <div className="bg-[#dce1ff]/40 border border-[#b6c4ff] p-3 rounded-lg">
          <span className="font-sans text-lg text-[#00236f] font-bold block">
            +{rationale.dsaPractice.pct}%
          </span>
          <p className="font-sans text-xs text-[#131b2e] font-semibold mt-0.5">
            DSA Practice
          </p>
          <span className="font-mono text-xs text-[#757682] block mt-1">
            {rationale.dsaPractice.detail}
          </span>
        </div>

        {/* Self-Appraisal */}
        <div className={`p-3 rounded-lg border ${
          rationale.selfAppraisal.warning
            ? 'bg-[#ffdad6]/50 border-[#ba1a1a]/20'
            : 'bg-[#dce1ff]/30 border-[#b6c4ff]'
        }`}>
          <span className={`font-sans text-lg font-bold block ${
            rationale.selfAppraisal.warning ? 'text-[#ba1a1a]' : 'text-[#00236f]'
          }`}>
            {rationale.selfAppraisal.pct > 0 ? `+${rationale.selfAppraisal.pct}%` : `${rationale.selfAppraisal.pct}%`}
          </span>
          <p className="font-sans text-xs text-[#131b2e] font-semibold mt-0.5">
            Self-Appraisal
          </p>
          <span className={`font-mono text-xs block mt-1 ${
            rationale.selfAppraisal.warning ? 'text-[#ba1a1a]/80 font-medium' : 'text-[#757682]'
          }`}>
            {rationale.selfAppraisal.detail}
          </span>
        </div>
      </div>

      {/* Description Snippet */}
      <p className="text-xs text-[#444651] mb-3 bg-[#faf8ff] p-2.5 rounded-lg border border-[#c5c5d3]/20 leading-relaxed font-sans">
        <strong className="text-[#00236f]">Audit Summary:</strong> {rationale.description}
      </p>

      {/* Bottom Evidence & Action Bar */}
      <div className="bg-[#f2f3ff] p-3 rounded-xl border border-[#c5c5d3]/30 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap font-mono text-xs text-[#444651]">
          <span className="font-mono text-[10px] uppercase text-[#757682] font-bold mr-1 tracking-wider">
            Evidence:
          </span>
          {rationale.evidence.map((item, idx) => (
            <span
              key={`ev-${idx}`}
              className="px-2 py-0.5 rounded bg-[#ffffff] border border-[#c5c5d3]/30 text-[#131b2e] font-medium shadow-2xs"
            >
              {item}
            </span>
          ))}
        </div>

        <button
          onClick={() => onViewLearningPathway(dimension.id)}
          className="inline-flex items-center gap-2 bg-[#00236f] text-white px-4 py-2 rounded-lg font-sans text-sm hover:bg-[#1e3a8a] transition-colors shadow-sm shrink-0 font-semibold cursor-pointer"
        >
          <span>View Learning Pathway</span>
          <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
        </button>
      </div>
    </div>
  );
};
