'use client';

import { useQuery } from '@tanstack/react-query';
import { FileQuestion } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import { learning } from '@/lib/api/client';
import QuizGeneratorPanel from '@/components/QuizGeneratorPanel';
import Badge from '@/components/ui/Badge';
import Panel from '@/components/ui/Panel';

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

  if (!ready) return null;

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-5">
      <div>
        <div className="flex items-center gap-2">
          <FileQuestion className="text-[#00236f]" size={20} aria-hidden="true" />
          <h1 className="font-sans text-lg font-bold text-[#00236f]">{t('quizGeneratorPage.heading')}</h1>
        </div>
        <p className="font-sans text-sm text-[#757682] mt-2 max-w-2xl">{t('quizGeneratorPage.subtitle')}</p>
      </div>

      <Panel variant="accent">
        <QuizGeneratorPanel onGenerated={() => refetchHistory()} />
      </Panel>

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
                <span className="font-sans text-sm font-semibold text-[#131b2e]">{item.title}</span>
                <div className="flex items-center gap-2">
                  <Badge tone="default">{item.difficulty}</Badge>
                  <Badge tone="accent">{item.generation_mode}</Badge>
                  <span className="font-mono text-[10px] text-[#757682]">
                    {item.question_count} {t('quizGeneratorPage.questionsSuffix')}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}
