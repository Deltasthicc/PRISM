'use client';

import React, { useEffect, useState } from 'react';

import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  BookOpen,
  CheckCircle,
  ChevronRight,
  ClipboardCheck,
  Info,
  LayoutDashboard,
  Lightbulb,
  Network,
  Radar,
  Timer,
} from 'lucide-react';

export default function CompetencyQuizPage({
  officerProfile,
  onCompleteQuizAndLaunchDashboard,
  onBackToProfile,
  onBackToLogin,
}) {
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState({});
  const [showExplanation, setShowExplanation] = useState(false);
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [timeRemaining, setTimeRemaining] = useState(600);
  const [isTimerRunning, setIsTimerRunning] = useState(true);

  // ============================================================
  // TIMER
  // ============================================================

  useEffect(() => {
    if (!isTimerRunning || isSubmitted) return;

    const interval = setInterval(() => {
      setTimeRemaining((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);

    return () => clearInterval(interval);
  }, [isTimerRunning, isSubmitted]);

  const formatTime = (seconds) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;

    return `${mins.toString().padStart(2, '0')}:${secs
      .toString()
      .padStart(2, '0')}`;
  };

  // ============================================================
  // QUESTIONS
  // ============================================================

  const questions = [
    {
      id: 1,
      dimension: 'NSSO Sampling & Survey Methodology',
      dimensionKey: 'sampling',
      code: 'NSSTA-STAT-701',
      question:
        'In a multi-stage stratified sample survey (such as the Periodic Labour Force Survey - PLFS), if sample attrition in rural sub-rounds exceeds 8.5%, what is the statistically compliant protocol under MoSPI survey guidelines?',
      citation:
        'MoSPI Annual Report 2023-24 §4.2 / NSSTA Manual on Survey Errors',
      options: [
        {
          id: 'A',
          text:
            'Substitute non-responding households with convenient replacement Primary Sampling Units (PSUs) in adjacent enumeration blocks.',
        },
        {
          id: 'B',
          text:
            'Apply post-stratification re-weighting using Registrar General of India (RGI) district-level auxiliary projections to mitigate selection bias.',
        },
        {
          id: 'C',
          text:
            'Drop the entire sub-round from national GDP aggregation and impute all household expenditure values using simple mean imputation.',
        },
        {
          id: 'D',
          text:
            'Re-run the survey without finite population correction (FPC) and report only unweighted sampling medians.',
        },
      ],
      correctAnswer: 'B',
      explanation:
        'Official gazette standards mandate that PSU substitution introduces severe selection bias. Instead, post-stratification re-weighting factors derived from Registrar General of India (RGI) district-level projections must be applied to preserve unbiased estimators.',
    },

    {
      id: 2,
      dimension: 'Large-Scale Data Wrangling & PySpark',
      dimensionKey: 'sql',
      code: 'CSO-DATA-402',
      question:
        'When executing a distributed join on 50 million Annual Survey of Industries (ASI) records in PySpark, executor nodes crash with `OutOfMemory: Java Heap Space` due to high partition skew on district codes. What is the optimal distributed execution strategy?',
      citation: 'GovCloud Cluster Infrastructure Guidelines v3.1',
      options: [
        {
          id: 'A',
          text:
            'Increase `spark.driver.memory` to 128GB while leaving executor memory unchanged and disabling adaptive query execution.',
        },
        {
          id: 'B',
          text:
            'Broadcast the large 50M records dataframe across all worker nodes to eliminate data shuffling.',
        },
        {
          id: 'C',
          text:
            'Enable Adaptive Query Execution (AQE) with skew join optimization (`spark.sql.adaptive.skewJoin.enabled=true`) and salt the skewed join keys.',
        },
        {
          id: 'D',
          text:
            'Export all records into a single CSV file and process them sequentially on a single core.',
        },
      ],
      correctAnswer: 'C',
      explanation:
        'High key skew cannot be resolved by driver memory or broadcasting 50M records (which causes broadcast OOM). Enabling Spark AQE skew join splitting and salting the skewed keys uniformly redistributes partition weight across executor heaps.',
    },

    {
      id: 3,
      dimension: 'Econometric & Time-Series Forecasting',
      dimensionKey: 'econo',
      code: 'NAD-TS-505',
      question:
        'When updating Consumer Price Index (CPI) and Index of Industrial Production (IIP) series during a decennial base-year revision, which method is recommended by MoSPI to link old and new index numbers without introducing artificial structural jumps?',
      citation: 'National Accounts Statistics: Sources and Methods (MoSPI NAD)',
      options: [
        {
          id: 'A',
          text:
            'Splicing using linking factors calculated from the overlapping period of both series (ratio method at common base periods).',
        },
        {
          id: 'B',
          text:
            'Arbitrarily scaling all pre-revision historical values by the latest wholesale inflation index.',
        },
        {
          id: 'C',
          text:
            'Completely discarding all pre-revision time-series data to avoid comparison discrepancies.',
        },
        {
          id: 'D',
          text:
            'Unweighted linear regression against international crude oil benchmarks.',
        },
      ],
      correctAnswer: 'A',
      explanation:
        'Standard National Accounts practice dictates that splicing through linking factors derived from the overlapping period of old and revised series guarantees seamless long-term continuity without creating artificial statistical discontinuity.',
    },

    {
      id: 4,
      dimension: 'DPDP Act 2023 & Sovereign Cloud Governance',
      dimensionKey: 'cloud',
      code: 'DPDP-SOV-101',
      question:
        'Under Section 8 of the Digital Personal Data Protection (DPDP) Act 2023 and National Data Sharing & Accessibility Policy (NDSAP), what technical measure is mandatory before releasing anonymized microdata containing granular geo-spatial and household demographics?',
      citation:
        'Digital Personal Data Protection Act 2023 (Gazette of India, Act No. 22 of 2023)',
      options: [
        {
          id: 'A',
          text:
            'Hashing only the Aadhaar number while retaining direct phone numbers and exact GPS coordinates intact.',
        },
        {
          id: 'B',
          text:
            'Enforcing k-anonymity (k ≥ 5) and l-diversity on quasi-identifiers, plus spatial aggregation to district/tehsil centroids to prevent re-identification.',
        },
        {
          id: 'C',
          text:
            'Publishing raw tables in open CSV format with a disclaimer asking citizens not to de-anonymize individuals.',
        },
        {
          id: 'D',
          text:
            'Restricting dataset downloads to users with personal social media accounts.',
        },
      ],
      correctAnswer: 'B',
      explanation:
        'DPDP 2023 and sovereign data governance require strict mathematical anonymization: quasi-identifiers must pass k-anonymity (k ≥ 5) and l-diversity, paired with spatial fuzzing to centroids to neutralize auxiliary linkage attacks.',
    },

    {
      id: 5,
      dimension: 'Distributed Machine Learning & Imputation',
      dimensionKey: 'dml',
      code: 'ML-IMP-603',
      question:
        'When imputing missing financial variables in the Annual Survey of Industries (ASI) microdata where missingness is Missing at Random (MAR), which machine learning approach best preserves multivariate covariance structures without deflating standard errors?',
      citation: 'CSO Big Data & ML Research Working Paper 2023-09',
      options: [
        {
          id: 'A',
          text:
            'Unconditional Mean Imputation substituting missing values with the state-level column arithmetic mean.',
        },
        {
          id: 'B',
          text:
            'Single deterministic regression imputation without adding stochastic residual error terms.',
        },
        {
          id: 'C',
          text:
            'Multiple Imputation by Chained Equations (MICE) or Random Forest-based MissForest with stochastic variance preservation.',
        },
        {
          id: 'D',
          text:
            'Deleting all enterprise records that contain any missing field.',
        },
      ],
      correctAnswer: 'C',
      explanation:
        'Mean or single deterministic imputation severely artificially shrinks variance and distorts covariance structures. Multiple Imputation by Chained Equations (MICE) or MissForest models uncertainty and retains true population variance.',
    },

    {
      id: 6,
      dimension: 'Algorithms & Graph Theory (DSA Core)',
      dimensionKey: 'dsa',
      code: 'DSA-GRAPH-301',
      question:
        'In national accounts inter-industry Supply and Use Tables (SUT), resolving circular supply chain dependencies to generate an admissible production sequence mathematically maps to which graph algorithm?',
      citation:
        'MoSPI Analytical Workbench: DAG Topological Sort & SCC Algorithms',
      options: [
        {
          id: 'A',
          text:
            'Kahn’s Algorithm for Topological Sorting on Directed Acyclic Graphs (DAG), coupled with Tarjan’s SCC algorithm to detect circular supply feedback loops.',
        },
        {
          id: 'B',
          text:
            'Dijkstra’s Single-Source Shortest Path algorithm on undirected trees.',
        },
        {
          id: 'C',
          text:
            'Kruskal’s Minimum Spanning Tree algorithm for unweighted networks.',
        },
        {
          id: 'D',
          text:
            'Breadth-First Search (BFS) for binary search trees.',
        },
      ],
      correctAnswer: 'A',
      explanation:
        'Economic flow pipelines model industry inputs and outputs as directed graphs. Kahn’s Topological Sort computes the valid execution schedule, while Tarjan’s Strongly Connected Components (SCC) algorithm isolates circular cyclic dependency loops.',
    },
  ];

  // ============================================================
  // QUIZ STATE
  // ============================================================

  const currentQ = questions[currentQuestionIndex];

  const answeredCount = Object.keys(selectedAnswers).length;

  const progressPercent = Math.round(
    (answeredCount / questions.length) * 100
  );

  // ============================================================
  // SELECT ANSWER
  // ============================================================

  const handleSelectOption = (optionId) => {
    if (isSubmitted) return;

    setSelectedAnswers({
      ...selectedAnswers,
      [currentQ.id]: optionId,
    });
  };

  // ============================================================
  // NEXT
  // ============================================================

  const handleNext = () => {
    setShowExplanation(false);

    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex(currentQuestionIndex + 1);
    }
  };

  // ============================================================
  // PREVIOUS
  // ============================================================

  const handlePrev = () => {
    setShowExplanation(false);

    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex(currentQuestionIndex - 1);
    }
  };

  // ============================================================
  // SUBMIT
  // ============================================================

  const handleSubmitQuiz = () => {
    setIsSubmitted(true);
    setIsTimerRunning(false);
  };

  // ============================================================
  // RESULTS
  // ============================================================

  const calculateResults = () => {
    let correct = 0;
    const dimensionScores = {};

    questions.forEach((q) => {
      const isCorrect = selectedAnswers[q.id] === q.correctAnswer;

      if (isCorrect) {
        correct += 1;
      }

      dimensionScores[q.dimensionKey] = {
        name: q.dimension,
        isCorrect,
        level: isCorrect ? 4 : 2,
        target: 4,
      };
    });

    const scorePercentage = Math.round(
      (correct / questions.length) * 100
    );

    return {
      total: questions.length,
      correct,
      scorePercentage,
      dimensionScores,
      congruence: Math.min(95, Math.max(45, scorePercentage)),
    };
  };

  const results = isSubmitted ? calculateResults() : null;

  // ============================================================
  // FINISH QUIZ
  // ============================================================

  const handleFinishAndLaunchDashboard = () => {
    if (!results) return;

    onCompleteQuizAndLaunchDashboard({
      ...officerProfile,
      quizResults: {
        score: results.correct,
        total: results.total,
        percentage: results.scorePercentage,
        congruence: results.congruence,
        dimensionLevels: results.dimensionScores,
        testedAt: new Date().toISOString(),
      },
    });
  };

  // ============================================================
  // UI
  // ============================================================

  return (
    <div className="min-h-screen w-full bg-[#f7f8fc] px-3 sm:px-5 py-5 sm:py-8">
      <div className="w-full max-w-6xl mx-auto">

        {/* ======================================================
            TOP IDENTITY BAR
        ====================================================== */}

        <div className="bg-white rounded-2xl border border-[#dfe2eb] shadow-[0_4px_20px_rgba(0,35,111,0.05)] overflow-hidden mb-5">

          <div className="h-1 bg-[#00236f]" />

          <div className="p-4 sm:p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">

            <div className="flex items-center gap-3 min-w-0">

              <div className="w-11 h-11 rounded-xl bg-[#00236f] text-white flex items-center justify-center font-bold text-sm font-mono shrink-0 shadow-sm">
                {officerProfile?.avatarInitials || 'RS'}
              </div>

              <div className="min-w-0">

                <div className="flex items-center gap-2 flex-wrap">

                  <span className="font-bold text-sm text-[#10182b]">
                    {officerProfile?.name || 'Dr. Rajesh Sharma'}
                  </span>

                  <span className="px-2 py-1 rounded-md bg-[#eef1ff] text-[#00236f] font-mono text-[10px] font-bold">
                    {officerProfile?.designation || 'Assistant Director'}
                  </span>

                </div>

                <p className="text-[11px] text-[#6b7280] mt-1 truncate">
                  {officerProfile?.division ||
                    'CSO Analytics & National Accounts'}{' '}
                  <span className="mx-1">•</span>{' '}
                  {officerProfile?.cadre || 'Cadre Band 3'}
                </p>

                <p className="text-[10px] text-[#8a8f9d] font-mono mt-0.5">
                  {officerProfile?.cadreId || 'IND-88219'}
                </p>

              </div>
            </div>

            {/* TIMER */}

            <div className="flex items-center gap-2 self-end sm:self-auto">

              <div
                className={`flex items-center gap-2 px-3.5 py-2 rounded-xl border font-mono ${
                  timeRemaining <= 60
                    ? 'bg-red-50 border-red-200 text-red-700'
                    : 'bg-[#f5f6fb] border-[#dfe2eb] text-[#172033]'
                }`}
              >
                <Timer
                  size={17}
                  strokeWidth={2.2}
                  className={
                    timeRemaining <= 60
                      ? 'text-red-600'
                      : 'text-[#904d00]'
                  }
                />

                <span className="font-bold tracking-wide">
                  {formatTime(timeRemaining)}
                </span>
              </div>

              <span className="hidden sm:inline-flex px-3 py-2 rounded-xl bg-[#fff2e9] text-[#904d00] font-bold text-[10px] font-mono border border-[#ffd2b5]">
                PROCTORED
              </span>

            </div>

          </div>
        </div>

        {/* ======================================================
            QUIZ HEADER
        ====================================================== */}

        {!isSubmitted && (
          <div className="mb-5">

            <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-3">

              <div>
                <p className="text-[10px] font-mono font-bold uppercase tracking-[0.15em] text-[#904d00] mb-1">
                  Baseline Diagnostic
                </p>

                <h1 className="text-xl sm:text-2xl font-bold text-[#10182b] tracking-tight">
                  Competency Assessment
                </h1>

                <p className="text-xs text-[#727887] mt-1">
                  Evaluate your current competency vector across six
                  core dimensions.
                </p>
              </div>

              <div className="flex items-center gap-2 text-[10px] font-mono text-[#747a88]">
                <span className="w-2 h-2 rounded-full bg-[#005147]" />
                Assessment active
              </div>

            </div>

          </div>
        )}

        {/* ======================================================
            QUIZ
        ====================================================== */}

        {!isSubmitted ? (

          <div className="w-full grid grid-cols-1 lg:grid-cols-12 gap-5">

            {/* ==================================================
                QUESTION CARD
            ================================================== */}

            <div className="lg:col-span-8 bg-white border border-[#dfe2eb] rounded-2xl shadow-[0_6px_25px_rgba(0,35,111,0.05)] overflow-hidden">

              {/* Question top accent */}

              <div className="h-1 bg-gradient-to-r from-[#00236f] via-[#3657a7] to-[#ff9b55]" />

              <div className="p-5 sm:p-7">

                {/* Question Header */}

                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#edf0f5]">

                  <div className="flex items-center gap-2 flex-wrap">

                    <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#00236f] text-white font-mono text-[11px] font-bold">
                      Q{currentQuestionIndex + 1}
                      <ChevronRight size={12} />
                      {questions.length}
                    </span>

                    <span className="px-2.5 py-1 rounded-lg bg-[#fff1e7] text-[#904d00] font-mono text-[10px] font-bold">
                      {currentQ.dimension}
                    </span>

                  </div>

                  <span className="font-mono text-[10px] text-[#8a8f9d]">
                    {currentQ.code}
                  </span>

                </div>

                {/* Question */}

                <div className="py-6">

                  <div className="flex items-start gap-3 mb-3">

                    <div className="mt-0.5 w-7 h-7 rounded-lg bg-[#eef1ff] text-[#00236f] flex items-center justify-center shrink-0">
                      <span className="font-mono text-[10px] font-bold">
                        {currentQuestionIndex + 1}
                      </span>
                    </div>

                    <h2 className="text-sm sm:text-base font-semibold text-[#151c2d] leading-7">
                      {currentQ.question}
                    </h2>

                  </div>

                  <div className="ml-10 flex items-start gap-1.5 text-[10px] text-[#7a808e] font-mono leading-relaxed">
                    <BookOpen
                      size={13}
                      strokeWidth={2}
                      className="shrink-0 mt-0.5"
                    />

                    <span>
                      <span className="font-semibold text-[#626977]">
                        Citation:
                      </span>{' '}
                      {currentQ.citation}
                    </span>
                  </div>

                </div>

                {/* OPTIONS */}

                <div className="space-y-2.5">

                  {currentQ.options.map((opt) => {
                    const isSelected =
                      selectedAnswers[currentQ.id] === opt.id;

                    return (
                      <button
                        key={opt.id}
                        type="button"
                        onClick={() => handleSelectOption(opt.id)}
                        className={`group w-full text-left p-3.5 sm:p-4 rounded-xl border transition-all duration-200 cursor-pointer flex items-start gap-3 ${
                          isSelected
                            ? 'bg-[#eef1ff] border-[#00236f] shadow-[0_3px_12px_rgba(0,35,111,0.08)]'
                            : 'bg-[#fbfcfe] border-[#e1e4eb] hover:border-[#aeb9d5] hover:bg-[#f7f8fc]'
                        }`}
                      >

                        {/* RADIO */}

                        <div
                          className={`relative mt-0.5 w-5 h-5 rounded-full shrink-0 flex items-center justify-center border-2 transition-all ${
                            isSelected
                              ? 'border-[#00236f]'
                              : 'border-[#b7bdc9] group-hover:border-[#6e7890]'
                          }`}
                        >
                          {isSelected && (
                            <div className="w-2.5 h-2.5 rounded-full bg-[#00236f]" />
                          )}
                        </div>

                        {/* LETTER */}

                        <div
                          className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 font-mono text-[11px] font-bold transition-all ${
                            isSelected
                              ? 'bg-[#00236f] text-white'
                              : 'bg-white text-[#687080] border border-[#e1e4eb] group-hover:border-[#b7bdc9]'
                          }`}
                        >
                          {opt.id}
                        </div>

                        {/* TEXT */}

                        <span
                          className={`text-xs leading-6 pt-0.5 ${
                            isSelected
                              ? 'text-[#00236f] font-semibold'
                              : 'text-[#252c3c]'
                          }`}
                        >
                          {opt.text}
                        </span>

                      </button>
                    );
                  })}

                </div>

                {/* EXPLANATION */}

                {showExplanation && (
                  <div className="mt-4 p-4 rounded-xl bg-[#f7f8fc] border border-[#dfe2eb]">

                    <div className="flex items-center gap-2 text-xs font-bold text-[#00236f] mb-2">
                      <div className="w-6 h-6 rounded-lg bg-[#e8ecff] flex items-center justify-center">
                        <Info size={14} strokeWidth={2.2} />
                      </div>

                      <span>
                        Official Gazette Statistical Standard
                      </span>
                    </div>

                    <p className="text-[11px] text-[#606777] leading-6 font-mono">
                      {currentQ.explanation}
                    </p>

                  </div>
                )}

                {/* NAVIGATION */}

                <div className="mt-6 pt-5 border-t border-[#edf0f5] flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3">

                  <div className="flex items-center gap-2">

                    <button
                      type="button"
                      onClick={handlePrev}
                      disabled={currentQuestionIndex === 0}
                      className="px-3.5 py-2.5 rounded-xl border border-[#dfe2eb] text-[#555d6d] hover:bg-[#f5f6fa] text-[11px] font-mono font-semibold transition-all disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer flex items-center gap-1.5"
                    >
                      <ArrowLeft size={14} />
                      Previous
                    </button>

                    <button
                      type="button"
                      onClick={() =>
                        setShowExplanation(!showExplanation)
                      }
                      className="px-3.5 py-2.5 rounded-xl bg-[#f5f6fb] text-[#00236f] text-[11px] font-mono font-semibold hover:bg-[#e9edff] transition-all cursor-pointer"
                    >
                      {showExplanation
                        ? 'Hide Rationale'
                        : 'View Rationale'}
                    </button>

                  </div>

                  {currentQuestionIndex <
                  questions.length - 1 ? (

                    <button
                      type="button"
                      onClick={handleNext}
                      className="bg-[#00236f] hover:bg-[#173d88] text-white px-5 py-2.5 rounded-xl text-[11px] font-bold font-mono transition-all shadow-sm hover:shadow-md flex items-center justify-center gap-2 cursor-pointer"
                    >
                      Next Question
                      <ArrowRight size={15} />
                    </button>

                  ) : (

                    <button
                      type="button"
                      onClick={handleSubmitQuiz}
                      className="bg-[#904d00] hover:bg-[#733d00] text-white px-5 py-2.5 rounded-xl text-[11px] font-bold font-mono transition-all shadow-sm hover:shadow-md flex items-center justify-center gap-2 cursor-pointer"
                    >
                      <BadgeCheck size={16} />
                      Submit Assessment
                    </button>

                  )}

                </div>

              </div>
            </div>

            {/* ==================================================
                RIGHT SIDEBAR
            ================================================== */}

            <div className="lg:col-span-4 space-y-4">

              {/* QUESTION INDEX */}

              <div className="bg-white border border-[#dfe2eb] rounded-2xl shadow-[0_5px_20px_rgba(0,35,111,0.04)] p-5">

                <div className="flex items-center justify-between mb-4">

                  <div>
                    <p className="text-[10px] uppercase tracking-[0.12em] font-bold font-mono text-[#00236f]">
                      Question Index
                    </p>

                    <p className="text-[10px] text-[#8a8f9d] font-mono mt-1">
                      Navigate freely
                    </p>
                  </div>

                  <span className="px-2.5 py-1 rounded-lg bg-[#eef1ff] text-[#00236f] text-[10px] font-mono font-bold">
                    {answeredCount}/{questions.length}
                  </span>

                </div>

                {/* QUESTION NUMBERS */}

                <div className="grid grid-cols-3 gap-2">

                  {questions.map((q, idx) => {
                    const isCurrent =
                      idx === currentQuestionIndex;

                    const isAnswered =
                      selectedAnswers[q.id] !== undefined;

                    return (
                      <button
                        key={q.id}
                        type="button"
                        onClick={() => {
                          setShowExplanation(false);
                          setCurrentQuestionIndex(idx);
                        }}
                        className={`relative py-3 px-3 rounded-xl text-[11px] font-mono font-bold transition-all flex items-center justify-between cursor-pointer ${
                          isCurrent
                            ? 'bg-[#00236f] text-white shadow-md'
                            : isAnswered
                            ? 'bg-[#eef1ff] text-[#00236f] border border-[#c4cdf4] hover:bg-[#e5e9ff]'
                            : 'bg-[#fafbfc] text-[#777e8d] border border-[#e1e4eb] hover:bg-[#f3f5f9]'
                        }`}
                      >
                        <span>Q{idx + 1}</span>

                        {isAnswered ? (
                          <CheckCircle
                            size={14}
                            strokeWidth={2.2}
                          />
                        ) : (
                          <span className="w-3.5 h-3.5 rounded-full border border-current opacity-60" />
                        )}
                      </button>
                    );
                  })}

                </div>

                {/* PROGRESS */}

                <div className="mt-5 pt-4 border-t border-[#edf0f5]">

                  <div className="flex items-center justify-between mb-2">

                    <span className="text-[10px] font-mono font-semibold text-[#747a88]">
                      Progress Completion
                    </span>

                    <span className="text-[11px] font-mono font-bold text-[#00236f]">
                      {progressPercent}%
                    </span>

                  </div>

                  <div className="h-2 bg-[#edf0f5] rounded-full overflow-hidden">

                    <div
                      className="h-full bg-[#00236f] rounded-full transition-all duration-500 ease-out"
                      style={{
                        width: `${progressPercent}%`,
                      }}
                    />

                  </div>

                </div>

                {/* FINISH */}

                <div className="mt-5 pt-4 border-t border-[#edf0f5]">

                  <button
                    type="button"
                    onClick={handleSubmitQuiz}
                    className="w-full bg-[#f5f6fb] hover:bg-[#e9edff] text-[#00236f] py-2.5 px-3 rounded-xl text-[11px] font-mono font-bold border border-[#dfe2eb] transition-all cursor-pointer flex items-center justify-center gap-2"
                  >
                    <ClipboardCheck size={16} />
                    Finish & Calculate Baseline
                  </button>

                </div>

              </div>

              {/* SCOPE GUIDE */}

              <div className="bg-[#10182b] rounded-2xl p-5 text-white shadow-[0_6px_20px_rgba(16,24,43,0.12)]">

                <div className="flex items-center gap-2 mb-3">

                  <div className="w-7 h-7 rounded-lg bg-white/10 flex items-center justify-center">
                    <Network size={15} strokeWidth={2} />
                  </div>

                  <div>
                    <p className="text-[10px] uppercase tracking-[0.12em] font-bold font-mono">
                      Cadre Alignment
                    </p>

                    <p className="text-[9px] text-white/50 font-mono mt-0.5">
                      MoSPI baseline matrix
                    </p>
                  </div>

                </div>

                <p className="text-[11px] leading-6 text-white/65">
                  Your answers evaluate six mathematical dimensions
                  matching the Cadre Cell baseline for{' '}
                  <span className="text-white font-semibold">
                    {officerProfile?.designation ||
                      'Statistical Officer'}
                  </span>
                  .
                </p>

              </div>

            </div>
          </div>

        ) : (

          /* ======================================================
             COMPLETED REPORT
          ====================================================== */

          <div className="w-full bg-white border border-[#dfe2eb] rounded-2xl shadow-[0_8px_35px_rgba(0,35,111,0.07)] overflow-hidden animate-in zoom-in-95 duration-300">

            <div className="h-1 bg-gradient-to-r from-[#005147] via-[#00236f] to-[#ff9b55]" />

            <div className="p-5 sm:p-8">

              {/* REPORT HEADER */}

              <div className="pb-6 border-b border-[#edf0f5]">

                <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-5">

                  <div className="flex items-center gap-4">

                    <div className="w-14 h-14 rounded-2xl bg-[#005147] text-white flex items-center justify-center shadow-sm">
                      <BadgeCheck
                        size={29}
                        strokeWidth={2}
                      />
                    </div>

                    <div>

                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#e6faf7] text-[#005147] font-mono text-[9px] font-bold tracking-wide mb-1.5">
                        <CheckCircle size={11} />
                        BASELINE DIAGNOSTIC ATTESTED
                      </span>

                      <h2 className="text-xl sm:text-2xl font-bold text-[#10182b]">
                        Officer Competency Vector
                      </h2>

                      <p className="text-[11px] text-[#7b8190] mt-1">
                        Generated for {officerProfile?.name} •{' '}
                        {officerProfile?.designation} •{' '}
                        {officerProfile?.cadreId}
                      </p>

                    </div>

                  </div>

                  {/* SCORE */}

                  <div className="flex items-center gap-3 bg-[#f7f8fc] p-3 rounded-2xl border border-[#dfe2eb]">

                    <div className="text-right font-mono">

                      <div className="text-[9px] uppercase tracking-wide text-[#818795] font-bold">
                        Diagnostic Score
                      </div>

                      <div className="text-lg font-bold text-[#00236f] mt-0.5">
                        {results.correct} / {results.total}
                      </div>

                    </div>

                    <div className="w-14 h-14 rounded-xl bg-[#00236f] text-white font-mono font-bold text-sm flex items-center justify-center shadow-sm">
                      {results.scorePercentage}%
                    </div>

                  </div>

                </div>
              </div>

              {/* ==================================================
                  DIMENSION BREAKDOWN
              ================================================== */}

              <div className="py-7">

                <div className="flex items-center gap-2 mb-4">

                  <div className="w-7 h-7 rounded-lg bg-[#eef1ff] text-[#00236f] flex items-center justify-center">
                    <Radar size={16} strokeWidth={2} />
                  </div>

                  <div>

                    <h3 className="text-xs font-bold text-[#00236f] uppercase font-mono">
                      Evaluated Competency Vectors
                    </h3>

                    <p className="text-[10px] text-[#858b98] font-mono mt-0.5">
                      Across 6 MoSPI Dimensions
                    </p>

                  </div>

                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">

                  {questions.map((q) => {

                    const isCorrect =
                      selectedAnswers[q.id] === q.correctAnswer;

                    const assignedLevel = isCorrect
                      ? 'Level 4 / 5'
                      : 'Level 2 / 5';

                    return (
                      <div
                        key={q.id}
                        className={`p-4 rounded-xl border transition-all ${
                          isCorrect
                            ? 'bg-[#f1fbf9] border-[#b8e4dc]'
                            : 'bg-[#fff8f2] border-[#ffd7bb]'
                        }`}
                      >

                        <div className="flex items-start justify-between gap-2 mb-3">

                          <span className="font-bold text-[11px] text-[#172033] leading-5">
                            {q.dimension}
                          </span>

                          <span
                            className={`shrink-0 text-[9px] font-bold px-2 py-1 rounded-lg ${
                              isCorrect
                                ? 'bg-[#d7f4ee] text-[#005147]'
                                : 'bg-[#ffe5d3] text-[#904d00]'
                            }`}
                          >
                            {isCorrect
                              ? 'Mastered'
                              : 'Gap Identified'}
                          </span>

                        </div>

                        <div className="space-y-1.5 text-[10px] font-mono">

                          <div className="flex items-center justify-between gap-3">
                            <span className="text-[#737a88]">
                              Assigned Vector
                            </span>

                            <strong className="text-[#172033]">
                              {assignedLevel}
                            </strong>
                          </div>

                          <div className="flex items-center justify-between gap-3">
                            <span className="text-[#737a88]">
                              Answer Given
                            </span>

                            <span className="text-[#333a49]">
                              {selectedAnswers[q.id] || 'Skipped'}
                            </span>
                          </div>

                          <div className="pt-2 border-t border-black/5">

                            <span
                              className={
                                isCorrect
                                  ? 'text-[#005147] font-semibold'
                                  : 'text-[#904d00] font-semibold'
                              }
                            >
                              {isCorrect
                                ? 'Correct response'
                                : `Correct answer: ${q.correctAnswer}`}
                            </span>

                          </div>

                        </div>

                      </div>
                    );
                  })}

                </div>

              </div>

              {/* ==================================================
                  RECOMMENDATION
              ================================================== */}

              <div className="bg-[#f7f8fc] border border-[#dfe2eb] rounded-2xl p-5 mb-6">

                <div className="flex items-center gap-2.5 mb-3">

                  <div className="w-8 h-8 rounded-xl bg-[#fff0df] text-[#904d00] flex items-center justify-center">
                    <Lightbulb size={17} strokeWidth={2} />
                  </div>

                  <div>
                    <h3 className="text-sm font-bold text-[#00236f]">
                      Cadre Promotion & Learning Pathway
                    </h3>

                    <p className="text-[9px] text-[#858b98] font-mono mt-0.5 uppercase tracking-wide">
                      Initial recommendation
                    </p>
                  </div>

                </div>

                <p className="text-[11px] text-[#555d6d] leading-6 font-mono mb-4">

                  Based on your initial diagnostic score (
                  <strong className="text-[#00236f]">
                    {results.scorePercentage}%
                  </strong>
                  ) and declared designation (
                  <strong>
                    {officerProfile?.designation}
                  </strong>
                  ), the sovereign inference engine has generated
                  an initial vector congruence of{' '}
                  <strong className="text-[#00236f]">
                    {results.congruence}%
                  </strong>{' '}
                  toward your target benchmark (
                  <strong>
                    {officerProfile?.targetBand}
                  </strong>
                  ).

                </p>

                <ul className="space-y-2 text-[10px] text-[#252c3c] font-mono">

                  <li className="flex gap-2">
                    <span className="text-[#005147]">✓</span>
                    <span>
                      NSSO Sampling & Weighting modules have been
                      added to your iGOT prerequisite pathways.
                    </span>
                  </li>

                  <li className="flex gap-2">
                    <span className="text-[#005147]">✓</span>
                    <span>
                      PySpark and Large-Scale Wrangling cluster
                      practice scenarios staged in Adaptive Practice.
                    </span>
                  </li>

                  <li className="flex gap-2">
                    <span className="text-[#005147]">✓</span>
                    <span>
                      DPDP Act 2023 Statutory Compliance badge
                      logged in your official dossier.
                    </span>
                  </li>

                </ul>

              </div>

              {/* ==================================================
                  BOTTOM ACTIONS
              ================================================== */}

              <div className="pt-5 border-t border-[#edf0f5] flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3">

                <div className="flex flex-col sm:flex-row gap-2">

                  <button
                    type="button"
                    onClick={() => setIsSubmitted(false)}
                    className="px-4 py-2.5 rounded-xl border border-[#dfe2eb] text-[#555d6d] hover:bg-[#f5f6fa] text-[10px] font-mono font-semibold transition-all cursor-pointer"
                  >
                    Review Answers
                  </button>

                  <button
                    type="button"
                    onClick={onBackToProfile}
                    className="px-4 py-2.5 rounded-xl border border-[#dfe2eb] text-[#555d6d] hover:bg-[#f5f6fa] text-[10px] font-mono font-semibold transition-all cursor-pointer"
                  >
                    Edit Profile / Designation
                  </button>

                </div>

                <button
                  type="button"
                  onClick={handleFinishAndLaunchDashboard}
                  className="w-full lg:w-auto bg-[#00236f] hover:bg-[#173d88] text-white py-3 px-6 rounded-xl text-[11px] font-bold font-mono tracking-wide transition-all shadow-md hover:shadow-lg flex items-center justify-center gap-2 cursor-pointer"
                >
                  <span>
                    Launch Skill-Intelligence Dashboard
                  </span>

                  <LayoutDashboard
                    size={17}
                    strokeWidth={2}
                  />
                </button>

              </div>

            </div>
          </div>
        )}

      </div>
    </div>
  );
}