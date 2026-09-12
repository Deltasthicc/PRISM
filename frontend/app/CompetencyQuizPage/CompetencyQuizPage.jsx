'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';

import {
  ArrowLeft,
  ArrowRight,
  BadgeCheck,
  BookOpen,
  CheckCircle,
  ChevronRight,
  ClipboardCheck,
  LayoutDashboard,
  Lightbulb,
  Network,
  Radar,
  ShieldCheck,
  Timer,
  Video,
  Volume2,
  XCircle,
} from 'lucide-react';

import { learning } from '@/lib/api/client';
import { useAuthStore } from '@/store/useAuthStore';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { COMPETENCY_TOPICS } from '@/lib/competencyTopics';
import ProctoringMonitor, { VIOLATION_LABELS } from '@/components/ProctoringMonitor';

const QUESTIONS_PER_TOPIC = 3;

// A real Next.js route (see app/baseline-assessment/page.jsx) instead of a
// step inside the old login/page.jsx state machine, so it sources the
// player/profile from real auth + backend state instead of receiving a
// fabricated "officerProfile" prop.
export default function CompetencyQuizPage() {
  const router = useRouter();
  const { ready } = useRequireAuth();
  const player = useAuthStore((state) => state.player);

  const [profile, setProfile] = useState(null);
  const [profileLoading, setProfileLoading] = useState(true);

  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [selectedAnswers, setSelectedAnswers] = useState({});
  const [isSubmitted, setIsSubmitted] = useState(false);
  const [reviewIndex, setReviewIndex] = useState(null);
  const [timeRemaining, setTimeRemaining] = useState(600);
  const [isTimerRunning, setIsTimerRunning] = useState(true);

  // Real, source-cited questions fetched from routes/competency_quiz.py,
  // one topic per curriculum the learner picked at registration
  // (LearnerProfile.target_domains). Falls back to the first real topic if
  // none of their picks matched one (e.g. a profile predating this route).
  const [questions, setQuestions] = useState([]);
  const [loadingQuestions, setLoadingQuestions] = useState(true);
  const [loadError, setLoadError] = useState('');
  const [submitError, setSubmitError] = useState('');
  const [results, setResults] = useState(null);
  const [submittingQuiz, setSubmittingQuiz] = useState(false);

  // Webcam integrity monitoring -- opt-in, off by default (see
  // components/ProctoringMonitor.jsx). `proctoringEverEnabled` survives a
  // later toggle-off/submission so the completed report can still show an
  // honest "N signals recorded" summary rather than losing it the moment the
  // camera stops. Counts are purely local bookkeeping for that summary --
  // ProctoringMonitor itself owns reporting each event to the backend.
  const [proctoringEnabled, setProctoringEnabled] = useState(false);
  const [proctoringEverEnabled, setProctoringEverEnabled] = useState(false);
  const [violationCounts, setViolationCounts] = useState({});

  // Per-question elapsed time, keyed by item_id, accumulated across every
  // visit to that question (Next/Prev/jump all flush the running delta) --
  // see recordElapsed()/questionStartRef below. Sent to the backend as
  // time_taken_ms so routes/competency_quiz.py's scoring can use it as a
  // secondary, accuracy-never-overriding confidence signal.
  const timeSpentRef = useRef({});
  const questionStartRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    if (!ready || !player) return undefined;

    async function loadProfile() {
      setProfileLoading(true);
      try {
        const { profile: fetched } = await learning.getProfile(player.player_id);
        if (!cancelled) setProfile(fetched);
      } catch {
        if (!cancelled) setProfile({});
      } finally {
        if (!cancelled) setProfileLoading(false);
      }
    }

    loadProfile();
    return () => {
      cancelled = true;
    };
  }, [ready, player]);

  const displayName = profile?.full_name || player?.username || '';
  const initials = displayName
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || '?';

  const selectedTopics = useMemo(() => {
    const targetDomains = profile?.target_domains || [];
    const picked = COMPETENCY_TOPICS.filter((topic) => targetDomains.includes(topic.curriculumSlug));
    return picked.length > 0 ? picked : [COMPETENCY_TOPICS[0]];
  }, [profile?.target_domains]);

  useEffect(() => {
    let cancelled = false;
    if (profileLoading) return undefined;

    async function loadQuestions() {
      setLoadingQuestions(true);
      setLoadError('');
      try {
        const batches = await Promise.all(
          selectedTopics.map((topic) =>
            learning
              .getCompetencyQuizQuestions(topic.id, QUESTIONS_PER_TOPIC)
              .then((response) =>
                response.questions.map((q) => ({
                  ...q,
                  topic_id: topic.id,
                  attempt_id: response.attempt_id,
                }))
              )
          )
        );
        if (!cancelled) setQuestions(batches.flat());
      } catch (cause) {
        if (!cancelled) setLoadError(cause.message);
      } finally {
        if (!cancelled) setLoadingQuestions(false);
      }
    }

    loadQuestions();
    return () => {
      cancelled = true;
    };
    // selectedTopics is derived from profile.target_domains, which is
    // stable for the lifetime of one quiz attempt.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileLoading]);

  // ============================================================
  // PER-QUESTION TIMING
  // ============================================================

  useEffect(() => {
    if (isSubmitted || !questions.length) return;
    questionStartRef.current = Date.now();
  }, [currentQuestionIndex, questions.length, isSubmitted]);

  function recordElapsed() {
    const q = questions[currentQuestionIndex];
    if (!q || questionStartRef.current == null) return;
    const delta = Date.now() - questionStartRef.current;
    timeSpentRef.current[q.item_id] = (timeSpentRef.current[q.item_id] || 0) + delta;
    questionStartRef.current = Date.now();
  }

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
  // QUIZ STATE
  // ============================================================
  // `questions` is now fetched from the real backend (see the useEffect
  // above) -- routes/competency_quiz.py, backed by
  // services/hand_authored_questions.py. Each question's `options` is a
  // plain array of strings (not {id,text} objects); the letter shown in the
  // UI (A/B/C/D) is just its array index, and `selectedAnswers` stores that
  // numeric index, not a letter -- the real answer_index never reaches the
  // client until after /submit grades it server-side.

  const currentQ = questions[currentQuestionIndex];

  // attempt_id here is issued per-topic (see the questions-loading effect
  // above), but one proctoring session should span the whole multi-topic
  // quiz -- group every violation under the first topic's attempt_id rather
  // than trying to attribute a webcam signal to whichever topic happens to
  // be on screen when it fires.
  const proctoringAttemptId = questions[0]?.attempt_id ?? null;

  const totalViolations = useMemo(
    () => Object.values(violationCounts).reduce((sum, count) => sum + count, 0),
    [violationCounts]
  );

  const handleToggleProctoring = () => {
    setProctoringEnabled((prev) => {
      const next = !prev;
      if (next) setProctoringEverEnabled(true);
      return next;
    });
  };

  const handleProctoringViolation = (violationType) => {
    setViolationCounts((prev) => ({ ...prev, [violationType]: (prev[violationType] || 0) + 1 }));
  };

  const answeredCount = Object.keys(selectedAnswers).length;

  const progressPercent = questions.length
    ? Math.round((answeredCount / questions.length) * 100)
    : 0;

  // ============================================================
  // SELECT ANSWER
  // ============================================================

  const handleSelectOption = (optionIndex) => {
    if (isSubmitted || !currentQ) return;

    // Functional update (rather than spreading the closed-over
    // `selectedAnswers`) so the keyboard-shortcut handler below always
    // applies against the latest answers, even across rapid keypresses
    // within the same render.
    setSelectedAnswers((prev) => ({
      ...prev,
      [currentQ.item_id]: optionIndex,
    }));
  };

  // Fill-in-the-blank items store their answer as trimmed text under the
  // same selectedAnswers map (keyed by item_id) as MCQ option indices --
  // handleSubmitQuiz branches on currentQ.question_type to know which shape
  // to send. An empty/whitespace-only draft is treated as "not answered
  // yet" so answeredCount/progress stay accurate.
  const handleTextAnswerChange = (itemId, text) => {
    if (isSubmitted) return;
    setSelectedAnswers((prev) => {
      const next = { ...prev };
      if (text.trim()) {
        next[itemId] = text;
      } else {
        delete next[itemId];
      }
      return next;
    });
  };

  // ============================================================
  // NEXT / PREVIOUS
  // ============================================================

  const handleNext = () => {
    recordElapsed();
    if (currentQuestionIndex < questions.length - 1) {
      setCurrentQuestionIndex(currentQuestionIndex + 1);
    }
  };

  const handlePrev = () => {
    recordElapsed();
    if (currentQuestionIndex > 0) {
      setCurrentQuestionIndex(currentQuestionIndex - 1);
    }
  };

  const jumpToQuestion = (idx) => {
    recordElapsed();
    setCurrentQuestionIndex(idx);
  };

  // ============================================================
  // READ ALOUD -- real browser Web Speech API (window.speechSynthesis),
  // not a mock. Guarded for SSR (`typeof window === 'undefined'`) and for
  // browsers that don't implement the API at all; the button is disabled
  // with an explanatory title in that case rather than throwing.
  // ============================================================

  const speechSupported = typeof window !== 'undefined' && 'speechSynthesis' in window;

  const handleReadAloud = () => {
    if (!speechSupported || !currentQ) return;

    // Cancel any in-progress utterance first so navigating between
    // questions (or clicking Read Aloud again) never overlaps audio.
    window.speechSynthesis.cancel();

    const parts = [currentQ.question];
    if (currentQ.question_type !== 'fill_in_blank' && Array.isArray(currentQ.options)) {
      currentQ.options.forEach((optionText, optionIndex) => {
        parts.push(`Option ${String.fromCharCode(65 + optionIndex)}: ${optionText}`);
      });
    }

    const utterance = new SpeechSynthesisUtterance(parts.join('. '));
    window.speechSynthesis.speak(utterance);
  };

  // Stop any in-progress speech the moment the learner moves to a
  // different question (Next/Prev/jump), and on unmount -- otherwise the
  // previous question's audio would keep playing over the new one.
  useEffect(() => {
    if (!speechSupported) return undefined;
    return () => {
      window.speechSynthesis.cancel();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentQuestionIndex, speechSupported]);

  // ============================================================
  // KEYBOARD NAVIGATION -- only while the quiz is live (not after
  // submission) and only when focus isn't inside a text input, since a
  // fill-in-the-blank answer may legitimately contain a digit that would
  // otherwise get hijacked as an option shortcut.
  // ============================================================

  useEffect(() => {
    if (isSubmitted) return undefined;

    function handleQuizKeyDown(event) {
      const targetTag = event.target?.tagName;
      if (targetTag === 'INPUT' || targetTag === 'TEXTAREA') return;
      if (!currentQ) return;

      const key = event.key;

      if (currentQ.question_type !== 'fill_in_blank' && Array.isArray(currentQ.options)) {
        const numberToIndex = { '1': 0, '2': 1, '3': 2, '4': 3 };
        const letterToIndex = { a: 0, b: 1, c: 2, d: 3 };
        const lowerKey = key.length === 1 ? key.toLowerCase() : key;

        let optionIndex;
        if (key in numberToIndex) optionIndex = numberToIndex[key];
        else if (lowerKey in letterToIndex) optionIndex = letterToIndex[lowerKey];

        if (optionIndex !== undefined && optionIndex < currentQ.options.length) {
          event.preventDefault();
          handleSelectOption(optionIndex);
          return;
        }
      }

      if (key === 'ArrowRight' || key === 'Enter') {
        event.preventDefault();
        if (currentQuestionIndex < questions.length - 1) {
          handleNext();
        } else if (!submittingQuiz) {
          handleSubmitQuiz();
        }
        return;
      }

      if (key === 'ArrowLeft') {
        event.preventDefault();
        handlePrev();
      }
    }

    document.addEventListener('keydown', handleQuizKeyDown);
    return () => document.removeEventListener('keydown', handleQuizKeyDown);
    // selectedAnswers is included so the handler's closures (handleNext /
    // handleSubmitQuiz, which read answeredCount/selectedAnswers) never go
    // stale between an option keypress and an immediate Enter/ArrowRight.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSubmitted, currentQ, currentQuestionIndex, questions.length, selectedAnswers, submittingQuiz]);

  // ============================================================
  // SUBMIT -- real server-side grading, one call per selected topic
  // ============================================================

  const handleSubmitQuiz = async () => {
    if (answeredCount !== questions.length) {
      setSubmitError('Please answer every question before submitting this baseline.');
      return;
    }
    recordElapsed();
    setSubmittingQuiz(true);
    setSubmitError('');
    setIsTimerRunning(false);

    try {
      const byTopic = {};
      questions.forEach((q) => {
        if (selectedAnswers[q.item_id] === undefined) return;
        const group = (byTopic[q.topic_id] ||= {
          attemptId: q.attempt_id,
          answers: [],
        });
        const timeTakenMs = timeSpentRef.current[q.item_id] || null;
        group.answers.push(
          q.question_type === 'fill_in_blank'
            ? { item_id: q.item_id, answer_text: selectedAnswers[q.item_id], time_taken_ms: timeTakenMs }
            : { item_id: q.item_id, selected_index: selectedAnswers[q.item_id], time_taken_ms: timeTakenMs }
        );
      });

      const topicResults = await Promise.all(
        Object.entries(byTopic).map(([topicId, attempt]) =>
          learning.submitCompetencyQuiz(
            attempt.attemptId,
            topicId,
            attempt.answers,
            player?.player_id
          )
        )
      );

      const gradedByItemId = {};
      const competencyScores = {};
      let correct = 0;
      let total = 0;

      topicResults.forEach((topicResult) => {
        correct += topicResult.correct;
        total += topicResult.total;
        topicResult.graded_answers.forEach((g) => {
          gradedByItemId[g.item_id] = g;
        });
        topicResult.competency_scores.forEach((c) => {
          competencyScores[c.competency_id] = c;
        });
      });

      const scorePercentage = total ? Math.round((correct / total) * 100) : 0;

      setResults({
        total,
        correct,
        scorePercentage,
        gradedByItemId,
        competencyScores: Object.values(competencyScores),
        evidencePersisted: topicResults.every(
          (topicResult) => topicResult.persisted_as_diagnostic_evidence
        ),
      });
      setIsSubmitted(true);
    } catch (cause) {
      setSubmitError(cause.message || 'The quiz could not be graded. Please retry.');
      setIsTimerRunning(true);
    } finally {
      setSubmittingQuiz(false);
    }
  };

  // ============================================================
  // FINISH QUIZ
  // ============================================================

  const handleFinishAndLaunchDashboard = () => {
    router.push('/stats');
  };

  // ============================================================
  // LOADING / ERROR
  // ============================================================

  if (!ready || profileLoading || loadingQuestions) {
    return (
      <div className="min-h-screen w-full bg-[#f7f8fc] flex items-center justify-center px-4">
        <p className="text-sm text-[#555d6d] font-mono">Preparing your competency assessment…</p>
      </div>
    );
  }

  if (loadError || questions.length === 0) {
    return (
      <div className="min-h-screen w-full bg-[#f7f8fc] flex flex-col items-center justify-center gap-4 px-4">
        <p className="text-sm text-[#b3261e] font-mono text-center">
          {loadError || 'No questions are available for the selected specialization yet.'}
        </p>
        <button
          type="button"
          onClick={() => router.push('/academy')}
          className="px-4 py-2.5 rounded-xl border border-[#dfe2eb] text-[#00236f] text-xs font-semibold hover:bg-[#f5f6fa]"
        >
          Back to Academy
        </button>
      </div>
    );
  }

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
                {initials}
              </div>

              <div className="min-w-0">

                <div className="flex items-center gap-2 flex-wrap">

                  <span className="font-bold text-sm text-[#10182b]">
                    {displayName}
                  </span>

                  {profile?.designation && (
                    <span className="px-2 py-1 rounded-md bg-[#eef1ff] text-[#00236f] font-mono text-[10px] font-bold">
                      {profile.designation}
                    </span>
                  )}

                </div>

                <p className="text-[10px] text-[#8a8f9d] font-mono mt-0.5">
                  {player?.username}
                </p>

              </div>
            </div>

            {/* TIMER */}

            <div className="flex items-center gap-2 self-end sm:self-auto">

              <div
                className={`flex items-center gap-2 px-3.5 py-2 rounded-xl border font-mono ${
                  timeRemaining === 0
                    ? 'bg-[#f5f6fb] border-[#dfe2eb] text-[#555d6d]'
                    : 'bg-[#f5f6fb] border-[#dfe2eb] text-[#172033]'
                }`}
              >
                <Timer
                  size={17}
                  strokeWidth={2.2}
                  className={
                    timeRemaining === 0
                      ? 'text-[#555d6d]'
                      : 'text-[#904d00]'
                  }
                />

                <span className="font-bold tracking-wide">
                  {timeRemaining === 0 ? 'PACE GUIDE ENDED' : formatTime(timeRemaining)}
                </span>
              </div>

              <span className="hidden sm:inline-flex px-3 py-2 rounded-xl bg-[#fff2e9] text-[#904d00] font-bold text-[10px] font-mono border border-[#ffd2b5]">
                SUGGESTED PACE
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
                    Evaluate your current competency vector across the
                    areas selected in your profile.
                </p>
              </div>

              <div className="flex items-center gap-2 text-[10px] font-mono text-[#747a88]">
                <span className="w-2 h-2 rounded-full bg-[#005147]" />
                Assessment active
              </div>

            </div>

            {/* WEBCAM INTEGRITY MONITORING -- explicit opt-in, default off.
                Never started silently: the camera only ever turns on after
                this button is clicked. */}
            <div className="mt-4 flex flex-wrap items-center gap-3 p-3 rounded-xl bg-white border border-[#dfe2eb]">
              <button
                type="button"
                onClick={handleToggleProctoring}
                aria-pressed={proctoringEnabled}
                className="flex items-center gap-2.5 cursor-pointer"
              >
                <span
                  className={`relative w-9 h-5 rounded-full transition-colors shrink-0 ${
                    proctoringEnabled ? 'bg-[#00236f]' : 'bg-[#dfe2eb]'
                  }`}
                >
                  <span
                    className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-transform ${
                      proctoringEnabled ? 'translate-x-4' : 'translate-x-0.5'
                    }`}
                  />
                </span>
                <Video size={14} className="text-[#00236f] shrink-0" />
                <span className="text-[11px] font-mono font-semibold text-[#151c2d] text-left">
                  Enable webcam integrity monitoring for this session
                </span>
              </button>

              {proctoringEnabled && (
                <span className="ml-auto inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#eef1ff] text-[#00236f] font-mono text-[10px] font-bold">
                  <ShieldCheck size={12} />
                  {totalViolations} signal{totalViolations === 1 ? '' : 's'} so far
                </span>
              )}
            </div>

            <p className="mt-1.5 text-[9px] text-[#8a8f9d] font-mono leading-relaxed px-1">
              Optional and off by default. This never blocks or auto-fails your submission -- it
              only records signals (face/phone visibility, tab or fullscreen changes) for a human
              reviewer.
            </p>

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
                      {currentQ.competency_label}
                    </span>

                  </div>

                  <span className="font-mono text-[10px] text-[#8a8f9d] uppercase prism-large-text-meta">
                    {currentQ.difficulty}
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

                    <h2 className="text-sm sm:text-base font-semibold text-[#151c2d] leading-7 prism-large-text-question flex-1">
                      {currentQ.question}
                    </h2>

                    {/* READ ALOUD -- real window.speechSynthesis (Web Speech
                        API), not a mock. Reads the question, then each
                        option as "Option A: ...". Disabled with an
                        explanatory title when the browser doesn't support
                        speech synthesis at all. */}
                    <button
                      type="button"
                      onClick={handleReadAloud}
                      disabled={!speechSupported}
                      title={
                        speechSupported
                          ? 'Read this question and its options aloud'
                          : 'Text-to-speech is not supported in this browser'
                      }
                      className="shrink-0 flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border border-[#c5c5d3]/40 text-[#00236f] text-[10px] font-mono font-semibold hover:bg-[#f5f6fa] transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                    >
                      <Volume2 size={13} />
                      Read aloud
                    </button>

                  </div>

                  <div className="ml-10 flex items-start gap-1.5 text-[10px] text-[#7a808e] font-mono leading-relaxed prism-large-text-meta">
                    <BookOpen
                      size={13}
                      strokeWidth={2}
                      className="shrink-0 mt-0.5"
                    />

                    <span>
                      <span className="font-semibold text-[#626977]">
                        Source:
                      </span>{' '}
                      {currentQ.doc_id}
                      {currentQ.locator ? ` — ${currentQ.locator}` : ''}
                    </span>
                  </div>

                </div>

                {/* ANSWER INPUT -- fill-in-the-blank gets a text field, MCQ gets options */}

                {currentQ.question_type === 'fill_in_blank' ? (
                  <div className="pt-1">
                    <label htmlFor="fill-in-blank-answer" className="sr-only">
                      Your answer
                    </label>
                    <input
                      id="fill-in-blank-answer"
                      type="text"
                      autoComplete="off"
                      value={selectedAnswers[currentQ.item_id] || ''}
                      onChange={(event) => handleTextAnswerChange(currentQ.item_id, event.target.value)}
                      placeholder="Type the missing word or phrase…"
                      className="w-full px-4 py-3.5 rounded-xl border border-[#dfe2eb] bg-[#fbfcfe] text-sm text-[#151c2d] outline-none transition focus:border-[#00236f] focus:bg-white focus:ring-4 focus:ring-[#00236f]/5"
                    />
                  </div>
                ) : (
                <div
                  className="space-y-2.5"
                  role="radiogroup"
                  aria-label={`Question ${currentQuestionIndex + 1} answer options`}
                >

                  {currentQ.options.map((optionText, optionIndex) => {
                    const isSelected =
                      selectedAnswers[currentQ.item_id] === optionIndex;
                    const letter = String.fromCharCode(65 + optionIndex);

                    return (
                      <button
                        key={optionIndex}
                        type="button"
                        onClick={() => handleSelectOption(optionIndex)}
                        role="radio"
                        aria-checked={isSelected}
                        aria-label={`${letter}. ${optionText}`}
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
                          {letter}
                        </div>

                        {/* TEXT */}

                        <span
                          className={`text-xs leading-6 pt-0.5 prism-large-text-option ${
                            isSelected
                              ? 'text-[#00236f] font-semibold'
                              : 'text-[#252c3c]'
                          }`}
                        >
                          {optionText}
                        </span>

                      </button>
                    );
                  })}

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
                      disabled={submittingQuiz || answeredCount !== questions.length}
                      className="bg-[#904d00] hover:bg-[#733d00] text-white px-5 py-2.5 rounded-xl text-[11px] font-bold font-mono transition-all shadow-sm hover:shadow-md flex items-center justify-center gap-2 cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed"
                    >
                      <BadgeCheck size={16} />
                      {submittingQuiz
                        ? 'Grading…'
                        : answeredCount === questions.length
                          ? 'Submit Assessment'
                          : `Answer ${questions.length - answeredCount} more`}
                    </button>

                  )}

                </div>

                {submitError && (
                  <p role="alert" className="mt-3 text-[11px] text-[#b3261e] font-mono">
                    {submitError}
                  </p>
                )}

              </div>
            </div>

            {/* ==================================================
                RIGHT SIDEBAR
            ================================================== */}

            <div className="lg:col-span-4 space-y-4">

              {proctoringEnabled && (
                <ProctoringMonitor
                  playerId={player?.player_id}
                  attemptId={proctoringAttemptId}
                  enabled={proctoringEnabled}
                  onViolation={handleProctoringViolation}
                />
              )}

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
                      selectedAnswers[q.item_id] !== undefined;

                    return (
                      <button
                        key={q.item_id}
                        type="button"
                        onClick={() => jumpToQuestion(idx)}
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
                      role="progressbar"
                      aria-label="Quiz completion"
                      aria-valuemin={0}
                      aria-valuemax={questions.length}
                      aria-valuenow={answeredCount}
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
                    disabled={submittingQuiz || answeredCount !== questions.length}
                    className="w-full bg-[#f5f6fb] hover:bg-[#e9edff] text-[#00236f] py-2.5 px-3 rounded-xl text-[11px] font-mono font-bold border border-[#dfe2eb] transition-all cursor-pointer flex items-center justify-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed"
                  >
                    <ClipboardCheck size={16} />
                    {answeredCount === questions.length
                      ? 'Finish & Calculate Baseline'
                      : `${answeredCount}/${questions.length} answered`}
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
                      Assessment Scope
                    </p>

                    <p className="text-[9px] text-white/50 font-mono mt-0.5">
                      Curated prototype item set
                    </p>
                  </div>

                </div>

                <p className="text-[11px] leading-6 text-white/65">
                  Your selected specialities determine the question topics.
                  Results are a provisional signal for{' '}
                  <span className="text-white font-semibold">
                    {profile?.designation || displayName}
                  </span>
                  , not an official or psychometrically validated rating.
                </p>

              </div>

            </div>
          </div>

        ) : reviewIndex !== null ? (

          /* ======================================================
             REVIEW MODE -- read-only per-question breakdown of what was
             already graded. This is the fix for the old "Review Answers"
             bug: that button used to call setIsSubmitted(false), which
             re-rendered the exact same live/editable quiz UI against an
             attempt_id the backend had already consumed, so re-submitting
             always 409'd with "expired or already submitted" and there was
             no way to actually see which answers were right or wrong.
             This branch never re-enters the live quiz at all -- it only
             ever reads from `results`, which is never cleared.
          ====================================================== */

          (() => {
            const reviewQuestion = questions[reviewIndex];
            const reviewGraded = results.gradedByItemId[reviewQuestion.item_id];
            const reviewIsCorrect = Boolean(reviewGraded?.correct);
            const reviewIsFillInBlank = reviewQuestion.question_type === 'fill_in_blank';
            const submittedValue = reviewIsFillInBlank
              ? reviewGraded?.submitted_text
              : reviewGraded?.selected_index;

            return (
              <div className="w-full bg-white border border-[#dfe2eb] rounded-2xl shadow-[0_6px_25px_rgba(0,35,111,0.05)] overflow-hidden">
                <div className={`h-1 ${reviewIsCorrect ? 'bg-[#005147]' : 'bg-[#904d00]'}`} />
                <div className="p-5 sm:p-7">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-[#edf0f5]">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-[#00236f] text-white font-mono text-[11px] font-bold">
                        Q{reviewIndex + 1}
                        <ChevronRight size={12} />
                        {questions.length}
                      </span>
                      <span className="px-2.5 py-1 rounded-lg bg-[#fff1e7] text-[#904d00] font-mono text-[10px] font-bold">
                        {reviewQuestion.competency_label}
                      </span>
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg font-mono text-[10px] font-bold ${
                          reviewIsCorrect ? 'bg-[#d7f4ee] text-[#005147]' : 'bg-[#ffe5d3] text-[#904d00]'
                        }`}
                      >
                        {reviewIsCorrect ? <CheckCircle size={12} /> : <XCircle size={12} />}
                        {reviewIsCorrect ? 'Correct' : 'Incorrect'}
                      </span>
                    </div>
                  </div>

                  <div className="py-6">
                    <h2 className="text-sm sm:text-base font-semibold text-[#151c2d] leading-7 mb-4">
                      {reviewQuestion.question}
                    </h2>

                    {reviewIsFillInBlank ? (
                      <div className="space-y-2">
                        <div className="p-3.5 rounded-xl border border-[#e1e4eb] bg-[#fbfcfe]">
                          <span className="font-mono text-[10px] text-[#7a808e] block mb-1">Your answer</span>
                          <span className="text-xs text-[#252c3c]">{submittedValue || '(skipped)'}</span>
                        </div>
                        {!reviewIsCorrect && (
                          <div className="p-3.5 rounded-xl border border-[#b8e4dc] bg-[#f1fbf9]">
                            <span className="font-mono text-[10px] text-[#7a808e] block mb-1">Accepted answer</span>
                            <span className="text-xs text-[#005147] font-semibold">
                              {reviewGraded?.correct_answer_display}
                            </span>
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="space-y-2.5">
                        {reviewQuestion.options.map((optionText, optionIndex) => {
                          const wasSelected = submittedValue === optionIndex;
                          const isCorrectOption = reviewGraded?.correct_index === optionIndex;
                          const letter = String.fromCharCode(65 + optionIndex);
                          return (
                            <div
                              key={optionIndex}
                              className={`w-full text-left p-3.5 rounded-xl border flex items-start gap-3 ${
                                isCorrectOption
                                  ? 'bg-[#f1fbf9] border-[#b8e4dc]'
                                  : wasSelected
                                    ? 'bg-[#fff8f2] border-[#ffd7bb]'
                                    : 'bg-[#fbfcfe] border-[#e1e4eb]'
                              }`}
                            >
                              <div
                                className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 font-mono text-[11px] font-bold ${
                                  isCorrectOption
                                    ? 'bg-[#005147] text-white'
                                    : wasSelected
                                      ? 'bg-[#904d00] text-white'
                                      : 'bg-white text-[#687080] border border-[#e1e4eb]'
                                }`}
                              >
                                {letter}
                              </div>
                              <span className="text-xs leading-6 pt-0.5 text-[#252c3c]">{optionText}</span>
                              {wasSelected && !isCorrectOption && (
                                <span className="ml-auto text-[9px] font-mono font-bold text-[#904d00] shrink-0">
                                  YOUR ANSWER
                                </span>
                              )}
                              {isCorrectOption && (
                                <span className="ml-auto text-[9px] font-mono font-bold text-[#005147] shrink-0">
                                  CORRECT
                                </span>
                              )}
                            </div>
                          );
                        })}
                      </div>
                    )}

                    <div className="mt-5 p-4 rounded-xl bg-[#f7f8fc] border border-[#dfe2eb]">
                      <p className="text-[10px] font-mono font-bold uppercase tracking-wide text-[#757682] mb-1.5">
                        Explanation
                      </p>
                      <p className="text-xs text-[#333a49] leading-6">{reviewGraded?.explanation}</p>
                      <p className="text-[10px] text-[#8a8f9d] font-mono mt-2">
                        Source: {reviewGraded?.doc_id}
                        {reviewGraded?.locator ? ` — ${reviewGraded.locator}` : ''}
                      </p>
                    </div>
                  </div>

                  <div className="pt-5 border-t border-[#edf0f5] flex items-center justify-between gap-3">
                    <button
                      type="button"
                      onClick={() => setReviewIndex(Math.max(0, reviewIndex - 1))}
                      disabled={reviewIndex === 0}
                      className="px-3.5 py-2.5 rounded-xl border border-[#dfe2eb] text-[#555d6d] hover:bg-[#f5f6fa] text-[11px] font-mono font-semibold transition-all disabled:opacity-30 disabled:cursor-not-allowed flex items-center gap-1.5"
                    >
                      <ArrowLeft size={14} />
                      Previous
                    </button>
                    <button
                      type="button"
                      onClick={() => setReviewIndex(null)}
                      className="px-4 py-2.5 rounded-xl bg-[#f5f6fb] text-[#00236f] text-[11px] font-mono font-bold hover:bg-[#e9edff]"
                    >
                      Back to Results
                    </button>
                    {reviewIndex < questions.length - 1 ? (
                      <button
                        type="button"
                        onClick={() => setReviewIndex(reviewIndex + 1)}
                        className="px-3.5 py-2.5 rounded-xl bg-[#00236f] text-white text-[11px] font-mono font-bold hover:bg-[#173d88] flex items-center gap-1.5"
                      >
                        Next
                        <ArrowRight size={14} />
                      </button>
                    ) : (
                      <div className="w-[88px]" />
                    )}
                  </div>
                </div>
              </div>
            );
          })()

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
                        PROVISIONAL DEMO BASELINE
                      </span>

                      <h2 className="text-xl sm:text-2xl font-bold text-[#10182b]">
                        Officer Competency Vector
                      </h2>

                      <p className="text-[11px] text-[#7b8190] mt-1">
                        Generated for {displayName}
                        {profile?.designation ? ` • ${profile.designation}` : ''} •{' '}
                        {player?.username}
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
                      Across {results.competencyScores.length} Competency Dimensions
                    </p>

                  </div>

                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">

                  {questions.map((q) => {

                    const graded = results.gradedByItemId[q.item_id];
                    const isCorrect = Boolean(graded?.correct);
                    const isFillInBlank = q.question_type === 'fill_in_blank';
                    const selectedValue = selectedAnswers[q.item_id];
                    const answerGivenDisplay = isFillInBlank
                      ? selectedValue || 'Skipped'
                      : selectedValue !== undefined
                        ? String.fromCharCode(65 + selectedValue)
                        : 'Skipped';
                    const correctAnswerDisplay = graded
                      ? isFillInBlank
                        ? graded.correct_answer_display
                        : String.fromCharCode(65 + graded.correct_index)
                      : '';

                    const questionIndex = questions.indexOf(q);

                    return (
                      <button
                        key={q.item_id}
                        type="button"
                        onClick={() => setReviewIndex(questionIndex)}
                        className={`text-left p-4 rounded-xl border transition-all hover:shadow-md cursor-pointer ${
                          isCorrect
                            ? 'bg-[#f1fbf9] border-[#b8e4dc]'
                            : 'bg-[#fff8f2] border-[#ffd7bb]'
                        }`}
                      >

                        <div className="flex items-start justify-between gap-2 mb-3">

                          <span className="font-bold text-[11px] text-[#172033] leading-5">
                            {q.competency_label}
                          </span>

                          <span
                            className={`shrink-0 text-[9px] font-bold px-2 py-1 rounded-lg ${
                              isCorrect
                                ? 'bg-[#d7f4ee] text-[#005147]'
                                : 'bg-[#ffe5d3] text-[#904d00]'
                            }`}
                          >
                            {isCorrect ? 'Correct' : 'Needs review'}
                          </span>

                        </div>

                        <div className="space-y-1.5 text-[10px] font-mono">

                          <div className="flex items-center justify-between gap-3">
                            <span className="text-[#737a88]">
                              Item outcome
                            </span>

                            <strong className="text-[#172033]">
                              {isCorrect ? 'Correct response' : 'Incorrect response'}
                            </strong>
                          </div>

                          <div className="flex items-center justify-between gap-3">
                            <span className="text-[#737a88]">
                              Answer Given
                            </span>

                            <span className="text-[#333a49]">
                              {answerGivenDisplay}
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
                                : `Correct answer: ${correctAnswerDisplay}`}
                            </span>

                          </div>

                        </div>

                      </button>
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
                      Provisional Learning Signal
                    </h3>

                    <p className="text-[9px] text-[#858b98] font-mono mt-0.5 uppercase tracking-wide">
                      Initial recommendation
                    </p>
                  </div>

                </div>

                <p className="text-[11px] text-[#555d6d] leading-6 font-mono mb-4">

                  Based only on this short curated diagnostic, your score is{' '}
                  <strong className="text-[#00236f]">
                    {results.scorePercentage}%
                  </strong>
                  . The ranking below uses answer accuracy and evidence count;
                  it is not an official proficiency or promotion decision.

                </p>

                <ul className="space-y-2 text-[10px] text-[#252c3c] font-mono">

                  {results.competencyScores
                    .slice()
                    .sort((a, b) => a.rank - b.rank)
                    .map((score) => (
                      <li key={score.competency_id} className="flex gap-2">
                        <span
                          className={
                            score.provisional_level >= 3
                              ? 'text-[#005147]'
                              : 'text-[#904d00]'
                          }
                        >
                          {score.provisional_level >= 3 ? '✓' : '△'}
                        </span>
                        <span>
                          {score.competency_label}: {score.correct}/{score.total} correct
                          {' '}(Provisional {score.provisional_level} / 5, rank {score.rank}, {score.confidence} evidence)
                        </span>
                      </li>
                    ))}

                </ul>

              </div>

              {/* ==================================================
                  EXAM INTEGRITY SUMMARY -- only shown if the learner opted
                  in at some point this session. Framed strictly as a signal
                  for a human reviewer, never a pass/fail verdict: this score
                  and this summary are computed independently, and neither
                  ever affects the other.
              ================================================== */}

              {proctoringEverEnabled && (
                <div className="bg-[#f7f8fc] border border-[#dfe2eb] rounded-2xl p-5 mb-6">
                  <div className="flex items-center gap-2.5 mb-3">
                    <div className="w-8 h-8 rounded-xl bg-[#eef1ff] text-[#00236f] flex items-center justify-center">
                      <ShieldCheck size={17} strokeWidth={2} />
                    </div>
                    <div>
                      <h3 className="text-sm font-bold text-[#00236f]">Webcam Integrity Summary</h3>
                      <p className="text-[9px] text-[#858b98] font-mono mt-0.5 uppercase tracking-wide">
                        Audit signal, not a score
                      </p>
                    </div>
                  </div>

                  {totalViolations === 0 ? (
                    <p className="text-[11px] text-[#005147] font-mono font-semibold">
                      No integrity signals recorded this session.
                    </p>
                  ) : (
                    <>
                      <p className="text-[11px] text-[#555d6d] leading-6 font-mono mb-3">
                        <strong className="text-[#904d00]">{totalViolations}</strong> integrity
                        signal{totalViolations === 1 ? '' : 's'} recorded this session. These are raw
                        client-reported events for a human reviewer to weigh -- not an automatic
                        pass/fail, and they had no effect on the diagnostic score above.
                      </p>
                      <ul className="space-y-1.5 text-[10px] text-[#252c3c] font-mono">
                        {Object.entries(violationCounts).map(([type, count]) => (
                          <li key={type} className="flex items-center justify-between gap-3">
                            <span>{VIOLATION_LABELS[type] || type}</span>
                            <span className="font-bold text-[#904d00]">{count}</span>
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>
              )}

              {/* ==================================================
                  BOTTOM ACTIONS
              ================================================== */}

              <div className="pt-5 border-t border-[#edf0f5] flex flex-col lg:flex-row items-stretch lg:items-center justify-between gap-3">

                <div className="flex flex-col sm:flex-row gap-2">

                  <button
                    type="button"
                    onClick={() => setReviewIndex(0)}
                    className="px-4 py-2.5 rounded-xl border border-[#dfe2eb] text-[#555d6d] hover:bg-[#f5f6fa] text-[10px] font-mono font-semibold transition-all cursor-pointer"
                  >
                    Review Answers
                  </button>

                  <button
                    type="button"
                    onClick={() => router.push('/register')}
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
