import React from 'react';

const CONFIDENCE_TONE = {
  none: { bg: 'bg-[#fce8e6]', text: 'text-[#b3261e]', border: 'border-[#f5c6c2]' },
  low: { bg: 'bg-[#fff4e5]', text: 'text-[#904d00]', border: 'border-[#ffd9a8]' },
  moderate: { bg: 'bg-[#dce1ff]/30', text: 'text-[#00236f]', border: 'border-[#b6c4ff]' },
};

// Real gap-analysis rationale for one competency (backend/services/learning_engine.py
// analyse_competencies()) -- every value here is a real field from that response, not
// invented ("Survey History"/"Proctored Quiz"/self-appraisal percentages in an earlier
// version of this component were placeholder content with no backend behind them).
export const InferenceRationaleCard = ({ dimension, onViewLearningPathway }) => {
  const { rationale, name } = dimension;
  const confidenceTone = CONFIDENCE_TONE[rationale.confidence] || CONFIDENCE_TONE.none;

  return (
    <div className="bg-[#ffffff] border border-[#c5c5d3]/30 rounded-xl p-4 md:p-6 shadow-sm mb-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2 pb-3 border-b border-[#eaedff] mb-4">
        <div className="flex items-center gap-2 flex-wrap">
          <h3 className="font-sans text-base text-[#00236f] font-bold">Gap analysis: {name}</h3>
          <span
            className={`px-2 py-0.5 rounded font-mono text-[11px] font-semibold border ${confidenceTone.bg} ${confidenceTone.text} ${confidenceTone.border}`}
          >
            {rationale.confidence} confidence
          </span>
        </div>
        <span className="font-mono text-xs text-[#757682]">
          {rationale.observedLabel}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
        <div className="bg-[#dce1ff]/30 border border-[#b6c4ff] p-3 rounded-lg">
          <span className="font-sans text-lg text-[#00236f] font-bold block">
            {rationale.observedLevel.toFixed(1)}/5
          </span>
          <p className="font-sans text-xs text-[#131b2e] font-semibold mt-0.5">Observed level</p>
          <span className="font-mono text-xs text-[#757682] block mt-1">{rationale.observedLabel}</span>
        </div>

        <div className="bg-[#ffdcc3]/40 border border-[#ffb77d] p-3 rounded-lg">
          <span className="font-sans text-lg text-[#904d00] font-bold block">
            {rationale.pathwayTarget.toFixed(1)}/5
          </span>
          <p className="font-sans text-xs text-[#131b2e] font-semibold mt-0.5">Pathway target</p>
          <span className="font-mono text-xs text-[#757682] block mt-1">
            {rationale.matchedRole ? `for ${rationale.matchedRole}` : 'based on your experience level'}
          </span>
        </div>

        <div className="bg-[#e2e7ff]/60 border border-[#c5c5d3]/40 p-3 rounded-lg">
          <span className="font-sans text-lg text-[#00236f] font-bold block">
            {rationale.gap.toFixed(1)}
          </span>
          <p className="font-sans text-xs text-[#131b2e] font-semibold mt-0.5">Gap (levels)</p>
          <span className="font-mono text-xs text-[#757682] block mt-1">{rationale.priority}</span>
        </div>

        <div className={`p-3 rounded-lg border ${confidenceTone.bg} ${confidenceTone.border}`}>
          <span className={`font-sans text-lg font-bold block ${confidenceTone.text}`}>
            {rationale.evidenceSources.length}
          </span>
          <p className="font-sans text-xs text-[#131b2e] font-semibold mt-0.5">Evidence source(s)</p>
          <span className="font-mono text-xs text-[#757682] block mt-1">
            {rationale.evidenceSources.length ? rationale.evidenceSources.join(', ') : 'none recorded yet'}
          </span>
        </div>
      </div>

      <p className="text-xs text-[#444651] mb-3 bg-[#faf8ff] p-2.5 rounded-lg border border-[#c5c5d3]/20 leading-relaxed font-sans">
        <strong className="text-[#00236f]">How this was scored:</strong> {rationale.evidenceNote}
      </p>

      {rationale.recommendedAction && (
        <p className="text-xs text-[#00236f] mb-3 bg-[#f2f3ff] p-2.5 rounded-lg border border-[#c5c5d3]/20 leading-relaxed font-sans font-medium">
          {rationale.recommendedAction}
        </p>
      )}

      <div className="bg-[#f2f3ff] p-3 rounded-xl border border-[#c5c5d3]/30 flex flex-col md:flex-row items-start md:items-center justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap font-mono text-xs text-[#444651]">
          <span className="font-mono text-[10px] uppercase text-[#757682] font-bold mr-1 tracking-wider">
            Evidence:
          </span>
          {rationale.evidenceRecords.length ? (
            rationale.evidenceRecords.map((record, idx) => (
              <span
                key={`ev-${idx}`}
                title={record.detail || undefined}
                className="px-2 py-0.5 rounded bg-[#ffffff] border border-[#c5c5d3]/30 text-[#131b2e] font-medium shadow-2xs"
              >
                {record.evidenceType.replace(/_/g, ' ')}
                {record.value != null ? ` (${record.value.toFixed(1)})` : ''}
              </span>
            ))
          ) : (
            <span className="text-[#757682]">none recorded yet</span>
          )}
        </div>

        <button
          onClick={() => onViewLearningPathway(dimension.id)}
          className="inline-flex items-center gap-2 bg-[#00236f] text-white px-4 py-2 rounded-lg font-sans text-sm hover:bg-[#1e3a8a] transition-colors shadow-sm shrink-0 font-semibold cursor-pointer"
        >
          <span>Open in Academy</span>
        </button>
      </div>
    </div>
  );
};
