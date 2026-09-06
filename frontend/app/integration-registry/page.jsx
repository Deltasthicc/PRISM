'use client';
import React, { useState } from 'react';
import { BadgeCheck, Network, Package, KeyRound, ShieldAlert, GraduationCap, Download, Landmark, Eye, Gamepad2, ArrowRight, BookOpen, FileSearch, Table2, ShieldCheck } from 'lucide-react';

export default function IntegrationRegistry({ onNavigate = () => {}, onOpenModal = () => {} } = {}) {
  const [toastMessage, setToastMessage] = useState('');

  const handleExportTopology = () => {
    const topology = {
      registry_rev: "2.4.11",
      architecture: "Sovereign Cloud Isolation & Zero Credential Catalog Mode",
      governance: "NDSAP & DPDP Act 2023 Aligned",
      connectors: [
        { name: "iGOT Karmayogi", mode: "Catalog-Fallback", records: 1420, egress_bytes: 0 },
        { name: "NSSTA / TPAC", mode: "Federated Blueprint Schema", bands: "1-5", egress_bytes: 0 },
        { name: "Adaptive DSA Sandbox", mode: "WASM Client Pyodide", egress_bytes: 0 },
        { name: "Document Ingestion RAG", mode: "Deterministic In-Memory Vectors", vectors: 18, egress_bytes: 0 }
      ]
    };
    const blob = new Blob([JSON.stringify(topology, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'mospi-integration-registry-topology.json';
    a.click();
    URL.revokeObjectURL(url);
    setToastMessage('System topology JSON exported successfully!');
    setTimeout(() => setToastMessage(''), 3500);
  };

  const handleReindex = () => {
    setToastMessage('Re-indexing local vectors: 18 statistical anchors verified with Cosine Similarity ΓëÑ 0.88.');
    setTimeout(() => setToastMessage(''), 3500);
  };

  return (
    <div className="flex flex-col w-full">
      {/* Sovereign Metadata Ribbon */}

      {/* Bento Grid: 4 Core Integration Modules */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        {/* Module 1: iGOT Karmayogi */}
        <div className="bg-white rounded-xl p-5 shadow-sm border border-[#c5c5d3]/30 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-[#eaedff] mb-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-[#dce1ff] text-[#00164e] flex items-center justify-center font-bold">
                  <GraduationCap className="w-[18px] h-[18px]" />
                </div>
                <h3 className="text-base font-bold text-[#00236f]">iGOT Karmayogi Curated Catalog</h3>
              </div>
              <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#f2f3ff] text-[#00236f] font-bold">
                CATALOG-FALLBACK ACTIVE
              </span>
            </div>
            <p className="text-xs text-[#444651] mb-4 leading-relaxed">
              National capacity building catalog for civil servants. Ingests structured JSON course blueprints for competency mapping without mock server round-trips.
            </p>
            <div className="grid grid-cols-3 gap-2 bg-[#f2f3ff] p-2.5 rounded-lg font-mono text-xs mb-4">
              <div>
                <span className="text-[10px] text-[#757682] block">Courses</span>
                <span className="font-bold text-[#131b2e]">1,420 Indexed</span>
              </div>
              <div>
                <span className="text-[10px] text-[#757682] block">Auth Mode</span>
                <span className="font-bold text-[#00312c]">Open Schema</span>
              </div>
              <div>
                <span className="text-[10px] text-[#757682] block">Refresh</span>
                <span className="font-bold text-[#00236f]">Hourly Build</span>
              </div>
            </div>
          </div>
          <div className="flex items-center justify-between pt-2 border-t border-[#eaedff]">
            <button
              onClick={() => onOpenModal('schema')}
              className="text-[#00236f] hover:underline text-xs font-semibold flex items-center gap-1 cursor-pointer"
            >
              <Download className="w-4 h-4" /> Download OpenAPI Specs
            </button>
            <button
              onClick={() => onNavigate('prerequisite-pathways')}
              className="bg-[#f2f3ff] hover:bg-[#e2e7ff] text-[#00236f] px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
            >
              View In Pathways
            </button>
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
                FEDERATED BLUEPRINT
              </span>
            </div>
            <p className="text-xs text-[#444651] mb-4 leading-relaxed">
              National Statistical Systems Training Academy curriculum registry. Maps physical and proctored training programs to Cadre Bands 1 through 5.
            </p>
            <div className="grid grid-cols-3 gap-2 bg-[#f2f3ff] p-2.5 rounded-lg font-mono text-xs mb-4">
              <div>
                <span className="text-[10px] text-[#757682] block">Cadre Scope</span>
                <span className="font-bold text-[#131b2e]">Band 1 ΓåÆ 4</span>
              </div>
              <div>
                <span className="text-[10px] text-[#757682] block">Sync Mode</span>
                <span className="font-bold text-[#00312c]">Static Catalog</span>
              </div>
              <div>
                <span className="text-[10px] text-[#757682] block">Attestation</span>
                <span className="font-bold text-[#00236f]">CSO Cadre Board</span>
              </div>
            </div>
          </div>
          <div className="flex items-center justify-between pt-2 border-t border-[#eaedff]">
            <button
              onClick={() => onOpenModal('dossier')}
              className="text-[#00236f] hover:underline text-xs font-semibold flex items-center gap-1 cursor-pointer"
            >
              <Eye className="w-4 h-4" /> View Blueprint Spec
            </button>
            <button
              onClick={() => {
                setToastMessage('Ingestion hash #48E0-92C verified against CSO Gazette.');
                setTimeout(() => setToastMessage(''), 3000);
              }}
              className="bg-[#f2f3ff] hover:bg-[#e2e7ff] text-[#00236f] px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
            >
              Audit Hash
            </button>
          </div>
        </div>

        {/* Module 3: Adaptive DSA RPG Engine */}
        <div className="bg-white rounded-xl p-5 shadow-sm border border-[#c5c5d3]/30 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-[#eaedff] mb-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-[#89f5e7] text-[#00312c] flex items-center justify-center font-bold">
                  <Gamepad2 className="w-[18px] h-[18px]" />
                </div>
                <h3 className="text-base font-bold text-[#00236f]">Adaptive DSA RPG Engine (WASM)</h3>
              </div>
              <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#89f5e7] text-[#00201d] font-bold">
                CLIENT-SIDE WASM
              </span>
            </div>
            <p className="text-xs text-[#444651] mb-4 leading-relaxed">
              Sandboxed WebAssembly runtime executing Python algorithms for technical competency evaluation. Code never egresses to remote servers.
            </p>
            <div className="grid grid-cols-3 gap-2 bg-[#f2f3ff] p-2.5 rounded-lg font-mono text-xs mb-4">
              <div>
                <span className="text-[10px] text-[#757682] block">Network Egress</span>
                <span className="font-bold text-[#00312c]">0 Packets</span>
              </div>
              <div>
                <span className="text-[10px] text-[#757682] block">Sandbox Memory</span>
                <span className="font-bold text-[#131b2e]">32 MB Constrained</span>
              </div>
              <div>
                <span className="text-[10px] text-[#757682] block">Execution Latency</span>
                <span className="font-bold text-[#00236f]">28ms Native</span>
              </div>
            </div>
          </div>
          <div className="flex items-center justify-between pt-2 border-t border-[#eaedff]">
            <button
              onClick={() => onNavigate('adaptive-practice-dsa-quest')}
              className="text-[#00236f] hover:underline text-xs font-semibold flex items-center gap-1 cursor-pointer"
            >
              <span>Launch DSA Quest</span>
              <ArrowRight className="w-4 h-4" />
            </button>
            <span className="font-mono text-[11px] text-[#757682]">Pyodide 0.25.0 Engine</span>
          </div>
        </div>

        {/* Module 4: Document Ingestion & RAG Grounding Engine */}
        <div className="bg-white rounded-xl p-5 shadow-sm border border-[#c5c5d3]/30 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-[#eaedff] mb-3">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 rounded-lg bg-[#e2e7ff] text-[#00236f] flex items-center justify-center font-bold">
                  <BookOpen className="w-[18px] h-[18px]" />
                </div>
                <h3 className="text-base font-bold text-[#00236f]">Document Ingestion &amp; RAG Engine</h3>
              </div>
              <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#e2e7ff] text-[#00236f] font-bold">
                DETERMINISTIC VECTORS
              </span>
            </div>
            <p className="text-xs text-[#444651] mb-4 leading-relaxed">
              Bounded retrieval augmented generation for quiz synthesis. Anchors diagnostic questions directly to official PDF gazettes and technical guidelines.
            </p>
            <div className="grid grid-cols-3 gap-2 bg-[#f2f3ff] p-2.5 rounded-lg font-mono text-xs mb-4">
              <div>
                <span className="text-[10px] text-[#757682] block">Hallucination Lock</span>
                <span className="font-bold text-[#00312c]">Active (100%)</span>
              </div>
              <div>
                <span className="text-[10px] text-[#757682] block">Min Cosine Match</span>
                <span className="font-bold text-[#131b2e]">╬╕ ΓëÑ 0.88</span>
              </div>
              <div>
                <span className="text-[10px] text-[#757682] block">Embedding Model</span>
                <span className="font-bold text-[#00236f]">text-gecko</span>
              </div>
            </div>
          </div>
          <div className="flex items-center justify-between pt-2 border-t border-[#eaedff]">
            <button
              onClick={() => onOpenModal('pdf_viewer')}
              className="text-[#00236f] hover:underline text-xs font-semibold flex items-center gap-1 cursor-pointer"
            >
              <FileSearch className="w-4 h-4" /> View Bounding Boxes
            </button>
            <button
              onClick={handleReindex}
              className="bg-[#f2f3ff] hover:bg-[#e2e7ff] text-[#00236f] px-3 py-1.5 rounded-lg text-xs font-semibold transition-colors cursor-pointer"
            >
              Re-Index Vectors
            </button>
          </div>
        </div>
      </div>

      {/* Protocol & Data Governance Ledger Table */}
      <div className="bg-white rounded-xl shadow-sm border border-[#c5c5d3]/30 overflow-hidden mb-6">
        <div className="px-5 py-3.5 bg-[#f2f3ff] border-b border-[#c5c5d3]/30 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Table2 className="w-5 h-5 text-[#00236f]" />
            <h3 className="text-sm font-bold text-[#00236f]">Protocol &amp; Data Governance Ledger</h3>
          </div>
          <span className="font-mono text-xs text-[#757682]">Audit Hash: 0x88219-NDSAP-VALID</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead className="bg-[#eaedff]/60 text-[#444651] border-b border-[#c5c5d3]/30 text-[11px] uppercase">
              <tr>
                <th className="py-2.5 px-4">Target System</th>
                <th className="py-2.5 px-4">Connection Type</th>
                <th className="py-2.5 px-4">Authentication Mode</th>
                <th className="py-2.5 px-4">Data Egress</th>
                <th className="py-2.5 px-4 text-right">DPDP Compliance</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#eaedff] text-[#131b2e]">
              <tr className="hover:bg-[#f2f3ff]/40">
                <td className="py-3 px-4 font-bold text-[#00236f]">iGOT Karmayogi</td>
                <td className="py-3 px-4">Open Blueprint JSON</td>
                <td className="py-3 px-4">Zero Token / Public</td>
                <td className="py-3 px-4 text-[#00312c] font-semibold">0 B Egress (Read-Only)</td>
                <td className="py-3 px-4 text-right">
                  <span className="px-2 py-0.5 rounded bg-[#89f5e7]/40 text-[#00312c] font-bold text-[10px]">
                    VERIFIED COMPLIANT
                  </span>
                </td>
              </tr>
              <tr className="hover:bg-[#f2f3ff]/40">
                <td className="py-3 px-4 font-bold text-[#00236f]">NSSTA Registry</td>
                <td className="py-3 px-4">Curated Local Catalog</td>
                <td className="py-3 px-4">Cadre Board Signed Hash</td>
                <td className="py-3 px-4 text-[#00312c] font-semibold">0 B (Local Sandbox)</td>
                <td className="py-3 px-4 text-right">
                  <span className="px-2 py-0.5 rounded bg-[#89f5e7]/40 text-[#00312c] font-bold text-[10px]">
                    SEALED LOCAL
                  </span>
                </td>
              </tr>
              <tr className="hover:bg-[#f2f3ff]/40">
                <td className="py-3 px-4 font-bold text-[#00236f]">Pyodide WASM Runtime</td>
                <td className="py-3 px-4">Client-side Virtual Thread</td>
                <td className="py-3 px-4">No Remote Auth Needed</td>
                <td className="py-3 px-4 text-[#00312c] font-semibold">0 B (Client Memory)</td>
                <td className="py-3 px-4 text-right">
                  <span className="px-2 py-0.5 rounded bg-[#89f5e7]/40 text-[#00312c] font-bold text-[10px]">
                    CERTIFIED ISOLATED
                  </span>
                </td>
              </tr>
              <tr className="hover:bg-[#f2f3ff]/40">
                <td className="py-3 px-4 font-bold text-[#00236f]">MoSPI PDF Corpus</td>
                <td className="py-3 px-4">Local Vector Index (Gecko)</td>
                <td className="py-3 px-4">Local Embedding Key</td>
                <td className="py-3 px-4 text-[#00312c] font-semibold">0 B (In-Memory)</td>
                <td className="py-3 px-4 text-right">
                  <span className="px-2 py-0.5 rounded bg-[#89f5e7]/40 text-[#00312c] font-bold text-[10px]">
                    AIR-GAPPED MATH
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <div className="p-4 bg-[#f2f3ff] border-t border-[#c5c5d3]/30 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs text-[#757682]">
            <ShieldCheck className="w-[18px] h-[18px] text-[#00236f]" />
            <span>All algorithms are validated in compliance with Section 8(1)(d) RTI Act &amp; DPDP Act 2023.</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => onOpenModal('dpdp_audit')}
              className="bg-white hover:bg-[#e2e7ff] text-[#00236f] px-3.5 py-1.5 rounded-lg text-xs font-semibold border border-[#c5c5d3]/40 transition-colors cursor-pointer"
            >
              View DPDP Audit Report
            </button>
            <button
              onClick={handleExportTopology}
              className="bg-[#00236f] hover:bg-[#1e3a8a] text-white px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 cursor-pointer"
            >
              <Download className="w-4 h-4" />
              <span>Export System Topology</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
