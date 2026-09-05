'use client';
import React, { useState } from 'react';
import { SquareCheckBig, Bolt, Lock, Check, Route, Play, Swords } from 'lucide-react';

export default function PrerequisitePathways({ onNavigate, onOpenModal }) {
  const [activeCourseNode, setActiveCourseNode] = useState(2);
  const [inFlightProgress, setInFlightProgress] = useState(64);
  const [courseToast, setCourseToast] = useState('');

  const handleContinueCourse = () => {
    setCourseToast('Synchronizing PySpark 3.4.1 GovEnv cluster state: Advancing Module 5 of 8...');
    setTimeout(() => {
      setInFlightProgress(75);
      setCourseToast('PySpark GovEnv checkpoint saved! Progress updated to 75% (Module 6: Window Functions & Shuffling).');
      setTimeout(() => setCourseToast(''), 4000);
    }, 800);
  };

  const handleExportGraph = () => {
    const graphData = {
      algorithm: "Kahn's Topological Sort v2.4",
      schema: "NDSAP-iGOT-v3.1",
      cycle_free: true,
      cadre: "Senior Statistical Officer (CSO-HQ)",
      nodes: [
        { id: "NODE_01", code: "NSSTA-STAT-701", status: "VERIFIED", ceu: 4.0 },
        { id: "NODE_02", code: "IGOT-CLD-SPARK-04", status: "IN_FLIGHT", progress: inFlightProgress },
        { id: "NODE_03", code: "MEITY-GOV-AI-01", status: "LOCKED", depends_on: ["NODE_02"] },
        { id: "NODE_04", code: "DSA-QUEST-SANDBOX", status: "PRACTICE_ACTIVE", xp: 180 }
      ]
    };
    const blob = new Blob([JSON.stringify(graphData, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'mospi-prerequisite-dag-kahn.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col w-full">
      {/* Context & Provenance Strip */}
      <div className="flex flex-col gap-3 mb-4">

        {courseToast && (
          <div className="px-4 py-2.5 bg-[#dce1ff] text-[#00164e] rounded-lg text-xs font-mono flex items-center gap-2 border border-[#b6c4ff] shadow-sm animate-in fade-in duration-200">
            <span className="material-symbols-outlined text-[18px] text-[#00236f]">check_circle</span>
            <span>{courseToast}</span>
          </div>
        )}

        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-3">
          <div className="space-y-1">
            <div className="flex items-center gap-3 flex-wrap">
              <h1 className="text-2xl sm:text-3xl font-bold text-[#00236f] tracking-tight">
                Prerequisite-Aware Learning Pathways
              </h1>

            </div>
          </div>
        </div>
      </div>

      {/* KPI Cards: High Visual Rhythm & Contrast */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        {/* Card 1: Completed Stage */}
        <div className="relative overflow-hidden bg-white rounded-xl p-5 shadow-sm border border-[#c5c5d3]/30 transition-transform hover:-translate-y-0.5">
          <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-[#004942]"></div>
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-[#89f5e7] text-[#00201d] flex items-center justify-center">
                <SquareCheckBig size={18} />
              </div>
              <span className="font-mono text-[10px] uppercase tracking-wider text-[#444651] font-bold">Stage 01</span>
            </div>
            <span className="font-mono text-xs px-2 py-0.5 rounded bg-[#6bd8cb]/40 text-[#00312c] font-semibold">
              VERIFIED
            </span>
          </div>
          <h3 className="text-base font-semibold text-[#131b2e] mb-1">Foundational Sampling &amp; NSO</h3>
          <p className="text-xs text-[#444651] mb-4">NSSTA / MoSPI Training Division curriculum benchmarked.</p>
          <div className="flex items-center justify-between font-mono text-xs pt-2 bg-[#f2f3ff]/60 rounded px-2">
            <span className="text-[#444651]">Prereq Sat: 100%</span>
            <span className="text-[#00312c] font-bold">4.0 CEU Conferred</span>
          </div>
        </div>

        {/* Card 2: Active Stage */}
        <div className="relative overflow-hidden bg-white rounded-xl p-5 shadow-sm border border-[#c5c5d3]/30 transition-transform hover:-translate-y-0.5">
          <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-[#00236f]"></div>
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-[#dce1ff] text-[#00164e] flex items-center justify-center">
                <Bolt size={18} />
              </div>
              <span className="font-mono text-[10px] uppercase tracking-wider text-[#00236f] font-bold">Stage 02</span>
            </div>
            <span className="font-mono text-xs px-2 py-0.5 rounded bg-[#b6c4ff]/40 text-[#00236f] font-semibold">
              {inFlightProgress}% ACTIVE
            </span>
          </div>
          <h3 className="text-base font-semibold text-[#131b2e] mb-1">Distributed Sovereign Cloud</h3>
          <p className="text-xs text-[#444651] mb-3">iGOT Karmayogi Catalog • Module 5 of 8 in runtime.</p>
          <div className="w-full bg-[#e2e7ff] h-1.5 rounded-full overflow-hidden mb-1">
            <div
              className="bg-[#00236f] h-full rounded-full transition-all duration-500"
              style={{ width: `${inFlightProgress}%` }}
            ></div>
          </div>
          <div className="flex items-center justify-between font-mono text-[11px] text-[#757682]">
            <span>Target: NIC-GovCloud</span>
            <span className="text-[#00236f] font-semibold">Pacing: On Track</span>
          </div>
        </div>

        {/* Card 3: Locked Target */}
        <div className="relative overflow-hidden bg-white rounded-xl p-5 shadow-sm border border-[#c5c5d3]/30 transition-transform hover:-translate-y-0.5">
          <div className="absolute left-0 top-0 bottom-0 w-1.5 bg-[#fe932c]"></div>
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-lg bg-[#ffdcc3] text-[#2f1500] flex items-center justify-center">
                <Lock size={18} />
              </div>
              <span className="font-mono text-[10px] uppercase tracking-wider text-[#904d00] font-bold">Stage 03</span>
            </div>
            <span className="font-mono text-xs px-2 py-0.5 rounded bg-[#ffb77d]/40 text-[#904d00] font-semibold">
              LOCKED TARGET
            </span>
          </div>
          <h3 className="text-base font-semibold text-[#131b2e] mb-1">Sovereign AI Governance</h3>
          <p className="text-xs text-[#444651] mb-4">TPAC / MeitY Blueprint • Unlocks post Spark validation.</p>
          <div className="flex items-center justify-between font-mono text-xs pt-2 bg-[#f2f3ff]/60 rounded px-2">
            <span className="text-[#757682]">Unmet Dependencies: 1</span>
            <span className="text-[#904d00] font-semibold">Est. Start: Q2 2025</span>
          </div>
        </div>
      </div>

      {/* Directed Acyclic Graph (DAG) Execution Flow */}
      <div className="w-full max-w-5xl mx-auto flex flex-col mb-6">
        <div className="flex items-center justify-between pb-2 mb-4">
          <div className="flex items-center gap-2">
            <Route size={22} className="text-[#00236f]" />
            <span className="text-base font-bold text-[#00236f]">Directed Acyclic Graph (DAG) Execution Flow</span>
          </div>
          <span className="font-mono text-xs text-[#757682]">Resolution Order: [KAHN_ORD: 01 → 02 → 03 → 04]</span>
        </div>

        {/* Node 1: Completed */}
        <div className="flex flex-col md:flex-row items-stretch gap-4 relative">
          <div className="hidden md:flex flex-col items-center w-12 shrink-0">
            <div className="w-10 h-10 rounded-full bg-[#89f5e7] text-[#00312c] flex items-center justify-center shadow-xs font-mono font-bold">
              <Check size={20} />
            </div>
            {/*<div className="w-0.5 grow bg-[#dae2fd] my-1"></div>*/}
          </div>
          <div className="flex-1 bg-white rounded-xl p-5 shadow-sm relative overflow-hidden border border-[#c5c5d3]/30">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#89f5e7] text-[#00201d] font-bold">
                  Course Code or whatevr
                </span>
                <span className="font-mono text-[10px] text-[#757682]">LOREM: IPSUM DOREM</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-[#f2f3ff] text-[#00312c] font-semibold flex items-center gap-1">
                  <span className="material-symbols-outlined text-[14px]">workspace_premium</span> 4.0 CEU Conferred
                </span>
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-[#00312c] text-white font-medium">
                  Verified
                </span>
              </div>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 items-center">
              <div className="lg:col-span-3 space-y-1">
                <h2 className="text-lg font-bold text-[#131b2e]">
                  Advanced Sampling Techniques for Official Statistics
                </h2>
                <p className="text-sm text-[#444651]">
                  Multistage stratified sampling, NSSO standard error estimation formulas, finite population corrections, and non-sampling bias attenuation across longitudinal surveys.
                </p>
                <div className="pt-2 flex items-center gap-4 flex-wrap font-mono text-xs text-[#757682]">
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-[15px]">domain</span> NSSTA / MoSPI Division
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-[15px]">event_available</span> Completed Oct 14, 2024
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-[15px]">fingerprint</span> Cert Hash: #48E0-92C
                  </span>
                </div>
              </div>
              <div className="lg:col-span-1 flex flex-col items-start lg:items-end justify-center">
                <button
                  onClick={() => onOpenModal('dossier')}
                  className="bg-[#f2f3ff] hover:bg-[#e2e7ff] text-[#00236f] px-3.5 py-2 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1 shadow-xs cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[16px]">visibility</span> Review Dossier
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Connector: Node 1 -> Node 2 */}
        <div className="flex items-center gap-4 my-2 ml-0 md:ml-12 pl-0 md:pl-6">
          <div className="h-3 w-0.5 bg-[transparent] hidden md:block"></div>
        </div>

        {/* Node 2: Active (Hero in Kahn sequence) */}
        <div className="flex flex-col md:flex-row items-stretch gap-4 relative">
          <div className="hidden md:flex flex-col items-center w-12 shrink-0">
            <div className="w-10 h-10 rounded-full bg-[#00236f] text-white flex items-center justify-center shadow-md font-mono font-bold ring-4 ring-[#dce1ff]">
              <Play size={20} />
            </div>
          </div>
          <div className="flex-1 bg-white rounded-xl p-5 shadow-md relative overflow-hidden border border-[#00236f]/40">
            <div className="absolute left-0 top-0 bottom-0 w-2 bg-[#00236f]"></div>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#dce1ff] text-[#00164e] font-bold">
                  NODE #02 • IGOT-CLD-SPARK-04
                </span>
                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#e2e7ff] text-[#444651]">
                  CATALOG FALLBACK ACTIVE
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-[#ffdcc3] text-[#2f1500] font-semibold">
                  In-Flight Resolution
                </span>
              </div>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-center">
              <div className="lg:col-span-8 space-y-2">
                <h2 className="text-lg font-bold text-[#00236f]">
                  Distributed Data Processing with Apache Spark on GovCloud
                </h2>
                <p className="text-sm text-[#444651]">
                  Execution of distributed RDD transformations, Parquet partitioning on NIC cloud clusters, MoSPI micro-data extraction pipelines, and automated memory management over multi-terabyte survey rounds.
                </p>
                <div className="bg-[#f2f3ff] rounded-lg p-3 space-y-2 mt-2 border border-[#c5c5d3]/30">
                  <div className="flex items-center justify-between text-xs">
                    <span className="font-semibold text-[#131b2e]">Curriculum Progress: {inFlightProgress}%</span>
                    <span className="font-mono text-xs text-[#00236f] font-bold">
                      Module {inFlightProgress >= 75 ? '6' : '5'} of 8 (Resilient Datasets)
                    </span>
                  </div>
                  <div className="w-full bg-[#e2e7ff] h-2.5 rounded-full overflow-hidden">
                    <div
                      className="bg-[#00236f] h-full rounded-full transition-all duration-300"
                      style={{ width: `${inFlightProgress}%` }}
                    ></div>
                  </div>
                  <div className="flex items-center justify-between font-mono text-[11px] text-[#757682] pt-0.5">
                    <span>Ingestion source: iGOT Karmayogi Curated Schema</span>
                    <span className="text-[#131b2e] font-medium">Target Node: NIC-GovCloud #Cluster-04</span>
                  </div>
                </div>
              </div>
              <div className="lg:col-span-4 flex flex-col gap-3 items-start lg:items-end justify-center">
                <div className="bg-[#f2f3ff] p-3 rounded-lg w-full text-left space-y-1 border border-[#c5c5d3]/30">
                  <div className="font-mono text-[10px] text-[#757682] uppercase">Active Environment</div>
                  <div className="font-mono text-xs text-[#131b2e] font-semibold flex items-center gap-1.5">
                    <span className="w-2 h-2 rounded-full bg-[#00312c] animate-pulse"></span> PySpark 3.4.1 GovEnv
                  </div>
                  <div className="font-mono text-[11px] text-[#757682]">Port 8080 • SSL Secured</div>
                </div>
                <button
                  onClick={handleContinueCourse}
                  className="w-full bg-[#00236f] hover:bg-[#1e3a8a] text-white px-4 py-2.5 rounded-lg text-sm font-semibold transition-all shadow-sm flex items-center justify-center gap-2 cursor-pointer"
                >
                  Continue Course <span className="material-symbols-outlined text-[18px]">arrow_forward</span>
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Connector: Node 2 -> Node 3 */}
        <div className="flex items-center gap-4 my-2 ml-0 md:ml-12 pl-0 md:pl-6">
          <div className="h-3 w-0.5 bg-[transparent] hidden md:block"></div>
        </div>

        {/* Node 3: Locked Target */}
        <div className="flex flex-col md:flex-row items-stretch gap-4 relative">
          <div className="hidden md:flex flex-col items-center w-12 shrink-0">
            <div className="w-10 h-10 rounded-full bg-[#e2e7ff] text-[#757682] flex items-center justify-center shadow-xs font-mono font-bold">
              <Lock size={20}/>
            </div>
          </div>
          <div className="flex-1 bg-white/90 rounded-xl p-5 shadow-xs relative overflow-hidden border border-[#c5c5d3]/30 opacity-90 hover:opacity-100 transition-opacity">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#e2e7ff] text-[#444651] font-bold">
                  NODE #03 • MEITY-GOV-AI-01
                </span>
                <span className="font-mono text-[10px] text-[#757682]">TARGET OBJECTIVE</span>
              </div>
              <span className="font-mono text-xs px-2 py-0.5 rounded bg-[#eaedff] text-[#757682] flex items-center gap-1">
                <Lock size={16}/> Locked Dependency
              </span>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-center">
              <div className="lg:col-span-9 space-y-1">
                <h2 className="text-lg font-bold text-[#444651]">
                  Sovereign AI Governance &amp; Algorithmic Impact Assessment
                </h2>
                <p className="text-sm text-[#757682]">
                  Ethical AI validation protocols for national micro-datasets, algorithmic bias mitigation in economic indices, statutory compliance with Digital Personal Data Protection (DPDP) Act 2023.
                </p>
                <div className="pt-2 flex items-center gap-4 flex-wrap font-mono text-xs text-[#757682]">
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-[15px]">account_balance</span> TPAC / MeitY Blueprint
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-[15px]">timer</span> Estimated Effort: 36 Hrs
                  </span>
                  <span className="flex items-center gap-1 text-[#904d00] font-semibold">
                    <span className="material-symbols-outlined text-[15px]">priority_high</span> Pre-req: Complete Node #02
                  </span>
                </div>
              </div>
              <div className="lg:col-span-3 flex flex-col items-start lg:items-end justify-center">
                <button
                  disabled
                  className="bg-[#eaedff] text-[#757682] px-4 py-2 rounded-lg text-xs font-semibold cursor-not-allowed flex items-center gap-1 border border-[#c5c5d3]/30"
                >
                  <span className="material-symbols-outlined text-[16px]">lock</span> Enqueue Module
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Connector: Node 3 -> Node 4 */}
        <div className="flex items-center gap-4 my-2 ml-0 md:ml-12 pl-0 md:pl-6">
          <div className="h-3 w-0.5 bg-[transparent] hidden md:block"></div>
        </div>

        {/* Node 4: Quest Mode Practice Sandbox */}
        <div className="flex flex-col md:flex-row items-stretch gap-4 relative mb-6">
          <div className="hidden md:flex flex-col items-center w-12 shrink-0">
            <div className="w-10 h-10 rounded-full bg-[#ffdcc3] text-[#2f1500] flex items-center justify-center shadow-xs font-mono font-bold">
              <Swords size={20}/>
            </div>
          </div>
          <div className="flex-1 bg-white rounded-xl p-5 shadow-sm relative overflow-hidden border border-[#c5c5d3]/30">
            <div className="absolute right-0 top-0 bottom-0 w-32 bg-gradient-to-l from-[#ffdcc3]/20 to-transparent pointer-events-none"></div>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#904d00] text-white font-bold">
                  NODE #04 • DSA QUEST SANDBOX
                </span>
                <span className="font-mono text-[10px] text-[#757682]">GAMIFIED COMPETENCY LAB</span>
              </div>
              <span className="font-mono text-xs px-2 py-0.5 rounded bg-[#ffdcc3] text-[#2f1500] font-semibold flex items-center gap-1">
                <span className="material-symbols-outlined text-[15px]">military_tech</span> Difficulty Level 3
              </span>
            </div>
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4 items-center">
              <div className="lg:col-span-8 space-y-1">
                <h2 className="text-lg font-bold text-[#131b2e]">
                  Core Algorithmic Optimization &amp; DSA for Data Pipelines
                </h2>
                <p className="text-sm text-[#444651]">
                  Hands-on test arena: Resolve DAG circular dependencies, heap queue dispatchers for census sample weights, and time complexity bounds (O(N log K)) in high-throughput streams.
                </p>
                <div className="pt-2 flex items-center gap-4 flex-wrap font-mono text-xs text-[#757682]">
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-[15px]">terminal</span> Interactive Python REPL
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-[15px]">deployed_code</span> +180 MoSPI Skill XP
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="material-symbols-outlined text-[15px]">security</span> Sandbox Isolated
                  </span>
                </div>
              </div>
              <div className="lg:col-span-4 flex flex-col items-start lg:items-end justify-center">
                <button
                  onClick={() => onNavigate('adaptive-practice-dsa-quest')}
                  className="bg-[#904d00] hover:bg-[#663500] text-white px-4 py-2.5 rounded-lg text-sm font-semibold transition-all shadow-sm flex items-center gap-2 cursor-pointer"
                >
                  Launch DSA Quest <span className="material-symbols-outlined text-[18px]">sports_esports</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom Integration & Provider Summary Bar */}
      <div className="bg-[#f2f3ff] rounded-xl p-4 shadow-xs flex flex-col md:flex-row items-center justify-between gap-4 border border-[#c5c5d3]/30">
        <div className="flex items-center gap-4 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[#00312c]"></span>
            <span className="font-mono text-xs font-semibold text-[#131b2e]">Catalog Mode: Fallback Enforced</span>
          </div>
          <span className="text-[#757682] hidden sm:inline">•</span>
          <span className="text-xs text-[#444651]">NSSTA Revision 2.4 • iGOT Schema v3.1 Compliant</span>
        </div>
        <div className="flex items-center gap-3 flex-wrap">
          <button
            onClick={handleExportGraph}
            className="bg-white hover:bg-[#e2e7ff] text-[#131b2e] px-3.5 py-2 rounded-lg text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5 border border-[#c5c5d3]/30 cursor-pointer"
          >
            <span className="material-symbols-outlined text-[16px]">download</span> Export Graph (JSON)
          </button>
          <button
            onClick={() => onOpenModal('schema')}
            className="bg-white hover:bg-[#e2e7ff] text-[#131b2e] px-3.5 py-2 rounded-lg text-xs font-semibold shadow-xs transition-colors flex items-center gap-1.5 border border-[#c5c5d3]/30 cursor-pointer"
          >
            <span className="material-symbols-outlined text-[16px]">description</span> Ingestion Schema Docs
          </button>
        </div>
      </div>
    </div>
  );
}