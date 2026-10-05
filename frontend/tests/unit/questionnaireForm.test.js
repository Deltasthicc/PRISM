import { describe, expect, it } from 'vitest';
import {
  blankQuestion,
  countdownText,
  emptyForm,
  fromQuestionnaire,
  isoToLocalInput,
  localInputToIso,
  toApiPayload,
  validateForm,
} from '@/lib/questionnaireForm';

function validForm() {
  return {
    ...emptyForm(),
    title: ' Week 1 ',
    audienceId: 'cohort-1',
    dueAt: '2026-10-06T12:00',
    questions: [{ prompt: ' 2+2? ', options: ['3 ', '4'], correctIndex: 1 }],
  };
}

describe('countdownText', () => {
  const now = Date.parse('2026-10-05T12:00:00Z');
  it('reports closed strictly after the deadline, not at it', () => {
    expect(countdownText('2026-10-05T12:00:00Z', now)).toBe('Due in less than a minute');
    expect(countdownText('2026-10-05T11:59:59.999Z', now)).toBe('Closed');
  });
  it('uses minutes, hours and days', () => {
    expect(countdownText('2026-10-05T12:05:00Z', now)).toBe('Due in 5 minutes');
    expect(countdownText('2026-10-05T13:30:00Z', now)).toBe('Due in 1 hour 30 min');
    expect(countdownText('2026-10-09T12:00:00Z', now)).toBe('Due in 4 days');
  });
  it('is empty for an unparseable date', () => {
    expect(countdownText('not a date', now)).toBe('');
  });
});

describe('datetime-local conversion', () => {
  it('round-trips through the viewer local time', () => {
    const iso = localInputToIso('2026-10-06T12:00');
    expect(iso).toMatch(/Z$/);
    expect(isoToLocalInput(iso)).toBe('2026-10-06T12:00');
  });
  it('returns null / empty for blank input', () => {
    expect(localInputToIso('')).toBeNull();
    expect(isoToLocalInput(null)).toBe('');
  });
});

describe('validateForm', () => {
  it('accepts a complete form', () => {
    expect(validateForm(validForm())).toEqual([]);
  });
  it('flags missing fields and bad questions', () => {
    const form = { ...emptyForm(), questions: [{ prompt: '', options: ['a'], correctIndex: 5 }] };
    const problems = validateForm(form);
    expect(problems).toContain('Enter a title.');
    expect(problems).toContain('Choose an audience.');
    expect(problems).toContain('Set a due date and time.');
    expect(problems).toContain('Question 1: enter the question text.');
    expect(problems).toContain('Question 1: use 2 to 6 options.');
    expect(problems).toContain('Question 1: mark which option is correct.');
    const blankOption = validateForm({ ...validForm(), questions: [{ prompt: 'p', options: ['a', ' '], correctIndex: 0 }] });
    expect(blankOption).toContain('Question 1: every option needs text.');
  });
  it('requires due after opens', () => {
    const form = { ...validForm(), opensAt: '2026-10-07T12:00' };
    expect(validateForm(form)).toContain('The due date must be later than the opening date.');
  });
});

describe('toApiPayload / fromQuestionnaire', () => {
  it('trims text and maps to the API shape', () => {
    const payload = toApiPayload('trainer-1', validForm());
    expect(payload.trainer_id).toBe('trainer-1');
    expect(payload.title).toBe('Week 1');
    expect(payload.opens_at).toBeNull();
    expect(payload.questions).toEqual([{ prompt: '2+2?', options: ['3', '4'], correct_index: 1 }]);
  });
  it('maps a saved questionnaire back to form state', () => {
    const form = fromQuestionnaire({
      title: 'T',
      description: null,
      audience_type: 'course',
      audience_id: 'c1',
      opens_at: null,
      due_at: '2026-10-06T12:00:00Z',
      questions: [{ prompt: 'p', options: ['a', 'b'], correct_index: 1 }],
    });
    expect(form.audienceType).toBe('course');
    expect(form.description).toBe('');
    expect(form.questions[0]).toEqual({ prompt: 'p', options: ['a', 'b'], correctIndex: 1 });
  });
  it('blankQuestion starts with two empty options', () => {
    expect(blankQuestion().options).toHaveLength(2);
  });
});
