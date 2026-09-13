'use client';

// Real trainer/content-reviewer approval queue for AI-generated quizzes
// (backend/routes/quiz_review.py) -- a learner submits their private quiz
// for review, and only a content_reviewer/trainer-permissioned principal
// can approve it into the shared Quiz Library (see app/quiz/page.jsx's
// "Library" tab) or reject it back to the creator. Reached by direct URL
// like /admin, rather than a main-nav tab -- an admin-facing area, not part
// of the primary learner pitch.
//
// Not yet translated into the other 10 UI languages -- plain English, same
// honesty convention as this project's other documented pending items (see
// app/sampling-lab/page.jsx).

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ClipboardCheck, CheckCircle2, XCircle, Pencil, Plus, Trash2 } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { learning } from '@/lib/api/client';
import Badge from '@/components/ui/Badge';
import Panel from '@/components/ui/Panel';

const DIFFICULTY_TONE = { foundation: 'success', intermediate: 'warning', advanced: 'danger', mixed: 'accent' };

export default function TrainerReviewPage() {
  const { ready } = useRequireAuth();
  const queryClient = useQueryClient();
  const [notesByQuiz, setNotesByQuiz] = useState({});
  const [expandedQuiz, setExpandedQuiz] = useState(null);
  // quiz_id -> a working copy of that quiz's questions while a reviewer is
  // editing them (null/absent means "not currently editing that quiz").
  // source_excerpt is deliberately never part of this editable state -- see
  // lib/api/client.js's reviewQuiz() comment for why it can't be re-verified.
  const [editedQuestionsByQuiz, setEditedQuestionsByQuiz] = useState({});
  const [editError, setEditError] = useState('');

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['quiz-review-queue'],
    queryFn: () => learning.getReviewQueue(),
    enabled: ready,
  });

  const decide = useMutation({
    mutationFn: ({ quizId, decision, notes, editedQuestions }) =>
      learning.reviewQuiz(quizId, decision, notes, editedQuestions),
    onSuccess: (_data, variables) => {
      refetch();
      queryClient.invalidateQueries({ queryKey: ['quiz-library'] });
      setEditedQuestionsByQuiz((prev) => {
        const next = { ...prev };
        delete next[variables.quizId];
        return next;
      });
      setEditError('');
    },
    onError: (cause) => setEditError(cause.message || 'Could not save this decision.'),
  });

  function startEditing(quiz) {
    setEditedQuestionsByQuiz((prev) => ({
      ...prev,
      // Deep clone so edits never mutate the query cache's own copy.
      [quiz.quiz_id]: JSON.parse(JSON.stringify(quiz.questions || [])),
    }));
  }

  function stopEditing(quizId) {
    setEditedQuestionsByQuiz((prev) => {
      const next = { ...prev };
      delete next[quizId];
      return next;
    });
  }

  function updateQuestionField(quizId, questionIndex, field, value) {
    setEditedQuestionsByQuiz((prev) => {
      const questions = [...prev[quizId]];
      questions[questionIndex] = { ...questions[questionIndex], [field]: value };
      return { ...prev, [quizId]: questions };
    });
  }

  function updateOption(quizId, questionIndex, optionIndex, value) {
    setEditedQuestionsByQuiz((prev) => {
      const questions = [...prev[quizId]];
      const options = [...questions[questionIndex].options];
      options[optionIndex] = value;
      questions[questionIndex] = { ...questions[questionIndex], options };
      return { ...prev, [quizId]: questions };
    });
  }

  function addOption(quizId, questionIndex) {
    setEditedQuestionsByQuiz((prev) => {
      const questions = [...prev[quizId]];
      const question = questions[questionIndex];
      if (question.options.length >= 6) return prev;
      questions[questionIndex] = { ...question, options: [...question.options, ''] };
      return { ...prev, [quizId]: questions };
    });
  }

  function removeOption(quizId, questionIndex, optionIndex) {
    setEditedQuestionsByQuiz((prev) => {
      const questions = [...prev[quizId]];
      const question = questions[questionIndex];
      if (question.options.length <= 2) return prev;
      const options = question.options.filter((_, i) => i !== optionIndex);
      // Keep pointing at the same correct answer where possible; if the
      // removed option WAS the answer, fall back to the first option
      // rather than silently leaving an out-of-range index.
      let answerIndex = question.answer_index;
      if (optionIndex === question.answer_index) answerIndex = 0;
      else if (optionIndex < question.answer_index) answerIndex -= 1;
      questions[questionIndex] = { ...question, options, answer_index: answerIndex };
      return { ...prev, [quizId]: questions };
    });
  }

  function approveWithEdits(quiz) {
    const edited = editedQuestionsByQuiz[quiz.quiz_id];
    // Only the fields the backend accepts an edit for -- source_excerpt is
    // taken from the ORIGINAL question, never the (unmodifiable) edit state.
    const payload = edited.map((question, index) => ({
      question: question.question,
      options: question.options,
      answer_index: question.answer_index,
      explanation: question.explanation,
      source_excerpt: quiz.questions[index].source_excerpt,
    }));
    decide.mutate({
      quizId: quiz.quiz_id,
      decision: 'approve',
      notes: notesByQuiz[quiz.quiz_id],
      editedQuestions: payload,
    });
  }

  if (!ready) return null;

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-5">
      <div>
        <div className="flex items-center gap-2">
          <ClipboardCheck className="text-[#00236f]" size={20} aria-hidden="true" />
          <h1 className="font-sans text-lg font-bold text-[#00236f]">Trainer Review Queue</h1>
        </div>
        <p className="font-sans text-sm text-[#757682] mt-2 max-w-2xl">
          AI-generated quizzes a learner has submitted for publication. Approving one adds it to
          the shared Quiz Library for every learner; rejecting it sends it back to the creator,
          who can edit their source material and resubmit.
        </p>
      </div>

      {isLoading ? (
        <Panel><p className="font-sans text-sm text-[#757682]">…</p></Panel>
      ) : isError ? (
        <Panel><p className="font-sans text-sm text-[#b3261e]">Could not load the review queue.</p></Panel>
      ) : !data?.quizzes?.length ? (
        <Panel><p className="font-sans text-sm text-[#757682]">Nothing is waiting for review right now.</p></Panel>
      ) : (
        data.quizzes.map((quiz) => {
          const isExpanded = expandedQuiz === quiz.quiz_id;
          const editedQuestions = editedQuestionsByQuiz[quiz.quiz_id];
          const isEditing = Boolean(editedQuestions);
          return (
            <Panel key={quiz.quiz_id}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="font-sans text-base font-bold text-[#131b2e]">{quiz.title}</h2>
                  <Badge tone="accent">{quiz.generation_mode}</Badge>
                  <Badge tone="default">{quiz.language}</Badge>
                  <Badge tone="default">{quiz.questions?.length ?? 0} questions</Badge>
                  {isEditing && <Badge tone="warning">Editing</Badge>}
                </div>
                <div className="flex items-center gap-3">
                  {!isEditing && (
                    <button
                      type="button"
                      onClick={() => startEditing(quiz)}
                      className="flex items-center gap-1 font-mono text-[10px] uppercase tracking-wide text-[#00236f] underline cursor-pointer"
                    >
                      <Pencil size={11} /> Edit questions
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setExpandedQuiz(isExpanded ? null : quiz.quiz_id)}
                    className="font-mono text-[10px] uppercase tracking-wide text-[#00236f] underline cursor-pointer"
                  >
                    {isExpanded ? 'Hide questions' : 'Read questions'}
                  </button>
                </div>
              </div>

              {isExpanded && !isEditing && (
                <ol className="flex flex-col gap-4 mt-4">
                  {(quiz.questions || []).map((question, questionIndex) => (
                    <li
                      key={`${question.question}-${questionIndex}`}
                      className="border border-[#c5c5d3]/40 rounded-lg bg-[#f2f3ff] p-4"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="font-sans text-sm font-semibold text-[#131b2e]">
                          {questionIndex + 1}. {question.question}
                        </p>
                        {question.difficulty && (
                          <Badge tone={DIFFICULTY_TONE[question.difficulty] || 'default'}>{question.difficulty}</Badge>
                        )}
                      </div>
                      <ol className="font-sans text-sm text-[#444651] mt-3 grid gap-1">
                        {(question.options || []).map((option, optionIndex) => (
                          <li
                            key={option}
                            className={optionIndex === question.answer_index ? 'text-[#00236f] font-medium' : ''}
                          >
                            {String.fromCharCode(65 + optionIndex)}. {option}
                            {optionIndex === question.answer_index ? ' ✓' : ''}
                          </li>
                        ))}
                      </ol>
                      {question.explanation && (
                        <p className="font-sans text-sm text-[#131b2e] mt-3">{question.explanation}</p>
                      )}
                      {question.source_excerpt && (
                        <blockquote className="font-sans text-sm text-[#757682] border-l-4 border-[#fe932c] pl-3 mt-2">
                          Source: {question.source_excerpt}
                        </blockquote>
                      )}
                    </li>
                  ))}
                </ol>
              )}

              {isEditing && (
                <ol className="flex flex-col gap-4 mt-4">
                  {editedQuestions.map((question, questionIndex) => (
                    <li
                      key={questionIndex}
                      className="border border-[#00236f]/30 rounded-lg bg-white p-4"
                    >
                      <label className="font-mono text-[10px] uppercase tracking-wide text-[#757682]">
                        Question {questionIndex + 1}
                      </label>
                      <textarea
                        rows={2}
                        value={question.question}
                        onChange={(e) => updateQuestionField(quiz.quiz_id, questionIndex, 'question', e.target.value)}
                        className="w-full text-sm font-sans border border-[#c5c5d3]/50 rounded-lg px-3 py-2 mt-1 outline-none focus:border-[#00236f]"
                      />
                      <div className="flex flex-col gap-1.5 mt-2">
                        {question.options.map((option, optionIndex) => (
                          <div key={optionIndex} className="flex items-center gap-2">
                            <input
                              type="radio"
                              name={`answer-${quiz.quiz_id}-${questionIndex}`}
                              checked={question.answer_index === optionIndex}
                              onChange={() => updateQuestionField(quiz.quiz_id, questionIndex, 'answer_index', optionIndex)}
                              title="Mark as the correct answer"
                            />
                            <input
                              type="text"
                              value={option}
                              onChange={(e) => updateOption(quiz.quiz_id, questionIndex, optionIndex, e.target.value)}
                              className="flex-1 text-sm font-sans border border-[#c5c5d3]/50 rounded-lg px-2.5 py-1.5 outline-none focus:border-[#00236f]"
                            />
                            <button
                              type="button"
                              disabled={question.options.length <= 2}
                              onClick={() => removeOption(quiz.quiz_id, questionIndex, optionIndex)}
                              className="text-[#b3261e] disabled:opacity-30 cursor-pointer disabled:cursor-default"
                              title="Remove this option"
                            >
                              <Trash2 size={14} />
                            </button>
                          </div>
                        ))}
                        <button
                          type="button"
                          disabled={question.options.length >= 6}
                          onClick={() => addOption(quiz.quiz_id, questionIndex)}
                          className="self-start flex items-center gap-1 font-mono text-[10px] uppercase text-[#00236f] disabled:opacity-30 cursor-pointer disabled:cursor-default mt-1"
                        >
                          <Plus size={12} /> Add option
                        </button>
                      </div>
                      <label className="font-mono text-[10px] uppercase tracking-wide text-[#757682] mt-3 block">
                        Explanation
                      </label>
                      <textarea
                        rows={2}
                        value={question.explanation}
                        onChange={(e) => updateQuestionField(quiz.quiz_id, questionIndex, 'explanation', e.target.value)}
                        className="w-full text-sm font-sans border border-[#c5c5d3]/50 rounded-lg px-3 py-2 mt-1 outline-none focus:border-[#00236f]"
                      />
                      <blockquote className="font-sans text-xs text-[#8a8f9d] border-l-4 border-[#c5c5d3] pl-3 mt-2">
                        Source (not editable -- can't be re-verified against the original material):{' '}
                        {quiz.questions[questionIndex]?.source_excerpt}
                      </blockquote>
                    </li>
                  ))}
                  <button
                    type="button"
                    onClick={() => stopEditing(quiz.quiz_id)}
                    className="self-start font-mono text-[10px] uppercase tracking-wide text-[#757682] underline cursor-pointer"
                  >
                    Discard edits
                  </button>
                </ol>
              )}

              {editError && <p className="font-sans text-xs text-[#b3261e] mt-3">{editError}</p>}

              <div className="mt-4 pt-4 border-t border-[#c5c5d3]/30 flex flex-col gap-2">
                <label className="font-mono text-[10px] uppercase tracking-wide text-[#757682]">
                  Notes to the creator (optional)
                </label>
                <textarea
                  rows={2}
                  value={notesByQuiz[quiz.quiz_id] || ''}
                  onChange={(e) => setNotesByQuiz((prev) => ({ ...prev, [quiz.quiz_id]: e.target.value }))}
                  className="w-full text-sm font-sans border border-[#c5c5d3]/50 rounded-lg px-3 py-2 outline-none focus:border-[#00236f]"
                  placeholder="e.g. Question 3's distractors are too obviously wrong -- tighten before resubmitting."
                />
                <div className="flex items-center gap-2 justify-end">
                  <button
                    type="button"
                    disabled={decide.isPending}
                    onClick={() =>
                      decide.mutate({ quizId: quiz.quiz_id, decision: 'reject', notes: notesByQuiz[quiz.quiz_id] })
                    }
                    className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wide px-3 py-2 rounded-md border border-[#b3261e]/40 text-[#b3261e] hover:bg-[#fce8e6] disabled:opacity-50 cursor-pointer"
                  >
                    <XCircle size={14} /> Reject
                  </button>
                  <button
                    type="button"
                    disabled={decide.isPending}
                    onClick={() =>
                      isEditing
                        ? approveWithEdits(quiz)
                        : decide.mutate({ quizId: quiz.quiz_id, decision: 'approve', notes: notesByQuiz[quiz.quiz_id] })
                    }
                    className="flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-wide px-3 py-2 rounded-md bg-[#1a7f4b] text-white hover:bg-[#146239] disabled:opacity-50 cursor-pointer"
                  >
                    <CheckCircle2 size={14} /> {isEditing ? 'Approve edited version' : 'Approve & Publish'}
                  </button>
                </div>
              </div>
            </Panel>
          );
        })
      )}
    </div>
  );
}
