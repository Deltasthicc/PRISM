'use client';

import { useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useAuthStore } from '@/store/useAuthStore';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import { learning } from '@/lib/api/client';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Panel from '@/components/ui/Panel';

const DIFFICULTY_TONE = { easy: 'success', medium: 'warning', hard: 'danger' };

/**
 * "Fixed question bank" mode for the Source Quiz Generator page -- a real,
 * curated, source-cited quiz (routes/competency_quiz.py, backed by
 * services/hand_authored_questions.py) as an alternative to uploading a
 * document, using the exact same time-weighted server-side grading
 * (services/quiz_scoring.py) the upload-and-generate flow's "Take quiz"
 * mode uses. Not a second implementation of scoring -- both paths already
 * shared the same backend algorithm before this panel existed.
 */
export default function FixedQuizPanel() {
  const player = useAuthStore((s) => s.player);
  const { t } = useLanguage();
  const [topicId, setTopicId] = useState('');
  const [count, setCount] = useState(5);
  const [session, setSession] = useState(null); // { questions, attemptId, topicId, topicLabel }
  const [answers, setAnswers] = useState({});
  const [starting, setStarting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const startTimesRef = useRef({});

  const {
    data: topicsData,
    isLoading: topicsLoading,
    isError: topicsErrored,
  } = useQuery({
    queryKey: ['competency-quiz-topics'],
    queryFn: () => learning.getCompetencyQuizTopics(),
  });

  const topics = topicsData || [];

  async function handleStart() {
    if (!topicId || starting) return;
    setStarting(true);
    setError('');
    setResult(null);
    setAnswers({});
    startTimesRef.current = {};
    try {
      const response = await learning.getCompetencyQuizQuestions(topicId, count);
      const topic = topics.find((item) => item.topic_id === topicId);
      setSession({
        questions: response.questions,
        attemptId: response.attempt_id,
        topicId,
        topicLabel: topic?.label || response.label,
      });
    } catch (cause) {
      setError(cause.message);
    } finally {
      setStarting(false);
    }
  }

  function markSeen(itemId) {
    if (!(itemId in startTimesRef.current)) {
      startTimesRef.current[itemId] = Date.now();
    }
  }

  function selectOption(itemId, optionIndex) {
    if (result) return;
    setAnswers((prev) => ({ ...prev, [itemId]: optionIndex }));
  }

  function setTextAnswer(itemId, text) {
    if (result) return;
    setAnswers((prev) => {
      const next = { ...prev };
      if (text.trim()) next[itemId] = text;
      else delete next[itemId];
      return next;
    });
  }

  async function handleSubmit() {
    if (!session || submitting) return;
    setSubmitting(true);
    setError('');
    try {
      const payload = session.questions.map((question) => {
        const startedAt = startTimesRef.current[question.item_id];
        const timeTakenMs = startedAt ? Date.now() - startedAt : null;
        return question.question_type === 'fill_in_blank'
          ? { item_id: question.item_id, answer_text: answers[question.item_id], time_taken_ms: timeTakenMs }
          : { item_id: question.item_id, selected_index: answers[question.item_id], time_taken_ms: timeTakenMs };
      });
      const response = await learning.submitCompetencyQuiz(
        session.attemptId,
        session.topicId,
        payload,
        player.player_id
      );
      setResult(response);
    } catch (cause) {
      setError(cause.message || t('quizGeneratorPage.submitFailed'));
    } finally {
      setSubmitting(false);
    }
  }

  function reset() {
    setSession(null);
    setAnswers({});
    setResult(null);
    setError('');
  }

  const answeredCount = session ? Object.keys(answers).length : 0;
  const allAnswered = session ? answeredCount === session.questions.length : false;

  if (!session) {
    return (
      <div className="flex flex-col gap-3">
        <p className="font-sans text-sm text-[#444651]">{t('quizGeneratorPage.fixedIntro')}</p>
        {topicsLoading ? (
          <p className="font-sans text-sm text-[#757682]">{t('quizGeneratorPage.loadingTopics')}</p>
        ) : topicsErrored ? (
          <p className="font-sans text-sm text-[#b3261e]">{t('quizGeneratorPage.loadTopicsFailed')}</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 items-end">
            <label className="flex flex-col gap-1.5 md:col-span-2">
              <span className="font-sans text-xs font-semibold text-[#444651]">{t('quizGeneratorPage.topicLabel')}</span>
              <select
                value={topicId}
                onChange={(e) => setTopicId(e.target.value)}
                className="bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]"
              >
                <option value="" disabled>
                  {t('quizGeneratorPage.topicLabel')}
                </option>
                {topics.map((topic) => (
                  <option key={topic.topic_id} value={topic.topic_id}>
                    {topic.label} ({topic.question_count})
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1.5">
              <span className="font-sans text-xs font-semibold text-[#444651]">{t('quizGeneratorPage.questionCountLabel')}</span>
              <input
                type="number"
                min={1}
                max={10}
                value={count}
                onChange={(e) => setCount(Number(e.target.value))}
                className="bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]"
              />
            </label>
          </div>
        )}
        {error && (
          <p className="font-sans text-sm text-[#b3261e] bg-[#fce8e6] border border-[#f5c6c2] rounded-lg px-3 py-2">
            {error}
          </p>
        )}
        <div>
          <Button variant="accent" onClick={handleStart} disabled={!topicId || starting}>
            {starting ? '…' : t('quizGeneratorPage.startFixedQuizButton')}
          </Button>
        </div>
      </div>
    );
  }

  if (result) {
    return (
      <Panel>
        <div className="flex flex-wrap items-center gap-3">
          <h2 className="font-sans text-base font-bold text-[#00236f]">{session.topicLabel}</h2>
          <Badge tone="accent">
            {result.correct}/{result.total} {t('quizGeneratorPage.correctOf')}
          </Badge>
          <span className="text-xl font-bold text-[#00236f] font-mono">{result.score_percentage}%</span>
        </div>
        <p className="font-mono text-[10px] text-[#757682] mt-1">{result.ranking_basis}</p>

        <ol className="flex flex-col gap-4 mt-5">
          {result.graded_answers.map((graded, index) => (
            <li
              key={graded.item_id}
              className={`border rounded-lg p-4 ${graded.correct ? 'border-[#b7e1c4] bg-[#f0faf3]' : 'border-[#f5c6c2] bg-[#fef4f3]'}`}
            >
              <p className="font-sans text-sm font-semibold text-[#131b2e]">
                {index + 1}. {session.questions.find((q) => q.item_id === graded.item_id)?.question}
              </p>
              <p className="font-sans text-sm text-[#444651] mt-2">
                {graded.correct
                  ? t('quizGeneratorPage.correctOf')
                  : `${t('quizGeneratorPage.yourScore')}: ${
                      graded.submitted_text ?? (graded.selected_index != null ? String.fromCharCode(65 + graded.selected_index) : '—')
                    } — ${graded.correct_answer_display ?? ''}`}
              </p>
              <p className="font-sans text-sm text-[#757682] mt-2">{graded.explanation}</p>
            </li>
          ))}
        </ol>

        <div className="flex flex-wrap gap-2 mt-4">
          {result.competency_scores.map((score) => (
            <Badge key={score.competency_id} tone="default">
              {score.competency_label}: {score.correct}/{score.total}
            </Badge>
          ))}
        </div>

        <Button variant="ghost" className="mt-4" onClick={reset}>
          {t('quizGeneratorPage.retakeButton')}
        </Button>
      </Panel>
    );
  }

  return (
    <Panel>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-sans text-base font-bold text-[#00236f]">{session.topicLabel}</h2>
        <Badge tone="default">
          {answeredCount}/{session.questions.length} {t('quizGeneratorPage.answeredOf')}
        </Badge>
      </div>

      <ol className="flex flex-col gap-4 mt-5">
        {session.questions.map((question, index) => (
          <li
            key={question.item_id}
            className="border border-[#c5c5d3]/40 rounded-lg bg-white p-4"
            onFocus={() => markSeen(question.item_id)}
            onMouseEnter={() => markSeen(question.item_id)}
          >
            <div className="flex items-center justify-between gap-2">
              <p className="font-sans text-sm font-semibold text-[#131b2e]">{index + 1}. {question.question}</p>
              <Badge tone={DIFFICULTY_TONE[question.difficulty] || 'default'}>{question.difficulty}</Badge>
            </div>
            {question.question_type === 'fill_in_blank' ? (
              <input
                type="text"
                value={answers[question.item_id] || ''}
                onChange={(e) => setTextAnswer(question.item_id, e.target.value)}
                placeholder="Type your answer…"
                className="mt-3 w-full bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]"
              />
            ) : (
              <div className="grid gap-1.5 mt-3">
                {question.options.map((option, optionIndex) => (
                  <button
                    key={option}
                    type="button"
                    onClick={() => selectOption(question.item_id, optionIndex)}
                    className={`text-left font-sans text-sm rounded-lg border px-3 py-2 transition-colors ${
                      answers[question.item_id] === optionIndex
                        ? 'bg-[#f2f3ff] border-[#00236f]/50 text-[#00236f] font-medium'
                        : 'bg-white border-[#c5c5d3]/40 hover:border-[#00236f]/30 text-[#444651]'
                    }`}
                  >
                    {String.fromCharCode(65 + optionIndex)}. {option}
                  </button>
                ))}
              </div>
            )}
          </li>
        ))}
      </ol>

      {error && (
        <p className="font-sans text-sm text-[#b3261e] bg-[#fce8e6] border border-[#f5c6c2] rounded-lg px-3 py-2 mt-4">
          {error}
        </p>
      )}

      <div className="flex gap-2 mt-4">
        <Button variant="accent" onClick={handleSubmit} disabled={submitting || !allAnswered}>
          {submitting ? t('quizGeneratorPage.scoring') : t('quizGeneratorPage.submitAnswersButton')}
        </Button>
        <Button variant="ghost" onClick={reset}>
          {t('quizGeneratorPage.retakeButton')}
        </Button>
      </div>
    </Panel>
  );
}
