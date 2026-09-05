'use client';
import React, { useState } from 'react';
import { FileText, SquareLibrary } from 'lucide-react';


export default function SourceQuizGenerator({ onNavigate, onOpenModal }) {
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [selectedOption, setSelectedOption] = useState('B');
  const [hasSubmitted, setHasSubmitted] = useState(false);
  const [quizToast, setQuizToast] = useState('');
  const [isResynthesizing, setIsResynthesizing] = useState(false);

  const questions = [
    {
      id: 1,
      number: '01 of 02',
      dimension: 'Sampling Methodology (PPSWOR)',
      cadre: 'SSO / Band 4',
      prompt: 'Under the Multi-Stage Stratified Sampling Framework defined in NSO Technical Circular 2023-Q4, what is the required protocol when a sample village sub-round exhibits attrition exceeding 8.5% due to seasonal migration?',
      options: [
        {
          id: 'A',
          text: 'Substitute the depleted primary sampling unit (PSU) with the geographically nearest reserve frame village without weight alteration.',
          isCorrect: false,
          overlap: '0.412'
        },
        {
          id: 'B',
          text: 'Apply post-stratification re-weighting factors based on auxiliary population projections from the latest RGI Census estimates.',
          isCorrect: true,
          overlap: '0.942'
        },
        {
          id: 'C',
          text: 'Truncate the sub-round dataset and compute missing variance estimators using simple random replacement without stratum re-balancing.',
          isCorrect: false,
          overlap: '0.380'
        },
        {
          id: 'D',
          text: 'Defer publication until the subsequent bi-annual survey wave and mark the stratum as non-responsive in final gazette tables.',
          isCorrect: false,
          overlap: '0.295'
        }
      ],
      citation: {
        anchor: 'NSO Framework Gazette Sec 4.2 (p. 18)',
        cosine: '0.942',
        quote: 'When attrition in rural sample sub-rounds exceeds 8.5%, survey supervisors must execute post-stratification re-weighting factors derived from Registrar General of India (RGI) district-level auxiliary projections rather than substituting replacement PSUs, which introduces systemic selection bias.',
        chunkId: 'NSO-7729-CHK3',
        page: 18
      }
    },
    {
      id: 2,
      number: '02 of 02',
      dimension: 'PySpark GovCloud Partitioning',
      cadre: 'SSO / Band 4',
      prompt: 'In large-scale ASI microdata extraction pipelines running on GovCloud clusters, which partitioning strategy is recommended to avoid shuffle spill during multi-stage stratum joins?',
      options: [
        {
          id: 'A',
          text: 'Default hash partitioning using monotonically increasing row IDs without salting.',
          isCorrect: false,
          overlap: '0.340'
        },
        {
          id: 'B',
          text: 'Range partitioning on composite (State_Code, Sector_NIC_2Digit) with pre-salted skew keys for high-density enterprise clusters.',
          isCorrect: true,
          overlap: '0.958'
        },
        {
          id: 'C',
          text: 'Broadcasting entire multi-terabyte factory transaction tables to every worker executor node.',
          isCorrect: false,
          overlap: '0.220'
        },
        {
          id: 'D',
          text: 'Persisting raw uncompressed JSON directly into driver heap memory before running join operators.',
          isCorrect: false,
          overlap: '0.190'
        }
      ],
      citation: {
        anchor: 'NIC GovCloud Big Data Manual v3 (p. 47)',
        cosine: '0.958',
        quote: 'For industrial surveys exceeding 10M records, join operations across heterogeneous survey tables must enforce range partitioning on compound geography/industry strata with pre-salted surrogate keys to prevent shuffle memory spill over executor nodes.',
        chunkId: 'NIC-BIGDATA-991',
        page: 47
      }
    }
  ];

  const currentQ = questions[currentQuestionIndex];

  const handleSubmit = () => {
    setHasSubmitted(true);
    setQuizToast('Evidence committed to Officer Ledger: +14.4% Competency Gain on Rural Survey Weighting verified!');
    setTimeout(() => {
      setQuizToast('');
    }, 5000);
  };

  const handleNextQuestion = () => {
    setHasSubmitted(false);
    setSelectedOption('B');
    setCurrentQuestionIndex((prev) => (prev + 1) % questions.length);
  };

  const handleResynthesize = () => {
    setIsResynthesizing(true);
    setQuizToast('Re-indexing vector embeddings against MoSPI 2023-24 Gazettes...');
    setTimeout(() => {
      setIsResynthesizing(false);
      setQuizToast('Vector space re-calibrated: 18 Statistical Vectors verified with 100% Grounding Lock.');
      setTimeout(() => setQuizToast(''), 4000);
    }, 900);
  };

  return (
    <div className="flex flex-col w-full">
      {/* Algorithmic Provenance Suite Top Banner */}
      <div className="flex flex-col gap-3 mb-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-[#e2e7ff] p-3.5 rounded-xl border border-[#b6c4ff]/50">
          <div className="flex items-center gap-2.5">
            <SquareLibrary size={30} />
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold text-[#00236f]">Algorithmic Provenance Suite</h1>
                <span className="font-mono text-[10px] px-2 py-0.5 rounded bg-[#00236f] text-white font-bold">
                  NSO-REV2.4.9
                </span>
              </div>
              <p className="text-xs text-[#444651]">
                Diagnostic generation bounded strictly to verified ministry circulars, data manuals, and statistical gazettes. Zero speculative generation.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <span className="font-mono text-xs px-2.5 py-1 rounded bg-white text-[#00312c] font-semibold border border-[#c5c5d3]/30 flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-[#00312c]"></span> Grounding Lock: Active (100% Citation Matched)
            </span>
            <button
              onClick={handleResynthesize}
              disabled={isResynthesizing}
              className="bg-[#00236f] hover:bg-[#1e3a8a] text-white px-3 py-1 rounded text-xs font-semibold transition-colors flex items-center gap-1 cursor-pointer"
            >
              <span className={`material-symbols-outlined text-[16px] ${isResynthesizing ? 'animate-spin' : ''}`}>
                sync
              </span>
              <span>{isResynthesizing ? 'Re-indexing...' : 'Re-Synthesize'}</span>
            </button>
          </div>
        </div>

        {quizToast && (
          <div className="px-4 py-2.5 bg-[#dce1ff] text-[#00164e] rounded-lg text-xs font-mono flex items-center gap-2 border border-[#b6c4ff] shadow-sm animate-in fade-in duration-200">
            <span className="material-symbols-outlined text-[18px] text-[#00236f]">verified</span>
            <span>{quizToast}</span>
          </div>
        )}

        {/* Ingested Document Anchor Card */}
        <div className="bg-white rounded-xl p-4 shadow-sm border border-[#c5c5d3]/30 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[#ffdcc3] text-[#2f1500] flex items-center justify-center font-bold shrink-0">
              <FileText size={20} />
            </div>
            <div>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="font-mono text-[10px] text-[#757682] uppercase font-bold">Ingested Statistical Source</span>
                <span className="text-xs px-2 py-0.5 bg-[#f2f3ff] text-[#00236f] rounded font-mono font-bold">
                  14.8 MB • Chunked &amp; Vectorized
                </span>
              </div>
              <h3 className="text-sm sm:text-base font-bold text-[#131b2e]">
                MoSPI_Annual_Report_2023_24_Data_Standards.pdf
              </h3>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-xs px-2 py-1 rounded bg-[#f2f3ff] text-[#444651]">
              42 Pages Parsed
            </span>
            <span className="font-mono text-xs px-2 py-1 rounded bg-[#f2f3ff] text-[#444651]">
              18 Statistical Vectors
            </span>
            <button
              onClick={() => onOpenModal('pdf_viewer')}
              className="bg-[#f2f3ff] hover:bg-[#e2e7ff] text-[#00236f] px-3 py-1 rounded text-xs font-semibold transition-colors flex items-center gap-1 border border-[#c5c5d3]/30 cursor-pointer"
            >
              <span className="material-symbols-outlined text-[16px]">pageview</span> View Source Bounding Boxes
            </button>
          </div>
        </div>
      </div>

      {/* Main Grid: Quiz Diagnostic Flow (8 cols) + Real-time Competency Evaluation (4 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 mb-6 items-start">
        {/* Left Column: Interactive Grounded Question Card */}
        <div className="lg:col-span-8 flex flex-col gap-4">
          <div className="bg-white rounded-xl p-5 shadow-sm border border-[#c5c5d3]/30 relative">
            <div className="flex items-center justify-between pb-3 border-b border-[#eaedff] mb-4">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs font-bold px-2.5 py-0.5 rounded bg-[#00236f] text-white">
                  QUESTION {currentQ.number}
                </span>
                <span className="font-mono text-xs text-[#757682]">
                  Dimension: <span className="font-bold text-[#131b2e]">{currentQ.dimension}</span>
                </span>
              </div>
              <span className="font-mono text-xs px-2 py-0.5 rounded bg-[#f2f3ff] text-[#444651]">
                Cadre: {currentQ.cadre}
              </span>
            </div>

            <div className="mb-5">
              <h2 className="text-base sm:text-lg font-bold text-[#131b2e] leading-snug mb-4">
                {currentQ.prompt}
              </h2>

              {/* Options */}
              <div className="space-y-2.5">
                {currentQ.options.map((opt) => {
                  const isChecked = selectedOption === opt.id;
                  let cardStyle = 'border-[#c5c5d3]/30 hover:border-[#c5c5d3] bg-white';
                  if (isChecked) {
                    cardStyle = 'border-[#00236f] ring-1 ring-[#00236f]/30 bg-[#f2f3ff]/40';
                  }
                  if (hasSubmitted) {
                    if (opt.isCorrect) {
                      cardStyle = 'border-[#00312c] bg-[#89f5e7]/20 ring-1 ring-[#00312c]';
                    } else if (isChecked && !opt.isCorrect) {
                      cardStyle = 'border-[#ba1a1a] bg-[#ffdad6]/30';
                    }
                  }

                  return (
                    <label
                      key={opt.id}
                      onClick={() => !hasSubmitted && setSelectedOption(opt.id)}
                      className={`flex items-start gap-3 p-3.5 rounded-lg border transition-all cursor-pointer ${cardStyle}`}
                    >
                      <input
                        type="radio"
                        name="quiz-option"
                        value={opt.id}
                        checked={isChecked}
                        onChange={() => {}}
                        className="mt-1 accent-[#00236f]"
                      />
                      <div className="flex-1">
                        <span className="text-xs sm:text-sm text-[#131b2e] font-medium leading-relaxed block">
                          <span className="font-mono font-bold mr-1.5 text-[#00236f]">[{opt.id}]</span>
                          {opt.text}
                        </span>
                        {hasSubmitted && opt.isCorrect && (
                          <span className="inline-flex items-center gap-1 font-mono text-[11px] text-[#00312c] font-bold mt-1">
                            <span className="material-symbols-outlined text-[14px]">check_circle</span> Grounded Correct Answer (Cosine: {opt.overlap})
                          </span>
                        )}
                      </div>
                    </label>
                  );
                })}
              </div>
            </div>

            {/* Grounding Citation Ledger (Source Anchor) */}
            <div className="bg-[#f2f3ff] rounded-xl p-4 border border-[#c5c5d3]/40 mb-5">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-1.5">
                  <span className="material-symbols-outlined text-[#00236f] text-[18px]">verified</span>
                  <span className="font-mono text-xs font-bold text-[#00236f]">
                    Grounded Source Anchor: {currentQ.citation.anchor}
                  </span>
                </div>
                <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-white text-[#757682] border border-[#c5c5d3]/30">
                  Vector Overlap: <span className="text-[#00236f] font-bold">{currentQ.citation.cosine} Cosine Sim</span>
                </span>
              </div>

              <blockquote className="text-xs text-[#131b2e] italic border-l-2 border-[#00236f] pl-3 py-1 bg-white/80 rounded-r my-2 font-mono">
                "{currentQ.citation.quote}"
              </blockquote>

              <div className="flex items-center justify-between text-[11px] font-mono text-[#757682] pt-1">
                <span>Extracted Chunk: {currentQ.citation.chunkId} • Model: text-embedding-gecko</span>
                <button
                  onClick={() => onOpenModal('pdf_viewer')}
                  className="text-[#00236f] font-semibold hover:underline flex items-center gap-0.5 cursor-pointer"
                >
                  <span>Open PDF viewer at page {currentQ.citation.page}</span>
                  <span className="material-symbols-outlined text-[14px]">launch</span>
                </button>
              </div>
            </div>

            {/* Actions Toolbar */}
            <div className="flex flex-col sm:flex-row items-center justify-between gap-3 pt-3 border-t border-[#eaedff]">
              <div className="flex items-center gap-2">
                <button
                  onClick={handleNextQuestion}
                  className="px-3 py-1.5 rounded text-xs font-semibold text-[#444651] hover:bg-[#f2f3ff] transition-colors border border-[#c5c5d3]/30 cursor-pointer"
                >
                  Skip Question
                </button>
                <button
                  onClick={() => {
                    setQuizToast('Question #01 flagged for Cadre Review Board (CSO-HQ).');
                    setTimeout(() => setQuizToast(''), 3000);
                  }}
                  className="px-3 py-1.5 rounded text-xs font-semibold text-[#904d00] hover:bg-[#ffdcc3]/30 transition-colors flex items-center gap-1 cursor-pointer"
                >
                  <span className="material-symbols-outlined text-[15px]">flag</span> Flag for Human Supervisor
                </button>
              </div>

              <div className="flex items-center gap-2">
                {hasSubmitted ? (
                  <button
                    onClick={handleNextQuestion}
                    className="bg-[#00236f] hover:bg-[#1e3a8a] text-white px-4 py-2 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 cursor-pointer"
                  >
                    <span>Next Question</span>
                    <span className="material-symbols-outlined text-[16px]">arrow_forward</span>
                  </button>
                ) : (
                  <button
                    onClick={handleSubmit}
                    className="bg-[#00236f] hover:bg-[#1e3a8a] text-white px-4 py-2 rounded-lg text-xs font-semibold transition-colors flex items-center gap-1.5 shadow-sm cursor-pointer"
                  >
                    <span className="material-symbols-outlined text-[16px]">check</span>
                    <span>Submit Diagnostic &amp; Commit Evidence</span>
                  </button>
                )}
              </div>
            </div>
          </div>

          {/* Dual Info Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="bg-white rounded-xl p-4 shadow-sm border border-[#c5c5d3]/30">
              <div className="flex items-center gap-2 text-[#00236f] font-bold text-xs mb-1">
                <span className="material-symbols-outlined text-[18px]">verified_user</span>
                <span>Zero-Hallucination Protocol</span>
              </div>
              <p className="text-xs text-[#444651]">
                Every question is paired with a strict bounding citation from verified internal documentation. No ungrounded LLM completions are accepted by Cadre Cell.
              </p>
            </div>
            <div className="bg-white rounded-xl p-4 shadow-sm border border-[#c5c5d3]/30">
              <div className="flex items-center gap-2 text-[#00312c] font-bold text-xs mb-1">
                <span className="material-symbols-outlined text-[18px]">sync_alt</span>
                <span>iGOT Dual-Sync Ready</span>
              </div>
              <p className="text-xs text-[#444651]">
                Diagnostic results map directly into the iGOT Karmayogi Sovereign Competency Framework (L1 through L5) for automatic Cadre band progression.
              </p>
            </div>
          </div>
        </div>

        {/* Right Column: Live Competency Impact & Continuous Evaluation Ledger */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          {/* Target Officer Profile Card */}
          <div className="bg-white rounded-xl p-4 shadow-sm border border-[#c5c5d3]/30">
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-[#eaedff]">
              <div>
                <span className="font-mono text-[10px] text-[#757682] uppercase font-bold">Target Officer</span>
                <h4 className="text-sm font-bold text-[#00236f]">rajesh.sharma (Band 4)</h4>
              </div>
              <span className="font-mono text-[11px] px-2 py-0.5 rounded bg-[#ffdcc3] text-[#2f1500] font-bold">
                SSO Cadre
              </span>
            </div>

            <div className="space-y-2.5">
              <div>
                <div className="flex justify-between text-xs font-mono mb-1">
                  <span className="text-[#444651]">Rural Survey Weighting</span>
                  <span className="font-bold text-[#00236f]">
                    {hasSubmitted ? '86.8% (+14.4%)' : '72.4%'}
                  </span>
                </div>
                <div className="w-full bg-[#eaedff] h-1.5 rounded-full overflow-hidden">
                  <div
                    className="bg-[#00236f] h-full rounded-full transition-all duration-500"
                    style={{ width: hasSubmitted ? '86.8%' : '72.4%' }}
                  ></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-mono mb-1">
                  <span className="text-[#444651]">X-13ARIMA Econometrics</span>
                  <span className="font-bold text-[#904d00]">
                    {hasSubmitted ? '79.5% (+21.5%)' : '58.0%'}
                  </span>
                </div>
                <div className="w-full bg-[#eaedff] h-1.5 rounded-full overflow-hidden">
                  <div
                    className="bg-[#fe932c] h-full rounded-full transition-all duration-500"
                    style={{ width: hasSubmitted ? '79.5%' : '58.0%' }}
                  ></div>
                </div>
              </div>

              <div>
                <div className="flex justify-between text-xs font-mono mb-1">
                  <span className="text-[#444651]">Citation &amp; Standard Adherence</span>
                  <span className="font-bold text-[#00312c]">99.2% OPTIMAL</span>
                </div>
                <div className="w-full bg-[#eaedff] h-1.5 rounded-full overflow-hidden">
                  <div className="bg-[#00312c] h-full rounded-full" style={{ width: '99.2%' }}></div>
                </div>
              </div>
            </div>

            <div className="mt-4 pt-3 border-t border-[#eaedff] flex items-center justify-between font-mono text-xs">
              <span className="text-[#757682]">Cadre Band 5 Eligibility:</span>
              <span className="font-bold text-[#00236f]">{hasSubmitted ? '88.5%' : '84.0%'}</span>
            </div>
          </div>

          {/* Continuous Evaluation Ledger Card */}
          <div className="bg-[#f2f3ff] rounded-xl p-4 border border-[#c5c5d3]/40">
            <div className="flex items-center gap-2 mb-2">
              <span className="material-symbols-outlined text-[#00236f] text-[18px]">receipt_long</span>
              <h4 className="text-xs font-bold text-[#00236f] uppercase font-mono tracking-wider">
                Continuous Evaluation Ledger
              </h4>
            </div>
            <div className="space-y-1.5 font-mono text-xs text-[#444651] mb-3">
              <div className="flex justify-between">
                <span>Traceability Hash:</span>
                <span className="font-semibold text-[#131b2e]">#NSO-EVAL-88219-B4</span>
              </div>
              <div className="flex justify-between">
                <span>Confidence Calibration:</span>
                <span className="text-[#00312c] font-bold">99.8% (Deterministic)</span>
              </div>
              <div className="flex justify-between">
                <span>DSA Quest Link:</span>
                <span className="text-[#904d00] font-bold">Queued for Practice</span>
              </div>
              <div className="flex justify-between">
                <span>Audit State:</span>
                <span className="text-[#00236f] font-bold">Ready to Commit</span>
              </div>
            </div>
            <button
              onClick={() => onNavigate('adaptive-practice-dsa-quest')}
              className="w-full bg-white hover:bg-[#e2e7ff] text-[#00236f] border border-[#c5c5d3]/40 py-2 rounded-lg text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 shadow-xs cursor-pointer"
            >
              <span>Practice in DSA Quest</span>
              <span className="material-symbols-outlined text-[16px]">sports_esports</span>
            </button>
          </div>

          {/* Supervisor Feedback Banner */}
          <div className="bg-white rounded-xl p-4 shadow-sm border border-[#c5c5d3]/30">
            <div className="flex items-center gap-2 mb-1.5 text-xs font-bold text-[#131b2e]">
              <span className="material-symbols-outlined text-[#904d00] text-[18px]">psychology</span>
              <span>Cadre Cell Continuous Loop</span>
            </div>
            <p className="text-xs text-[#757682]">
              Quiz answers reinforce the probabilistic Bayesian belief network updating the officer's competency profile without requiring subjective self-appraisal submissions.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
