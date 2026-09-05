import React, { useState } from 'react';

export const RecalibrateModal = ({
  isOpen,
  onClose,
  dimensions,
  currentBenchmark,
  onApplyRecalibration,
}) => {
  const [selectedDimId, setSelectedDimId] = useState('dml');
  const [simulatedLevel, setSimulatedLevel] = useState(3);
  const [isProcessing, setIsProcessing] = useState(false);
  const [successMsg, setSuccessMsg] = useState(null);

  if (!isOpen) return null;

  const currentDim = dimensions.find(d => d.id === selectedDimId) || dimensions[0];

  const handleRunInference = () => {
    setIsProcessing(true);
    setSuccessMsg(null);
    setTimeout(() => {
      onApplyRecalibration(selectedDimId, simulatedLevel);
      setIsProcessing(false);
      setSuccessMsg(`Successfully recalculated vector for "${currentDim.name}". Verified level updated to L${simulatedLevel}.`);
      setTimeout(() => {
        setSuccessMsg(null);
        onClose();
      }, 1400);
    }, 900);
  };

  return (
    <div className="fixed inset-0 z-50 bg-[#131b2e]/60 backdrop-blur-xs flex items-center justify-center p-4">
      <div className="bg-[#ffffff] rounded-2xl max-w-lg w-full border border-[#c5c5d3]/40 shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="bg-[#f2f3ff] px-6 py-4 border-b border-[#c5c5d3]/30 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-[#00236f] text-[22px]">tune</span>
            <div>
              <h3 className="font-sans font-bold text-base text-[#00236f]">
                NSO-XAI Engine Recalibration
              </h3>
              <p className="font-mono text-xs text-[#757682]">
                Cadre Cell Attestation &amp; Evidence Resynthesis
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full hover:bg-[#eaedff] flex items-center justify-center text-[#757682] cursor-pointer"
          >
            ✕
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          <div>
            <label className="block font-mono text-xs text-[#757682] uppercase font-bold mb-1.5">
              Select Competency Dimension to Calibrate:
            </label>
            <select
              value={selectedDimId}
              onChange={(e) => {
                setSelectedDimId(e.target.value);
                const d = dimensions.find(dim => dim.id === e.target.value);
                if (d) setSimulatedLevel(Math.min(5, d.officerLevel + 1));
              }}
              className="w-full bg-[#f2f3ff] border border-[#c5c5d3]/50 rounded-lg px-3 py-2 text-sm font-sans font-medium text-[#131b2e] outline-none focus:border-[#00236f]"
            >
              {dimensions.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} (Current: L{d.officerLevel} · Req: L{d.requiredLevel} · {d.gapText})
                </option>
              ))}
            </select>
          </div>

          <div className="bg-[#faf8ff] p-4 rounded-xl border border-[#eaedff] space-y-3">
            <div className="flex justify-between items-center text-xs">
              <span className="font-mono text-[#757682]">Current Verified Level:</span>
              <span className="font-mono font-bold text-[#00236f] bg-[#dce1ff] px-2 py-0.5 rounded">
                Level {currentDim.officerLevel} / 5
              </span>
            </div>
            <div className="flex justify-between items-center text-xs">
              <span className="font-mono text-[#757682]">Target Benchmark Required:</span>
              <span className="font-mono font-bold text-[#904d00] bg-[#ffdcc3] px-2 py-0.5 rounded">
                Level {currentDim.requiredLevel} ({currentBenchmark.band})
              </span>
            </div>

            <div>
              <div className="flex justify-between items-center mb-1 text-xs">
                <span className="font-sans font-medium text-[#131b2e]">Simulate Proctored Assessment Score:</span>
                <span className="font-mono font-bold text-[#00236f]">L{simulatedLevel}</span>
              </div>
              <input
                type="range"
                min="1"
                max="5"
                step="1"
                value={simulatedLevel}
                onChange={(e) => setSimulatedLevel(parseInt(e.target.value))}
                className="w-full accent-[#00236f] cursor-pointer"
              />
              <div className="flex justify-between text-[10px] font-mono text-[#757682]">
                <span>L1 (Novice)</span>
                <span>L2 (Associate)</span>
                <span>L3 (Practitioner)</span>
                <span>L4 (Specialist)</span>
                <span>L5 (Master)</span>
              </div>
            </div>
          </div>

          <div className="bg-[#f2f3ff] p-3 rounded-lg border border-[#c5c5d3]/30 text-xs text-[#444651]">
            <p className="font-mono text-[11px] text-[#00236f] font-semibold mb-1">
              ✓ Automated Verification Sources:
            </p>
            <ul className="list-disc list-inside space-y-0.5 text-[11px]">
              <li>Ingests fresh PLFS 2023-Q4 survey field returns</li>
              <li>Validates NSSTA proctored test logs</li>
              <li>Re-evaluates SBERT attribution vector congruences</li>
            </ul>
          </div>

          {successMsg && (
            <div className="p-3 bg-[#dce1ff] border border-[#00236f]/30 rounded-lg text-xs text-[#00236f] font-sans font-medium flex items-center gap-2 animate-in fade-in">
              <span className="material-symbols-outlined text-[18px]">check_circle</span>
              <span>{successMsg}</span>
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="bg-[#faf8ff] px-6 py-3.5 border-t border-[#c5c5d3]/30 flex items-center justify-end gap-3">
          <button
            onClick={onClose}
            disabled={isProcessing}
            className="px-4 py-1.5 rounded-lg border border-[#c5c5d3]/50 text-xs font-sans font-semibold text-[#444651] hover:bg-[#eaedff] transition-colors cursor-pointer"
          >
            Cancel
          </button>
          <button
            onClick={handleRunInference}
            disabled={isProcessing}
            className="px-4 py-1.5 rounded-lg bg-[#00236f] text-white text-xs font-sans font-semibold hover:bg-[#1e3a8a] transition-colors flex items-center gap-1.5 cursor-pointer shadow-sm disabled:opacity-50"
          >
            {isProcessing ? (
              <>
                <span className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"></span>
                <span>Recalibrating...</span>
              </>
            ) : (
              <>
                <span className="material-symbols-outlined text-[16px]">sync</span>
                <span>Execute Recalibration</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
};