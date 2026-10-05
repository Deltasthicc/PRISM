'use client';

import { useCallback, useEffect, useState } from 'react';
import { ClipboardList } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { cohorts, courseCatalog } from '@/lib/api/client';
import { questionnairesApi } from '@/lib/api/questionnaires';
import {
  MAX_OPTIONS,
  MAX_QUESTIONS,
  MIN_OPTIONS,
  blankQuestion,
  browserTimeZone,
  emptyForm,
  formatDeadline,
  fromQuestionnaire,
  localInputToIso,
  toApiPayload,
  validateForm,
} from '@/lib/questionnaireForm';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';

// Trainer authoring surface for questionnaires with deadlines
// (backend/routes/questionnaires.py, PS75-08). Not role-gated in the UI;
// QUESTIONNAIRE_MANAGE and ownership are enforced server-side (403 / 404).
// Not yet translated -- English only, like the other trainer pages.

function ErrorText({ children }) {
  if (!children) return null;
  return (
    <p role="alert" className="font-sans text-xs text-[#b3261e]">
      {children}
    </p>
  );
}

function statusBadge(questionnaire) {
  if (!questionnaire.is_published) return <Badge>Draft</Badge>;
  return <Badge tone="success">Published</Badge>;
}

function resultStatusLabel(status) {
  if (status === 'submitted') return 'Submitted';
  if (status === 'missed_deadline') return 'Missed deadline';
  return 'Not submitted yet';
}

function ResultsView({ trainerId, questionnaireId }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setData(await questionnairesApi.results(questionnaireId, trainerId));
    } catch (cause) {
      setError(cause.message || 'Could not load results.');
    } finally {
      setLoading(false);
    }
  }, [questionnaireId, trainerId]);

  useEffect(() => {
    load();
  }, [load]);

  if (loading) return <p className="font-sans text-sm text-[#757682]">Loading results…</p>;
  if (error) {
    return (
      <div className="flex flex-col gap-2 items-start">
        <ErrorText>{error}</ErrorText>
        <Button variant="ghost" onClick={load}>
          Retry
        </Button>
      </div>
    );
  }
  if (!data) return null;
  const { aggregates, rows } = data;
  return (
    <div className="flex flex-col gap-3">
      <p className="font-sans text-sm text-[#131b2e]">
        {aggregates.submitted_count} of {aggregates.audience_size} trainees submitted
        {aggregates.mean_score !== null
          ? `; mean score ${aggregates.mean_score} out of ${aggregates.max_score}`
          : '; no scores yet'}
        .
      </p>
      <p className="font-sans text-xs text-[#757682]">
        {data.deadline_passed ? 'The deadline has passed.' : 'The questionnaire is still open.'} Showing only your own
        audience. These scores are not recorded as competency evidence.
      </p>
      {rows.length === 0 ? (
        <p className="font-sans text-sm text-[#757682]">No trainees are in this audience yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left font-sans text-sm">
            <caption className="sr-only">Participation and scores</caption>
            <thead>
              <tr className="text-xs text-[#444651]">
                <th scope="col" className="py-1 pr-3">Trainee</th>
                <th scope="col" className="py-1 pr-3">Status</th>
                <th scope="col" className="py-1 pr-3">Score</th>
                <th scope="col" className="py-1">Submitted</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.player_id} className="border-t border-[#c5c5d3]/40">
                  <td className="py-1.5 pr-3">{row.username}</td>
                  <td className="py-1.5 pr-3">{resultStatusLabel(row.status)}</td>
                  <td className="py-1.5 pr-3">
                    {row.score !== null ? `${row.score} / ${row.max_score}` : '—'}
                  </td>
                  <td className="py-1.5">{row.submitted_at ? formatDeadline(row.submitted_at) : '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Button variant="ghost" onClick={load} className="self-start">
        Refresh results
      </Button>
    </div>
  );
}

function QuestionEditor({ index, question, onChange, onRemove, canRemove }) {
  const n = index + 1;
  const name = `correct-${index}`;

  function setOption(optionIndex, value) {
    const options = question.options.map((option, i) => (i === optionIndex ? value : option));
    onChange({ ...question, options });
  }

  function addOption() {
    if (question.options.length >= MAX_OPTIONS) return;
    onChange({ ...question, options: [...question.options, ''] });
  }

  function removeOption(optionIndex) {
    if (question.options.length <= MIN_OPTIONS) return;
    const options = question.options.filter((_, i) => i !== optionIndex);
    let correctIndex = question.correctIndex;
    if (optionIndex < correctIndex) correctIndex -= 1;
    else if (optionIndex === correctIndex) correctIndex = 0;
    onChange({ ...question, options, correctIndex });
  }

  return (
    <fieldset className="border border-[#c5c5d3]/60 rounded-lg p-3 flex flex-col gap-3">
      <legend className="font-sans text-xs font-bold text-[#00236f] px-1">Question {n}</legend>
      <Input
        id={`q-${index}-prompt`}
        label={`Question ${n} text`}
        textarea
        rows="2"
        maxLength={1000}
        value={question.prompt}
        onChange={(e) => onChange({ ...question, prompt: e.target.value })}
      />
      <div role="radiogroup" aria-label={`Options for question ${n}. Select the correct one.`} className="flex flex-col gap-2">
        {question.options.map((option, optionIndex) => (
          <div key={optionIndex} className="flex items-end gap-2">
            <label className="flex items-center gap-1.5 pb-2.5 font-sans text-xs text-[#444651]">
              <input
                type="radio"
                name={name}
                checked={question.correctIndex === optionIndex}
                onChange={() => onChange({ ...question, correctIndex: optionIndex })}
                aria-label={`Mark option ${optionIndex + 1} of question ${n} as the correct answer`}
              />
              <span aria-hidden="true">Correct</span>
            </label>
            <div className="flex-1">
              <Input
                id={`q-${index}-opt-${optionIndex}`}
                label={`Question ${n} option ${optionIndex + 1}`}
                maxLength={500}
                value={option}
                onChange={(e) => setOption(optionIndex, e.target.value)}
                className="w-full"
              />
            </div>
            <Button
              variant="ghost"
              onClick={() => removeOption(optionIndex)}
              disabled={question.options.length <= MIN_OPTIONS}
              aria-label={`Remove option ${optionIndex + 1} of question ${n}`}
            >
              Remove
            </Button>
          </div>
        ))}
      </div>
      <div className="flex gap-2 flex-wrap">
        <Button variant="ghost" onClick={addOption} disabled={question.options.length >= MAX_OPTIONS}>
          Add option
        </Button>
        <Button variant="ghost" onClick={onRemove} disabled={!canRemove} aria-label={`Remove question ${n}`}>
          Remove question
        </Button>
      </div>
    </fieldset>
  );
}

export default function TrainerQuestionnairesPage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);
  const trainerId = player?.player_id;

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const [cohortList, setCohortList] = useState([]);
  const [courseList, setCourseList] = useState([]);
  const [audienceError, setAudienceError] = useState('');

  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState(null);
  const [saving, setSaving] = useState(false);
  const [formErrors, setFormErrors] = useState([]);
  const [saveError, setSaveError] = useState('');

  const [busyId, setBusyId] = useState(null);
  const [rowErrors, setRowErrors] = useState({});
  const [extendValues, setExtendValues] = useState({});
  const [resultsOpenId, setResultsOpenId] = useState(null);
  const [timeZone, setTimeZone] = useState('');

  useEffect(() => {
    setTimeZone(browserTimeZone());
  }, []);

  const refresh = useCallback(async () => {
    if (!trainerId) return;
    setLoading(true);
    setLoadError('');
    try {
      setItems((await questionnairesApi.listMine(trainerId)) || []);
    } catch (cause) {
      setLoadError(cause.message || 'Could not load your questionnaires.');
    } finally {
      setLoading(false);
    }
  }, [trainerId]);

  const loadAudiences = useCallback(async () => {
    if (!trainerId) return;
    setAudienceError('');
    try {
      const [cohortRows, courseRows] = await Promise.all([
        cohorts.listMine(trainerId),
        courseCatalog.listMine(trainerId),
      ]);
      setCohortList(cohortRows || []);
      setCourseList(courseRows || []);
    } catch (cause) {
      setAudienceError(cause.message || 'Could not load your cohorts and courses.');
    }
  }, [trainerId]);

  useEffect(() => {
    if (!ready) return;
    refresh();
    loadAudiences();
  }, [ready, refresh, loadAudiences]);

  function updateForm(patch) {
    setForm((current) => ({ ...current, ...patch }));
  }

  function updateQuestion(index, question) {
    setForm((current) => ({
      ...current,
      questions: current.questions.map((q, i) => (i === index ? question : q)),
    }));
  }

  function resetForm() {
    setForm(emptyForm());
    setEditingId(null);
    setFormErrors([]);
    setSaveError('');
  }

  async function handleSave(event) {
    event.preventDefault();
    if (!trainerId) return;
    const problems = validateForm(form);
    setFormErrors(problems);
    setSaveError('');
    if (problems.length) return;
    setSaving(true);
    try {
      const payload = toApiPayload(trainerId, form);
      if (editingId) await questionnairesApi.update(editingId, payload);
      else await questionnairesApi.create(payload);
      resetForm();
      await refresh();
    } catch (cause) {
      setSaveError(cause.message || 'Could not save the questionnaire.');
    } finally {
      setSaving(false);
    }
  }

  async function runRowAction(questionnaireId, action) {
    setBusyId(questionnaireId);
    setRowErrors((current) => ({ ...current, [questionnaireId]: '' }));
    try {
      await action();
      await refresh();
    } catch (cause) {
      setRowErrors((current) => ({ ...current, [questionnaireId]: cause.message || 'That did not work.' }));
    } finally {
      setBusyId(null);
    }
  }

  function startEdit(questionnaire) {
    setEditingId(questionnaire.questionnaire_id);
    setForm(fromQuestionnaire(questionnaire));
    setFormErrors([]);
    setSaveError('');
    if (typeof window !== 'undefined') window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  if (!ready || !player) return null;

  const audiences = form.audienceType === 'cohort' ? cohortList : courseList;
  const audienceLabel = form.audienceType === 'cohort' ? 'Cohort' : 'Course';
  const tzNote = timeZone ? `your local time, ${timeZone}` : 'your local time';

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1 flex items-center gap-1.5">
          <ClipboardList size={12} aria-hidden="true" />
          Trainer
        </p>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">Questionnaires</h1>
        <p className="font-sans text-sm text-[#757682] mt-1">
          Write multiple-choice questionnaires for one of your cohorts or courses, set a deadline, and see who has
          taken them. Once published, questions and the deadline are locked; the deadline can only be extended.
        </p>
      </div>

      <Panel>
        <h2 className="font-sans text-sm font-bold text-[#131b2e] mb-3">
          {editingId ? 'Edit draft questionnaire' : 'New questionnaire'}
        </h2>
        <form onSubmit={handleSave} className="flex flex-col gap-3" noValidate>
          <Input id="qn-title" label="Title" value={form.title} maxLength={200} onChange={(e) => updateForm({ title: e.target.value })} required />
          <Input
            id="qn-description"
            label="Description (optional)"
            textarea
            rows="2"
            maxLength={2000}
            value={form.description}
            onChange={(e) => updateForm({ description: e.target.value })}
          />

          <fieldset className="flex flex-col gap-2">
            <legend className="font-sans text-xs font-semibold text-[#444651] mb-1">Audience</legend>
            <div className="flex gap-4">
              {[
                ['cohort', 'One of my cohorts'],
                ['course', 'One of my courses'],
              ].map(([value, label]) => (
                <label key={value} className="flex items-center gap-1.5 font-sans text-sm text-[#131b2e]">
                  <input
                    type="radio"
                    name="audience-type"
                    value={value}
                    checked={form.audienceType === value}
                    onChange={() => updateForm({ audienceType: value, audienceId: '' })}
                  />
                  {label}
                </label>
              ))}
            </div>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="qn-audience" className="font-sans text-xs font-semibold text-[#444651]">
                {audienceLabel}
              </label>
              <select
                id="qn-audience"
                value={form.audienceId}
                onChange={(e) => updateForm({ audienceId: e.target.value })}
                className="bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f] outline-none"
              >
                <option value="">Select a {audienceLabel.toLowerCase()}…</option>
                {audiences.map((audience) => {
                  const id = audience.cohort_id || audience.course_id;
                  const name = audience.name || audience.title;
                  return (
                    <option key={id} value={id}>
                      {name}
                    </option>
                  );
                })}
              </select>
              {audiences.length === 0 && !audienceError && (
                <p className="font-sans text-xs text-[#757682]">
                  {form.audienceType === 'cohort'
                    ? 'You have no cohorts yet. An administrator assigns cohorts to trainers.'
                    : 'You have no courses yet. Create one on the My courses page.'}
                </p>
              )}
              {audienceError && (
                <div className="flex items-center gap-2">
                  <ErrorText>{audienceError}</ErrorText>
                  <Button variant="ghost" onClick={loadAudiences}>
                    Retry
                  </Button>
                </div>
              )}
            </div>
          </fieldset>

          <div className="grid gap-3 sm:grid-cols-2">
            <Input
              id="qn-opens"
              type="datetime-local"
              label={`Opens (optional, ${tzNote})`}
              value={form.opensAt}
              onChange={(e) => updateForm({ opensAt: e.target.value })}
            />
            <Input
              id="qn-due"
              type="datetime-local"
              label={`Due (required, ${tzNote})`}
              value={form.dueAt}
              onChange={(e) => updateForm({ dueAt: e.target.value })}
              required
            />
          </div>
          <p className="font-sans text-xs text-[#757682]">
            Deadlines are checked by the server clock. A submission at exactly the due time is accepted; anything later is
            rejected.
          </p>

          <div className="flex flex-col gap-3">
            {form.questions.map((question, index) => (
              <QuestionEditor
                key={index}
                index={index}
                question={question}
                canRemove={form.questions.length > 1}
                onChange={(next) => updateQuestion(index, next)}
                onRemove={() =>
                  setForm((current) => ({
                    ...current,
                    questions: current.questions.filter((_, i) => i !== index),
                  }))
                }
              />
            ))}
            <Button
              variant="ghost"
              className="self-start"
              disabled={form.questions.length >= MAX_QUESTIONS}
              onClick={() => setForm((current) => ({ ...current, questions: [...current.questions, blankQuestion()] }))}
            >
              Add question
            </Button>
          </div>

          {formErrors.length > 0 && (
            <div role="alert" className="font-sans text-xs text-[#b3261e]">
              <p className="font-semibold">Please fix the following:</p>
              <ul className="list-disc pl-5">
                {formErrors.map((problem) => (
                  <li key={problem}>{problem}</li>
                ))}
              </ul>
            </div>
          )}
          <ErrorText>{saveError}</ErrorText>
          <div className="flex gap-2">
            <Button type="submit" disabled={saving}>
              {saving ? 'Saving…' : editingId ? 'Save changes' : 'Create draft'}
            </Button>
            {editingId && (
              <Button variant="ghost" onClick={resetForm} disabled={saving}>
                Cancel editing
              </Button>
            )}
          </div>
        </form>
      </Panel>

      <h2 className="font-sans text-sm font-bold text-[#131b2e]">My questionnaires</h2>
      {loading && <p className="font-sans text-sm text-[#757682]" role="status">Loading your questionnaires…</p>}
      {!loading && loadError && (
        <div className="flex flex-col gap-2 items-start">
          <ErrorText>{loadError}</ErrorText>
          <Button variant="ghost" onClick={refresh}>
            Retry
          </Button>
        </div>
      )}
      {!loading && !loadError && items.length === 0 && (
        <p className="font-sans text-sm text-[#757682]">No questionnaires yet. Create your first one above.</p>
      )}

      {!loading &&
        !loadError &&
        items.map((item) => {
          const id = item.questionnaire_id;
          const busy = busyId === id;
          const editable = !item.is_published && item.attempt_count === 0;
          const extendValue = extendValues[id] || '';
          return (
            <Panel key={id}>
              <div className="flex items-start justify-between gap-3 flex-wrap">
                <div>
                  <h3 className="font-sans text-sm font-bold text-[#131b2e]">{item.title}</h3>
                  <p className="font-sans text-xs text-[#757682]">
                    {item.audience_type === 'cohort' ? 'Cohort' : 'Course'} audience, {item.questions.length} question
                    {item.questions.length === 1 ? '' : 's'}, {item.attempt_count} submission
                    {item.attempt_count === 1 ? '' : 's'}
                  </p>
                  <p className="font-sans text-xs text-[#444651]">Due {formatDeadline(item.due_at)}</p>
                </div>
                {statusBadge(item)}
              </div>

              <div className="flex gap-2 flex-wrap mt-3">
                <Button
                  variant="ghost"
                  disabled={busy}
                  onClick={() =>
                    runRowAction(id, () =>
                      item.is_published
                        ? questionnairesApi.unpublish(id, trainerId)
                        : questionnairesApi.publish(id, trainerId)
                    )
                  }
                >
                  {item.is_published ? 'Unpublish' : 'Publish'}
                </Button>
                {editable && (
                  <Button variant="ghost" disabled={busy} onClick={() => startEdit(item)}>
                    Edit draft
                  </Button>
                )}
                <Button
                  variant="ghost"
                  aria-expanded={resultsOpenId === id}
                  onClick={() => setResultsOpenId(resultsOpenId === id ? null : id)}
                >
                  {resultsOpenId === id ? 'Hide results' : 'View results'}
                </Button>
              </div>

              {item.is_published && (
                <div className="mt-3 flex items-end gap-2 flex-wrap">
                  <Input
                    id={`extend-${id}`}
                    type="datetime-local"
                    label={`Extend deadline to (${tzNote})`}
                    value={extendValue}
                    onChange={(e) => setExtendValues((current) => ({ ...current, [id]: e.target.value }))}
                  />
                  <Button
                    variant="ghost"
                    disabled={busy || !extendValue}
                    onClick={() =>
                      runRowAction(id, async () => {
                        await questionnairesApi.extendDeadline(id, trainerId, localInputToIso(extendValue));
                        setExtendValues((current) => ({ ...current, [id]: '' }));
                      })
                    }
                  >
                    Extend deadline
                  </Button>
                </div>
              )}

              <div className="mt-2">
                <ErrorText>{rowErrors[id]}</ErrorText>
              </div>

              {resultsOpenId === id && (
                <div className="mt-3 border-t border-[#c5c5d3]/40 pt-3">
                  <ResultsView trainerId={trainerId} questionnaireId={id} />
                </div>
              )}
            </Panel>
          );
        })}
    </div>
  );
}
