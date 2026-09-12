'use client';

import { useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { FileQuestion, Library } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import { learning } from '@/lib/api/client';
import QuizGeneratorPanel, { QuizPreview } from '@/components/QuizGeneratorPanel';
import FixedQuizPanel from '@/components/FixedQuizPanel';
import Badge from '@/components/ui/Badge';
import Panel from '@/components/ui/Panel';

// Review-status badges below are plain hardcoded English -- not yet
// translated into the other 10 UI languages, same honesty convention as
// this project's other documented pending items (see app/sampling-lab/page.jsx).
const REVIEW_STATUS_LABEL = {
  private: 'Private',
  pending_review: 'Pending review',
  published: 'Published',
  rejected: 'Rejected',
};

const REVIEW_STATUS_TONE = {
  private: 'default',
  pending_review: 'warning',
  published: 'success',
  rejected: 'danger',
};

// The real feature this nav tab is named for: POST /learning/quiz/generate
// (backend/routes/learning_content.py -> services/quiz_generator.py), a
// genuinely AI-grounded (or, without a configured model key, a
// deterministic source-preserving extractive fallback) quiz generator over
// an uploaded document. An earlier version of this page was a fully
// hardcoded mockup with fake questions, a fake PDF viewer, and zero backend
// calls -- QuizGeneratorPanel is the same shared component the Academy hub
// links out to, so this page and that one can never drift apart.
export default function SourceQuizGeneratorPage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);
  const { t } = useLanguage();
  const [mode, setMode] = useState('upload');
  const [openQuiz, setOpenQuiz] = useState(null);
  const [openError, setOpenError] = useState('');

  const {
    data: historyData,
    isLoading: historyLoading,
    isError: historyErrored,
    refetch: refetchHistory,
  } = useQuery({
    queryKey: ['quiz-history', player?.player_id],
    queryFn: () => learning.listQuizzes(player.player_id),
    enabled: ready && !!player,
  });

  const {
    data: libraryData,
    isLoading: libraryLoading,
    isError: libraryErrored,
  } = useQuery({
    queryKey: ['quiz-library'],
    queryFn: () => learning.getQuizLibrary(),
    enabled: ready && !!player && mode === 'library',
  });

  const submitForReview = useMutation({
    mutationFn: (quizId) => learning.submitQuizForReview(quizId, player.player_id),
    onSuccess: () => refetchHistory(),
  });

  async function openFromHistory(quizId) {
    setOpenError('');
    try {
      const quiz = await learning.getQuiz(quizId, player.player_id);
      setOpenQuiz(quiz);
    } catch (cause) {
      setOpenError(cause.message);
    }
  }

  async function openFromLibrary(quizId) {
    setOpenError('');
    try {
      const quiz = await learning.getQuiz(quizId, player.player_id);
      setOpenQuiz(quiz);
    } catch (cause) {
      setOpenError(cause.message);
    }
  }

  if (!ready) return null;

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-5">
      <div>
        <div className="flex items-center gap-2">
          <FileQuestion className="text-[#00236f]" size={20} aria-hidden="true" />
          <h1 className="font-sans text-lg font-bold text-[#00236f]">{t('quizGeneratorPage.heading')}</h1>
        </div>
        <p className="font-sans text-sm text-[#757682] mt-2 max-w-2xl">{t('quizGeneratorPage.subtitle')}</p>
        {/* Not yet translated into the other 10 UI languages -- same honesty
            convention as this project's other documented pending items (see
            app/sampling-lab/page.jsx). Kept separate from the translated
            subtitle above rather than editing that key, so the other 10
            languages' existing translations don't go stale. */}
        <p className="font-mono text-[10px] text-[#8a8f9d] mt-1 max-w-2xl">
          Also accepts PPTX slides, VTT/SRT/plain transcripts, and audio or video files (MP4, MOV,
          WEBM, MP3, WAV, M4A, up to 60 MB / 10 minutes) -- speech is transcribed automatically.
        </p>
      </div>

      <div className="flex items-center gap-1 bg-[#f2f3ff] rounded-lg p-1 self-start">
        <button
          type="button"
          onClick={() => setMode('upload')}
          className={`font-mono text-[11px] uppercase tracking-wider px-3 py-2 rounded-md ${mode === 'upload' ? 'bg-white text-[#00236f] shadow-sm' : 'text-[#757682]'}`}
        >
          {t('quizGeneratorPage.modeUpload')}
        </button>
        <button
          type="button"
          onClick={() => setMode('fixed')}
          className={`font-mono text-[11px] uppercase tracking-wider px-3 py-2 rounded-md ${mode === 'fixed' ? 'bg-white text-[#00236f] shadow-sm' : 'text-[#757682]'}`}
        >
          {t('quizGeneratorPage.modeFixed')}
        </button>
        <button
          type="button"
          onClick={() => setMode('library')}
          className={`font-mono text-[11px] uppercase tracking-wider px-3 py-2 rounded-md flex items-center gap-1.5 ${mode === 'library' ? 'bg-white text-[#00236f] shadow-sm' : 'text-[#757682]'}`}
        >
          <Library size={13} aria-hidden="true" />
          Library
        </button>
      </div>

      {mode === 'upload' ? (
        <Panel variant="accent">
          <QuizGeneratorPanel onGenerated={() => refetchHistory()} />
        </Panel>
      ) : mode === 'fixed' ? (
        <FixedQuizPanel />
      ) : (
        <Panel>
          <h2 className="font-sans text-base font-bold text-[#131b2e] mb-1">Published Quiz Library</h2>
          <p className="font-sans text-xs text-[#757682] mb-3">
            Quizzes another learner generated and a trainer approved for everyone -- not yet
            translated into the other 10 UI languages.
          </p>
          {libraryLoading ? (
            <p className="font-sans text-sm text-[#757682]">…</p>
          ) : libraryErrored ? (
            <p className="font-sans text-sm text-[#b3261e]">Could not load the quiz library.</p>
          ) : !libraryData?.quizzes?.length ? (
            <p className="font-sans text-sm text-[#757682]">
              No published quizzes yet -- ask a trainer to approve one from the review queue.
            </p>
          ) : (
            <ul className="flex flex-col gap-2">
              {libraryData.quizzes.map((item) => (
                <li key={item.quiz_id}>
                  <button
                    type="button"
                    onClick={() => openFromLibrary(item.quiz_id)}
                    className="w-full flex flex-wrap items-center justify-between gap-2 border border-[#c5c5d3]/30 rounded-lg px-3 py-2 text-left hover:border-[#00236f]/30"
                  >
                    <span className="font-sans text-sm font-semibold text-[#131b2e]">{item.title}</span>
                    <div className="flex items-center gap-2">
                      <Badge tone="default">{item.difficulty}</Badge>
                      <Badge tone="accent">{item.generation_mode}</Badge>
                      <span className="font-mono text-[10px] text-[#757682]">
                        {item.question_count} questions
                      </span>
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      )}

      {openError && (
        <p className="font-sans text-sm text-[#b3261e] bg-[#fce8e6] border border-[#f5c6c2] rounded-lg px-3 py-2">
          {openError}
        </p>
      )}
      {openQuiz && <QuizPreview quiz={openQuiz} onScored={() => refetchHistory()} />}

      <Panel>
        <h2 className="font-sans text-base font-bold text-[#131b2e] mb-3">{t('quizGeneratorPage.historyHeading')}</h2>
        {historyLoading ? (
          <p className="font-sans text-sm text-[#757682]">…</p>
        ) : historyErrored ? (
          <p className="font-sans text-sm text-[#b3261e]">{t('quizGeneratorPage.historyLoadFailed')}</p>
        ) : !historyData?.quizzes?.length ? (
          <p className="font-sans text-sm text-[#757682]">{t('quizGeneratorPage.historyEmpty')}</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {historyData.quizzes.map((item) => (
              <li
                key={item.quiz_id || item.id || `${item.title}-${item.created_at}`}
                className="flex flex-wrap items-center justify-between gap-2 border border-[#c5c5d3]/30 rounded-lg px-3 py-2"
              >
                <button
                  type="button"
                  onClick={() => item.quiz_id && openFromHistory(item.quiz_id)}
                  className="flex-1 min-w-0 flex flex-wrap items-center justify-between gap-2 text-left cursor-pointer"
                >
                  <span className="font-sans text-sm font-semibold text-[#131b2e]">{item.title}</span>
                  <div className="flex items-center gap-2">
                    <Badge tone="default">{item.difficulty}</Badge>
                    <Badge tone="accent">{item.generation_mode}</Badge>
                    <span className="font-mono text-[10px] text-[#757682]">
                      {item.question_count} {t('quizGeneratorPage.questionsSuffix')}
                    </span>
                    {item.best_score != null && (
                      <Badge tone="success">
                        {t('quizGeneratorPage.bestScore')}: {item.best_score}%
                      </Badge>
                    )}
                    {item.review_status && item.review_status !== 'private' && (
                      <Badge tone={REVIEW_STATUS_TONE[item.review_status] || 'default'}>
                        {REVIEW_STATUS_LABEL[item.review_status] || item.review_status}
                      </Badge>
                    )}
                  </div>
                </button>
                {(item.review_status === 'private' || item.review_status === 'rejected') && (
                  <button
                    type="button"
                    onClick={() => submitForReview.mutate(item.quiz_id)}
                    disabled={submitForReview.isPending}
                    className="shrink-0 font-mono text-[10px] uppercase tracking-wide px-2.5 py-1.5 rounded-md border border-[#00236f]/30 text-[#00236f] hover:bg-[#f2f3ff] disabled:opacity-50 cursor-pointer"
                  >
                    {item.review_status === 'rejected' ? 'Resubmit for review' : 'Submit for review'}
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
