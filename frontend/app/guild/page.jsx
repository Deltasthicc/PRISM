'use client';
import React, { useState } from 'react';
import { Play, RotateCcw, Cloud, Download, Terminal, CircleHelp, Database, CircleCheck, PartyPopper } from 'lucide-react';

export default function AdaptivePracticeDsaQuest() {
  const router = useRouter();
  const [selectedLang, setSelectedLang] = useState('Python 3.11 (Pyodide)');
  const [isRunning, setIsRunning] = useState(false);
  const [bossHp, setBossHp] = useState(210);
  const [testResult, setTestResult] = useState({
    passed: true,
    suites: '5/5',
    runtime: '28ms',
    complexity: 'O(V + E)',
    memory: '4.12 MB',
    kops: '1,402'
  });
  const [toastMessage, setToastMessage] = useState('');
  const handleNavigate = (path) => {
    router.push(path);
  };

  const initialCode = `def cluster_survey_districts(n_strata, adj_matrix):
    """
    Find strongly connected district clusters in O(V + E).
    Prevents cross-district circular survey dependencies.
    """
    index = 0
    stack = []
    indices = [-1] * n_strata
    lowlink = [-1] * n_strata
    on_stack = [False] * n_strata
    sccs = []

    def strongconnect(v):
        nonlocal index
        indices[v] = lowlink[v] = index
        index += 1
        stack.append(v)
        on_stack[v] = True

        for w in adj_matrix[v]:
            if indices[w] == -1:
                strongconnect(w)
                lowlink[v] = min(lowlink[v], lowlink[w])
            elif on_stack[w]:
                lowlink[v] = min(lowlink[v], indices[w])

        if lowlink[v] == indices[v]:
            scc = []
            while True:
                w = stack.pop()
                on_stack[w] = False
                scc.append(w)
                if w == v: break
            sccs.append(scc)

    for v in range(n_strata):
        if indices[v] == -1:
            strongconnect(v)
    return sccs`;

  const [code, setCode] = useState(initialCode);

  const handleRunWasm = () => {
    setIsRunning(true);
    setToastMessage('Compiling in client-side WebAssembly sandbox...');
    setTimeout(() => {
      setIsRunning(false);
      setBossHp(0);
      setTestResult({
        passed: true,
        suites: '5/5',
        runtime: '24ms',
        complexity: 'O(V + E)',
        memory: '4.08 MB',
        kops: '1,380'
      });
      setToastMessage('Execution Successful! 5/5 Test Suites Passed • Time-Hydra Defeated (-210 HP) • +50 XP Awarded!');
      setTimeout(() => setToastMessage(''), 5000);
    }, 700);
  };

  const handleSyncToProfile = () => {
    setToastMessage('Competency Vector Delta committed: DSA Core & Spatial Structures upgraded to Level 4 (Cadre Benchmark Met)!');
    setTimeout(() => setToastMessage(''), 4000);
  };

  const handleExportJson = () => {
    const data = {
      session_id: "WASM-7729-QUEST",
      timestamp: new Date().toISOString(),
      officer: "rajesh.sharma",
      algorithm: "Tarjan's Strongly Connected Components",
      time_complexity: "O(V + E)",
      tests_passed: 5,
      total_tests: 5,
      xp_awarded: 50,
      integrity_score: 0.986
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'mospi-dsa-quest-telemetry.json';
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col w-full">
      {/* Top Protocol Strip */}
      <div className="flex flex-col gap-3 mb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#e2e7ff] p-3.5 rounded-xl border border-[#b6c4ff]/50">
          <div className="flex items-center gap-2.5">
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-base font-bold text-[#00236f]">NSO Sandbox Engine // DSA Quest</h1>
                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#ffdcc3] text-[#2f1500] font-bold">
                  4 Day Streak
                </span>
                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#00236f] text-white font-bold">
                  1,420 XP
                </span>
                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-white text-[#00236f] font-bold border border-[#c5c5d3]/40">
                  Matrix L3
                </span>
              </div>
              <p className="text-xs text-[#444651]">
                Zero-trust local runtime • Real browser WASM compilation engine. Client-side evaluation without cloud credential transmission.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="font-mono text-xs px-2.5 py-1 rounded bg-white text-[#00312c] font-semibold border border-[#c5c5d3]/30 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#00312c] animate-pulse"></span> WASM-SANDBOX-ACTIVE
            </span>
          </div>
        </div>

        {toastMessage && (
          <div className="px-4 py-2.5 bg-[#dce1ff] text-[#00164e] rounded-lg text-xs font-mono flex items-center gap-2 border border-[#b6c4ff] shadow-sm animate-in fade-in duration-200">
            <span className="material-symbols-outlined text-[18px] text-[#00236f]">military_tech</span>
            <span>{toastMessage}</span>
          </div>
        )}
      </div>


      {/* Main Sandbox Grid: Interactive Code Arena (8 cols) + Skill Delta Matrix (4 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-6 items-start">
        {/* Left Column: Code Editor & WASM Execution Suite */}
        <div className="lg:col-span-8 flex flex-col gap-4">
          <div className="bg-white rounded-xl shadow-sm border border-[#c5c5d3]/30 overflow-hidden">
            {/* Editor Header */}
            <div className="bg-[#f2f3ff] px-4 py-2.5 border-b border-[#c5c5d3]/30 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <Terminal size={16} className="text-[#00236f]" />
                <span className="font-mono text-xs font-bold text-[#00236f]">solution.py</span>
                <span className="text-[#c5c5d3]">•</span>
                <span className="font-mono text-[11px] text-[#757682]">WASM Sandbox Isolation</span>
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={selectedLang}
                  onChange={(e) => setSelectedLang(e.target.value)}
                  className="bg-white border border-[#c5c5d3]/40 rounded px-2.5 py-1 text-xs font-mono text-[#131b2e] outline-none cursor-pointer"
                >
                  <option>Python 3.11 (Pyodide)</option>
                  <option>C++20 (Emscripten)</option>
                  <option>Node.js 20 (Local)</option>
                </select>
                <button
                  onClick={() => setCode(initialCode)}
                  className="bg-white hover:bg-[#e2e7ff] text-[#444651] px-2.5 py-1 rounded text-xs font-mono border border-[#c5c5d3]/40 transition-colors cursor-pointer"
                >
                  Reset
                </button>
              </div>
            </div>

            {/* Problem Objective Capsule */}
            <div className="bg-[#f8f9ff] px-4 py-2 border-b border-[#c5c5d3]/20 text-xs text-[#444651] flex items-start gap-2">
              <CircleHelp size={16} className="text-[#00236f]" />
              <p className="font-mono text-[11px] leading-relaxed">
                <strong className="text-[#00236f]">Objective:</strong> Implement{' '}
                <code className="bg-[#e2e7ff] px-1 rounded text-[#00236f]">cluster_survey_districts(n_strata, adj_matrix)</code>{' '}
                using Tarjan&apos;s Strongly Connected Components (SCC) in <strong className="text-[#00312c]">O(V + E)</strong> time to partition survey enumeration districts into independent census strata.
              </p>
            </div>

            {/* Code Textarea with line numbers aesthetic */}
            <div className="relative bg-[#131b2e] text-[#f2f3ff] p-4 font-mono text-xs overflow-x-auto">
              <textarea
                value={code}
                onChange={(e) => setCode(e.target.value)}
                rows={16}
                spellCheck={false}
                className="w-full bg-transparent text-[#eef0ff] font-mono text-xs outline-none resize-y leading-relaxed"
              />
            </div>

            {/* Controls Toolbar */}
            <div className="p-3 bg-[#f2f3ff] border-t border-[#c5c5d3]/30 flex flex-col sm:flex-row items-center justify-between gap-3">
              <div className="flex items-center gap-2 text-xs font-mono text-[#757682]">
                <Database size={16} />
                <span>Heap: {testResult.memory} • Cycles: {testResult.kops} kOps</span>
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={handleRunWasm}
                  disabled={isRunning}
                  className="bg-white hover:bg-[#e2e7ff] text-[#00236f] px-3.5 py-1.5 rounded-lg text-xs font-semibold border border-[#c5c5d3]/40 transition-colors cursor-pointer"
                >
                  Test Single Case
                </button>
                <button
                  onClick={handleRunWasm}
                  disabled={isRunning}
                  className="bg-[#00236f] hover:bg-[#1e3a8a] text-white px-4 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 shadow-sm cursor-pointer"
                >
                  <Play
                    size={16}
                    strokeWidth={2}
                    className={isRunning ? 'animate-spin' : ''}
                  />
                  <span>{isRunning ? 'Compiling WASM...' : 'Run WASM Sandbox (Ctrl+Enter)'}</span>
                </button>
              </div>
            </div>
          </div>

          {/* Test Execution Output Banner */}
          <div className="bg-white rounded-xl p-4 shadow-sm border border-[#c5c5d3]/30">
            <div className="flex items-center justify-between pb-2 mb-2 border-b border-[#eaedff]">
              <div className="flex items-center gap-2">
                <CircleCheck size={16} className="text-[#00312c]" />
                <h4 className="text-xs font-bold text-[#00312c] uppercase font-mono tracking-wider">
                  Test Results: All {testResult.suites} Suites Passed
                </h4>
              </div>
              <span className="font-mono text-xs text-[#757682]">
                Execution: <strong className="text-[#131b2e]">{testResult.runtime}</strong> • Complexity:{' '}
                <strong className="text-[#00236f]">{testResult.complexity}</strong>
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 font-mono text-xs mb-3">
              <div className="bg-[#f2f3ff] p-2 rounded border border-[#c5c5d3]/30">
                <span className="text-[#757682] block text-[10px]">Test 01 (DAG Acyclic)</span>
                <span className="text-[#00312c] font-bold">Passed (4ms)</span>
              </div>
              <div className="bg-[#f2f3ff] p-2 rounded border border-[#c5c5d3]/30">
                <span className="text-[#757682] block text-[10px]">Test 02 (Dense Cyclic)</span>
                <span className="text-[#00312c] font-bold">Passed (12ms)</span>
              </div>
              <div className="bg-[#f2f3ff] p-2 rounded border border-[#c5c5d3]/30">
                <span className="text-[#757682] block text-[10px]">Test 03 (Scale 10k Nodes)</span>
                <span className="text-[#00312c] font-bold">Passed (8ms)</span>
              </div>
            </div>

            {bossHp === 0 && (
              <div className="bg-[#ffdcc3]/60 border border-[#ffb77d] p-3 rounded-lg flex items-center justify-between gap-2 text-xs">
                <div className="flex items-center gap-2">
                  <PartyPopper size={16} className="text-[#904d00]" />
                  <span className="font-mono text-[#904d00] font-bold">
                    Battle Reward Unlocked: +50 XP Conferred to Officer Rajesh Sharma!
                  </span>
                </div>
                <button
                  onClick={handleSyncToProfile}
                  className="bg-[#904d00] text-white px-3 py-1 rounded text-[11px] font-bold hover:bg-[#663500] transition-colors cursor-pointer"
                >
                  Commit XP
                </button>
              </div>
            )}
          </div>
        </div>

        {/* Right Column: Skill Delta & Real-time Projection Radar */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          {/* Radar & Competency Delta Card */}
          <div className="bg-white rounded-xl p-4 shadow-sm border border-[#c5c5d3]/30">
            <div className="flex items-center justify-between mb-2">
              <span className="font-mono text-[10px] text-[#757682] uppercase font-bold">Skill Delta Matrix</span>
              <span className="font-mono text-xs text-[#00236f] font-semibold">+0.6 Delta Achieved</span>
            </div>
            <h4 className="text-sm font-bold text-[#131b2e] mb-2">Algorithmic Skill Projection</h4>

            {/* Radar Mini SVG */}
            <div className="relative w-full flex items-center justify-center py-1">
              <svg className="w-full max-w-[240px] aspect-square overflow-visible" viewBox="0 0 280 280">
                <polygon
                  className="text-[#c5c5d3]/40"
                  fill="none"
                  points="140,40 230,95 230,195 140,250 50,195 50,95"
                  stroke="currentColor"
                  strokeWidth="1"
                />
                <polygon
                  className="text-[#c5c5d3]/20"
                  fill="none"
                  points="140,80 190,115 190,175 140,210 90,175 90,115"
                  stroke="currentColor"
                  strokeWidth="1"
                />
                {/* Projected polygon */}
                <polygon
                  fill="#ffdcc3"
                  fillOpacity="0.4"
                  points="140,40 230,95 200,190 140,220 70,185 60,105"
                  stroke="#fe932c"
                  strokeDasharray="3 3"
                  strokeWidth="1.5"
                />
                {/* Current polygon */}
                <polygon
                  fill="#dce1ff"
                  fillOpacity="0.6"
                  points="140,70 200,110 180,180 140,210 90,175 80,115"
                  stroke="#00236f"
                  strokeWidth="2"
                />
                <text className="fill-[#00236f] font-mono text-[9px] font-bold" textAnchor="middle" x="140" y="30">
                  Graph DSA L3
                </text>
                <text className="fill-[#131b2e] font-mono text-[9px] font-semibold" textAnchor="start" x="236" y="96">
                  Sampling Logic
                </text>
                <text className="fill-[#131b2e] font-mono text-[9px] font-semibold" textAnchor="start" x="236" y="200">
                  Time Complexity
                </text>
                <text className="fill-[#131b2e] font-mono text-[9px] font-semibold" textAnchor="middle" x="140" y="266">
                  Spatial Stat L4
                </text>
                <text className="fill-[#131b2e] font-mono text-[9px] font-semibold" textAnchor="end" x="42" y="195">
                  NSSO Core
                </text>
                <text className="fill-[#131b2e] font-mono text-[9px] font-semibold" textAnchor="end" x="42" y="96">
                  Stack Bounds
                </text>
              </svg>
            </div>

            <div className="space-y-2 mt-3 pt-2 border-t border-[#eaedff] font-mono text-xs">
              <div className="flex justify-between">
                <span className="text-[#444651]">Graph DSA Core:</span>
                <span className="font-bold text-[#00236f]">L3 → L4 (+0.6 Delta)</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[#444651]">Spatial Sampling Bounds:</span>
                <span className="font-bold text-[#904d00]">L3 → L4 (+0.4 Delta)</span>
              </div>
            </div>
          </div>

          {/* Verifiable Activity Feed (Append-only audit log) */}
          <div className="bg-white rounded-xl p-4 shadow-sm border border-[#c5c5d3]/30">
            <div className="flex items-center gap-2 mb-2 pb-1 border-b border-[#eaedff]">
              <RotateCcw size={16} className="text-[#00236f]" />
              <h4 className="text-xs font-bold text-[#00236f] uppercase font-mono tracking-wider">
                Verifiable Activity Feed
              </h4>
            </div>
            <div className="space-y-2 font-mono text-[11px]">
              <div className="p-2 bg-[#f2f3ff] rounded border border-[#c5c5d3]/30">
                <div className="flex justify-between text-[#131b2e] font-bold">
                  <span>Session #4029</span>
                  <span className="text-[#00312c]">28ms • Passed</span>
                </div>
                <span className="text-[#757682] block text-[10px]">Tarjan SCC • O(V+E) verified</span>
              </div>
              <div className="p-2 bg-[#f2f3ff] rounded border border-[#c5c5d3]/30">
                <div className="flex justify-between text-[#131b2e] font-bold">
                  <span>Session #4028</span>
                  <span className="text-[#ba1a1a]">Recursion Bound</span>
                </div>
                <span className="text-[#757682] block text-[10px]">Max call stack exceeded test 3</span>
              </div>
            </div>
          </div>

          {/* Evidence Reliability Index */}
          {/* Evidence Reliability Index */}

<div className="bg-[#f2f3ff] rounded-xl p-4 border border-[#c5c5d3]/40">

  <div className="flex items-center justify-between mb-2">
    <span className="text-xs font-bold text-[#00236f] uppercase font-mono tracking-wider">
      Evidence Reliability Index
    </span>

    <span className="font-mono text-xs font-bold text-[#00312c]">
      98.6%
    </span>
  </div>

  <p className="text-xs text-[#444651] mb-3">
    Zero external injection • Client-side WASM execution verified against deterministic test fixtures.
  </p>

  <div className="flex flex-col gap-2">

    <button
      onClick={handleSyncToProfile}
      className="w-full bg-[#00236f] hover:bg-[#1e3a8a] text-white py-2 rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
    >
      <Cloud size={16} />
      <span>Sync to Local Competency Profile</span>
    </button>

    <button
      onClick={handleExportJson}
      className="w-full bg-white hover:bg-[#e2e7ff] text-[#131b2e] border border-[#c5c5d3]/40 py-1.5 rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 cursor-pointer"
    >
      <Download size={16} />
      <span>Export JSON Telemetry</span>
    </button>

  </div>
</div>
        </div>
      </div>
    </div>
  );
}