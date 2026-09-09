'use client';

import { useRef, useState } from 'react';
import { useAuthStore } from '@/store/useAuthStore';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import { learning } from '@/lib/api/client';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Panel from '@/components/ui/Panel';

/**
 * The real "upload a document, get a grounded quiz back" flow --
 * POST /learning/quiz/generate (backend/routes/learning_content.py ->
 * services/quiz_generator.py). AI-generated (Gemini) when a real model key
 * is configured, with every answer's source_excerpt checked to be a literal
 * substring of the uploaded document; falls back to a deterministic,
 * source-wording-preserving extractive generator otherwise. Shared between
 * /quiz (its dedicated home) and the Academy hub's teaser link, so the two
 * surfaces can never drift out of sync with each other.
 */
export default function QuizGeneratorPanel({ onGenerated }) {
  const player = useAuthStore((s) => s.player);
  const { t, language } = useLanguage();
  const [quiz, setQuiz] = useState(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState('');

  async function createQuiz(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const file = form.get('learning_file');
    if (!(file instanceof File) || !file.size) {
      setError(t('academy.chooseFileError'));
      return;
    }
    setWorking(true);
    setError('');
    setQuiz(null);
    try {
      const result = await learning.generateQuiz({
        playerId: player.player_id,
        title: form.get('title'),
        difficulty: form.get('difficulty'),
        language: form.get('language'),
        questionCount: Number(form.get('question_count')),
        file,
      });
      setQuiz(result);
      onGenerated?.(result);
    } catch (cause) {
      setError(cause.message);
    } finally {
      setWorking(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <form onSubmit={createQuiz} className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Input id="quiz-title" name="title" label={t('academy.quizTitleLabel')} required defaultValue="My learning material quiz" />
        <Input
          key={language}
          id="quiz-language"
          name="language"
          label={t('academy.outputLanguageLabel')}
          required
          defaultValue={language === 'hi' ? 'Hindi' : 'English'}
        />
        <label className="flex flex-col gap-1.5">
          <span className="font-sans text-xs font-semibold text-[#444651]">{t('academy.difficultyLabel')}</span>
          <select
            name="difficulty"
            defaultValue="mixed"
            className="bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]"
          >
            <option value="foundation">{t('academy.difficultyFoundation')}</option>
            <option value="intermediate">{t('academy.difficultyIntermediate')}</option>
            <option value="advanced">{t('academy.difficultyAdvanced')}</option>
            <option value="mixed">{t('academy.difficultyMixed')}</option>
          </select>
        </label>
        <Input id="question-count" name="question_count" label={t('academy.questionCountLabel')} type="number" min="3" max="10" defaultValue="5" />
        <label className="md:col-span-2 flex flex-col gap-1.5">
          <span className="font-sans text-xs font-semibold text-[#444651]">{t('academy.learningMaterialLabel')}</span>
          <input
            name="learning_file"
            type="file"
            required
            accept=".txt,.md,.pdf,.docx"
            className="bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 file:bg-[#00236f] file:text-white file:border-0 file:rounded-md file:px-3 file:py-1.5 file:mr-3"
          />
        </label>
        <div className="md:col-span-2">
          <Button type="submit" variant="accent" disabled={working}>
            {working ? t('academy.generatingButton') : t('academy.generateQuizButton')}
          </Button>
        </div>
      </form>

      {error && (
        <p className="font-sans text-sm text-[#b3261e] bg-[#fce8e6] border border-[#f5c6c2] rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {quiz && <QuizPreview quiz={quiz} onScored={onGenerated} />}
    </div>
  );
}

const DIFFICULTY_TONE = { easy: 'success', medium: 'warning', hard: 'danger' };

export function QuizPreview({ quiz, onScored }) {
  const { t } = useLanguage();
  const [mode, setMode] = useState('preview');

  return (
    <Panel>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="font-sans text-base font-bold text-[#00236f]">{quiz.title}</h2>
          <Badge tone="accent">{quiz.generation_mode}</Badge>
          <Badge tone="default">{quiz.language}</Badge>
        </div>
        {quiz.quiz_id && (
          <div className="flex items-center gap-1 bg-[#f2f3ff] rounded-lg p-1">
            <button
              type="button"
              onClick={() => setMode('preview')}
              className={`font-mono text-[10px] uppercase tracking-wider px-2.5 py-1.5 rounded-md ${mode === 'preview' ? 'bg-white text-[#00236f] shadow-sm' : 'text-[#757682]'}`}
            >
              {t('quizGeneratorPage.previewTab')}
            </button>
            <button
              type="button"
              onClick={() => setMode('take')}
              className={`font-mono text-[10px] uppercase tracking-wider px-2.5 py-1.5 rounded-md ${mode === 'take' ? 'bg-white text-[#00236f] shadow-sm' : 'text-[#757682]'}`}
            >
              {t('quizGeneratorPage.takeQuizTab')}
            </button>
          </div>
        )}
      </div>

      {mode === 'preview' ? (
        <ol className="flex flex-col gap-5 mt-5">
          {quiz.questions.map((question, questionIndex) => (
            <li key={`${question.question}-${questionIndex}`} className="border border-[#c5c5d3]/40 rounded-lg bg-[#f2f3ff] p-4">
              <div className="flex items-center justify-between gap-2">
                <p className="font-sans text-sm font-semibold text-[#131b2e]">{questionIndex + 1}. {question.question}</p>
                {question.difficulty && (
                  <Badge tone={DIFFICULTY_TONE[question.difficulty] || 'default'}>{question.difficulty}</Badge>
                )}
              </div>
              <ol className="font-sans text-sm text-[#444651] mt-3 grid gap-1">
                {question.options.map((option, optionIndex) => (
                  <li key={option} className={optionIndex === question.answer_index ? 'text-[#00236f] font-medium' : ''}>
                    {String.fromCharCode(65 + optionIndex)}. {option}{optionIndex === question.answer_index ? ' ✓' : ''}
                  </li>
                ))}
              </ol>
              <p className="font-sans text-sm text-[#131b2e] mt-3">{question.explanation}</p>
              <blockquote className="font-sans text-sm text-[#757682] border-l-4 border-[#fe932c] pl-3 mt-2">Source: {question.source_excerpt}</blockquote>
            </li>
          ))}
        </ol>
      ) : (
        <TakeQuizFlow quiz={quiz} onScored={onScored} />
      )}
    </Panel>
  );
}

/**
 * Interactive, scored "take it" mode for a generated quiz -- answers are
 * collected without revealing answer_index, per-question elapsed time is
 * tracked client-side, and POST /learning/quiz/{quiz_id}/submit
 * (services/quiz_scoring.py) returns a real, time+difficulty-weighted
 * score. Deliberately a standalone per-quiz score, not curriculum
 * evidence -- see that endpoint's own docstring for why.
 */
function TakeQuizFlow({ quiz, onScored }) {
  const player = useAuthStore((s) => s.player);
  const { t } = useLanguage();
  const [answers, setAnswers] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const startTimesRef = useRef({});

  function markSeen(questionIndex) {
    if (!(questionIndex in startTimesRef.current)) {
      startTimesRef.current[questionIndex] = Date.now();
    }
  }

  function selectOption(questionIndex, optionIndex) {
    if (result) return;
    setAnswers((prev) => ({ ...prev, [questionIndex]: optionIndex }));
  }

  async function handleSubmit() {
    if (submitting || !quiz.quiz_id) return;
    setSubmitting(true);
    setError('');
    try {
      const payload = Object.entries(answers).map(([questionIndex, selectedIndex]) => {
        const index = Number(questionIndex);
        const startedAt = startTimesRef.current[index];
        return {
          question_index: index,
          selected_index: selectedIndex,
          time_taken_ms: startedAt ? Date.now() - startedAt : null,
        };
      });
      const response = await learning.submitGeneratedQuiz(quiz.quiz_id, player.player_id, payload);
      setResult(response);
      onScored?.(response);
    } catch (cause) {
      setError(cause.message || t('quizGeneratorPage.submitFailed'));
    } finally {
      setSubmitting(false);
    }
  }

  const answeredCount = Object.keys(answers).length;

  if (result) {
    return (
      <div className="mt-5 flex flex-col gap-4">
        <div className="flex flex-wrap items-center gap-3 bg-[#f2f3ff] rounded-lg p-4">
          <div className="text-2xl font-bold text-[#00236f] font-mono">{result.weighted_score}%</div>
          <div className="font-sans text-sm text-[#444651]">
            {result.correct_count}/{result.total_questions} {t('quizGeneratorPage.correctOf')}
          </div>
        </div>
        <p className="font-mono text-[10px] text-[#757682]">{result.scoring_note}</p>
        <div className="flex flex-wrap gap-2">
          {Object.entries(result.by_difficulty).map(([difficulty, stats]) => (
            <Badge key={difficulty} tone={DIFFICULTY_TONE[difficulty] || 'default'}>
              {difficulty}: {stats.correct}/{stats.count}
            </Badge>
          ))}
        </div>
        <Button
          variant="ghost"
          onClick={() => {
            setResult(null);
            setAnswers({});
            startTimesRef.current = {};
          }}
        >
          {t('quizGeneratorPage.retakeButton')}
        </Button>
      </div>
    );
  }

  return (
    <div className="mt-5 flex flex-col gap-4">
      <ol className="flex flex-col gap-4">
        {quiz.questions.map((question, questionIndex) => (
          <li
            key={`${question.question}-${questionIndex}`}
            className="border border-[#c5c5d3]/40 rounded-lg bg-white p-4"
            onFocus={() => markSeen(questionIndex)}
            onMouseEnter={() => markSeen(questionIndex)}
          >
            <div className="flex items-center justify-between gap-2">
              <p className="font-sans text-sm font-semibold text-[#131b2e]">{questionIndex + 1}. {question.question}</p>
              {question.difficulty && (
                <Badge tone={DIFFICULTY_TONE[question.difficulty] || 'default'}>{question.difficulty}</Badge>
              )}
            </div>
            <div className="grid gap-1.5 mt-3">
              {question.options.map((option, optionIndex) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => selectOption(questionIndex, optionIndex)}
                  className={`text-left font-sans text-sm rounded-lg border px-3 py-2 transition-colors ${
                    answers[questionIndex] === optionIndex
                      ? 'bg-[#f2f3ff] border-[#00236f]/50 text-[#00236f] font-medium'
                      : 'bg-white border-[#c5c5d3]/40 hover:border-[#00236f]/30 text-[#444651]'
                  }`}
                >
                  {String.fromCharCode(65 + optionIndex)}. {option}
                </button>
              ))}
            </div>
          </li>
        ))}
      </ol>

      {error && (
        <p className="font-sans text-sm text-[#b3261e] bg-[#fce8e6] border border-[#f5c6c2] rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      <Button variant="accent" onClick={handleSubmit} disabled={submitting || !answeredCount}>
        {submitting
          ? t('quizGeneratorPage.scoring')
          : `${t('quizGeneratorPage.submitAnswersButton')} (${answeredCount}/${quiz.questions.length} ${t('quizGeneratorPage.answeredOf')})`}
      </Button>
    </div>
  );
}
