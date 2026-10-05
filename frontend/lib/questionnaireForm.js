// Pure helpers for the questionnaire pages (no React, no fetch) so the
// deadline wording and the form -> API mapping can be unit tested.

export const MAX_QUESTIONS = 50;
export const MIN_OPTIONS = 2;
export const MAX_OPTIONS = 6;

export function blankQuestion() {
  return { prompt: '', options: ['', ''], correctIndex: 0 };
}

/** Name of the viewer's timezone, e.g. "Asia/Kolkata"; '' if unavailable. */
export function browserTimeZone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || '';
  } catch {
    return '';
  }
}

/** <input type="datetime-local"> value (local wall time) -> ISO UTC string, or null. */
export function localInputToIso(value) {
  if (!value) return null;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date.toISOString();
}

/** ISO string -> <input type="datetime-local"> value in the viewer's local time. */
export function isoToLocalInput(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  const pad = (n) => String(n).padStart(2, '0');
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}`
  );
}

/** Human-readable absolute date in the viewer's local time, with the zone named. */
export function formatDeadline(iso) {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleString(undefined, {
    dateStyle: 'medium',
    timeStyle: 'short',
    timeZoneName: 'short',
  });
}

/**
 * Plain-language time remaining until `dueIso`, relative to `nowMs`.
 * Past the deadline it says "Closed"; the server remains the only authority.
 */
export function countdownText(dueIso, nowMs = Date.now()) {
  const due = new Date(dueIso).getTime();
  if (Number.isNaN(due)) return '';
  const diff = due - nowMs;
  if (diff < 0) return 'Closed';
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return 'Due in less than a minute';
  if (minutes < 60) return `Due in ${minutes} minute${minutes === 1 ? '' : 's'}`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) {
    const rest = minutes % 60;
    return `Due in ${hours} hour${hours === 1 ? '' : 's'}${rest ? ` ${rest} min` : ''}`;
  }
  const days = Math.floor(hours / 24);
  return `Due in ${days} days`;
}

/** Returns a list of human-readable problems; empty when the form is submittable. */
export function validateForm(form) {
  const problems = [];
  if (!form.title.trim()) problems.push('Enter a title.');
  if (!form.audienceId) problems.push('Choose an audience.');
  if (!form.dueAt) problems.push('Set a due date and time.');
  if (form.dueAt && form.opensAt && new Date(form.dueAt) <= new Date(form.opensAt)) {
    problems.push('The due date must be later than the opening date.');
  }
  if (form.questions.length < 1) problems.push('Add at least one question.');
  if (form.questions.length > MAX_QUESTIONS) problems.push(`Use at most ${MAX_QUESTIONS} questions.`);
  form.questions.forEach((question, index) => {
    const n = index + 1;
    if (!question.prompt.trim()) problems.push(`Question ${n}: enter the question text.`);
    if (question.options.length < MIN_OPTIONS || question.options.length > MAX_OPTIONS) {
      problems.push(`Question ${n}: use ${MIN_OPTIONS} to ${MAX_OPTIONS} options.`);
    }
    if (question.options.some((option) => !option.trim())) {
      problems.push(`Question ${n}: every option needs text.`);
    }
    if (question.correctIndex < 0 || question.correctIndex >= question.options.length) {
      problems.push(`Question ${n}: mark which option is correct.`);
    }
  });
  return problems;
}

/** Form state -> request body for POST/PUT /learning/questionnaires. */
export function toApiPayload(trainerId, form) {
  return {
    trainer_id: trainerId,
    title: form.title.trim(),
    description: form.description.trim(),
    audience_type: form.audienceType,
    audience_id: form.audienceId,
    opens_at: localInputToIso(form.opensAt),
    due_at: localInputToIso(form.dueAt),
    questions: form.questions.map((question) => ({
      prompt: question.prompt.trim(),
      options: question.options.map((option) => option.trim()),
      correct_index: question.correctIndex,
    })),
  };
}

/** Saved questionnaire (trainer view) -> editable form state. */
export function fromQuestionnaire(questionnaire) {
  return {
    title: questionnaire.title,
    description: questionnaire.description || '',
    audienceType: questionnaire.audience_type,
    audienceId: questionnaire.audience_id,
    opensAt: isoToLocalInput(questionnaire.opens_at),
    dueAt: isoToLocalInput(questionnaire.due_at),
    questions: questionnaire.questions.map((question) => ({
      prompt: question.prompt,
      options: [...question.options],
      correctIndex: question.correct_index,
    })),
  };
}

export function emptyForm() {
  return {
    title: '',
    description: '',
    audienceType: 'cohort',
    audienceId: '',
    opensAt: '',
    dueAt: '',
    questions: [blankQuestion()],
  };
}
