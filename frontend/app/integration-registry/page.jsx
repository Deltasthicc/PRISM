'use client';
import React, { useState } from 'react';
import Link from 'next/link';
import { GraduationCap, Download, Landmark, Gamepad2, ArrowRight, BookOpen, Table2, ShieldCheck } from 'lucide-react';
// Design-intent registry: what each integration is meant to become and how
// it behaves today. None of the figures here (record counts, latency,
// hashes) are measured from a live system -- this prototype has no real
// iGOT/NSSTA network integration yet (see SIH26101_MASTER_CHECKLIST.md and
// EVIDENCE.md's "Known Limitations"). Earlier copy on this page stated
// specific compliance/audit claims ("VERIFIED COMPLIANT", a fabricated audit
// hash, a specific RTI Act citation) that were never actually checked
// against anything -- removed rather than repeated here.
export default function IntegrationRegistry() {
  const [toastMessage, setToastMessage] = useState('');

  const showToast = (message) => {
    setToastMessage(message);
    setTimeout(() => setToastMessage(''), 3500);
  };

  const handleExportTopology = () => {
    const topology = {
      registry_rev: '0.1-prototype',
      note: 'Design-intent snapshot, not a live introspection of a running system.',
      connectors: [
        { name: 'iGOT Karmayogi', mode: 'Catalog-fallback (static course list)', status: 'not live-integrated' },
        { name: 'NSSTA / TPAC', mode: 'Static curated catalog', status: 'not live-integrated' },
        { name: 'Adaptive DSA practice (Pyodide)', mode: 'Client-side WASM', status: 'client-side mockup' },
        { name: 'Document ingestion / retrieval', mode: 'Extractive + optional Gemini grounding', status: 'implemented, see backend/services/competency_docs.py' },
      ],
    };
    const blob = new Blob([JSON.stringify(topology, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'prism-integration-registry-topology.json';
    a.click();
    URL.revokeObjectURL(url);
    showToast('Design-intent topology exported.');
  };

  return (
    <div className="flex flex-col w-full">
      {toastMessage && (
        <div className="mb-4 rounded-lg border border-[#c5c5d3]/40 bg-[#f2f3ff] px-4 py-2.5 text-xs text-[#00236f] font-medium">
          {toastMessage}
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {/* Module 1: iGOT Karmayogi */}
        <div className="bg-white rounded-xl p-5 shadow-sm border border-[#c5c5d3]/30 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-[#eaedff] mb-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-[#dce1ff] text-[#00164e] flex items-center justify-center font-bold">
                  <GraduationCap className="w-[18px] h-[18px]" />
                </div>
                <h3 className="text-base font-bold text-[#00236f]">iGOT Karmayogi Catalog</h3>
              </div>
              <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#f2f3ff] text-[#00236f] font-bold">
                CATALOG-FALLBACK
              </span>
            </div>
            <p className="text-xs text-[#444651] mb-4 leading-relaxed">
              A static, curated course catalog used as a stand-in for a real iGOT Karmayogi API
              integration, which this prototype does not yet have live access to.
            </p>
          </div>
          <div className="flex items-center justify-between pt-2 border-t border-[#eaedff]">
            <span className="font-mono text-[11px] text-[#757682]">No live network call from this app</span>
            <Link
              href="/academy"
              className="bg-[#f2f3ff] hover:bg-[#e2e7ff] text-[#00236f] px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors"
            >
              View in Academy
            </Link>
          </div>
        </div>

        {/* Module 2: NSSTA / TPAC */}
        <div className="bg-white rounded-xl p-5 shadow-sm border border-[#c5c5d3]/30 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-[#eaedff] mb-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-[#ffdcc3] text-[#2f1500] flex items-center justify-center font-bold">
                  <Landmark className="w-[18px] h-[18px]" />
                </div>
                <h3 className="text-base font-bold text-[#00236f]">NSSTA / TPAC Training Modules</h3>
              </div>
              <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#ffdcc3] text-[#904d00] font-bold">
                STATIC CATALOG
              </span>
            </div>
            <p className="text-xs text-[#444651] mb-4 leading-relaxed">
              National Statistical Systems Training Academy programs, represented here as a static
              catalog pending a real registry integration.
            </p>
          </div>
          <div className="flex items-center justify-between pt-2 border-t border-[#eaedff]">
            <span className="font-mono text-[11px] text-[#757682]">Not live-synced</span>
          </div>
        </div>

        {/* Module 3: DSA sandbox */}
        <div className="bg-white rounded-xl p-5 shadow-sm border border-[#c5c5d3]/30 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-[#eaedff] mb-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-[#89f5e7] text-[#00312c] flex items-center justify-center font-bold">
                  <Gamepad2 className="w-[18px] h-[18px]" />
                </div>
                <h3 className="text-base font-bold text-[#00236f]">DSA Sandbox</h3>
              </div>
              <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#c7f5c9] text-[#0d3b12] font-bold">
                REAL EXECUTION
              </span>
            </div>
            <p className="text-xs text-[#444651] mb-4 leading-relaxed">
              A real code-runner: every submission executes on Judge0, an isolated external
              sandbox, and a solved problem writes real practice evidence into the same
              competency scoring the Prerequisite Pathways map reads. Visible only to learners
              who selected DSA Fundamentals.
            </p>
          </div>
          <div className="flex items-center justify-between pt-2 border-t border-[#eaedff]">
            <Link
              href="/dsa-sandbox"
              className="text-[#00236f] hover:underline text-xs font-semibold flex items-center gap-1"
            >
              <span>Open the DSA sandbox</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>

        {/* Module 4: Document Ingestion & retrieval */}
        <div className="bg-white rounded-xl p-5 shadow-sm border border-[#c5c5d3]/30 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-[#eaedff] mb-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-[#e2e7ff] text-[#00236f] flex items-center justify-center font-bold">
                  <BookOpen className="w-[18px] h-[18px]" />
                </div>
                <h3 className="text-base font-bold text-[#00236f]">Document Ingestion &amp; Retrieval</h3>
              </div>
              <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#e2e7ff] text-[#00236f] font-bold">
                LEXICAL, NOT EMBEDDINGS
              </span>
            </div>
            <p className="text-xs text-[#444651] mb-4 leading-relaxed">
              Quiz questions are grounded in real, hash-verified government documents via
              deterministic extraction, with an optional Gemini-assisted generation path. Retrieval
              today is keyword/lexical matching, not a vector embedding index.
            </p>
          </div>
          <div className="flex items-center justify-between pt-2 border-t border-[#eaedff]">
            <span className="font-mono text-[11px] text-[#757682]">backend/services/competency_docs.py</span>
          </div>
        </div>
      </div>

      {/* Design-intent ledger */}
      <div className="bg-white rounded-xl shadow-sm border border-[#c5c5d3]/30 overflow-hidden mb-6">
        <div className="px-5 py-3.5 bg-[#f2f3ff] border-b border-[#c5c5d3]/30 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Table2 className="w-5 h-5 text-[#00236f]" />
            <h3 className="text-sm font-bold text-[#00236f]">Integration Status</h3>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead className="bg-[#eaedff]/60 text-[#444651] border-b border-[#c5c5d3]/30 text-[11px] uppercase">
              <tr>
                <th className="py-2.5 px-4">Target system</th>
                <th className="py-2.5 px-4">Today</th>
                <th className="py-2.5 px-4 text-right">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#eaedff] text-[#131b2e]">
              <tr>
                <td className="py-3 px-4 font-bold text-[#00236f]">iGOT Karmayogi</td>
                <td className="py-3 px-4">Static catalog fallback</td>
                <td className="py-3 px-4 text-right">
                  <span className="px-2 py-0.5 rounded bg-[#f2f3ff] text-[#757682] font-bold text-[10px]">
                    NOT LIVE
                  </span>
                </td>
              </tr>
              <tr>
                <td className="py-3 px-4 font-bold text-[#00236f]">NSSTA Registry</td>
                <td className="py-3 px-4">Static catalog</td>
                <td className="py-3 px-4 text-right">
                  <span className="px-2 py-0.5 rounded bg-[#f2f3ff] text-[#757682] font-bold text-[10px]">
                    NOT LIVE
                  </span>
                </td>
              </tr>
              <tr>
                <td className="py-3 px-4 font-bold text-[#00236f]">Document retrieval</td>
                <td className="py-3 px-4">Real, hash-verified corpus; lexical match</td>
                <td className="py-3 px-4 text-right">
                  <span className="px-2 py-0.5 rounded bg-[#89f5e7]/40 text-[#00312c] font-bold text-[10px]">
                    IMPLEMENTED
                  </span>
                </td>
              </tr>
              <tr>
                <td className="py-3 px-4 font-bold text-[#00236f]">Quest practice mode</td>
                <td className="py-3 px-4">Client-side WASM (Pyodide), opt-in</td>
                <td className="py-3 px-4 text-right">
                  <span className="px-2 py-0.5 rounded bg-[#89f5e7]/40 text-[#00312c] font-bold text-[10px]">
                    IMPLEMENTED, OPT-IN
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="p-4 bg-[#f2f3ff] border-t border-[#c5c5d3]/30 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs text-[#757682]">
            <ShieldCheck className="w-[18px] h-[18px] text-[#00236f]" />
            <span>This is a hackathon prototype, not an audited or certified production system.</span>
          </div>
          <button
            onClick={handleExportTopology}
            className="bg-[#00236f] hover:bg-[#1e3a8a] text-white px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5"
          >
            <Download className="w-4 h-4" />
            <span>Export design-intent topology</span>
          </button>
        </div>
      </div>
    </div>
  );
}
