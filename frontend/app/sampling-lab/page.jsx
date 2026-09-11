'use client';

import { useEffect, useState } from 'react';
import { FlaskConical, CheckCircle2, XCircle } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { samplingLab } from '@/lib/api/client';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';

// A real, bounded virtual lab (backend/labs/sampling_lab.py, exposed at
// /learning/sampling-lab). Deterministic expected outputs recomputed
// server-side from a fixed formula -- no learner code is ever accepted or
// executed. A correct submission is real practice evidence for
// os_sampling_design, feeding the same AccuracyHistory table Prerequisite
// Pathways reads (see routes/sampling_lab.py's module docstring for why that
// dual-write matters).
//
// Not yet translated into the other 10 UI languages -- English only for now,
// same honesty convention as this project's other documented pending items.
export default function SamplingLabPage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);
  const [tasks, setTasks] = useState([]);
  const [selectedTaskId, setSelectedTaskId] = useState(null);
  const [value, setValue] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!ready) return;
    samplingLab
      .getTasks()
      .then((data) => {
        setTasks(data.tasks || []);
        if (data.tasks?.length) setSelectedTaskId(data.tasks[0].task_id);
      })
      .catch((cause) => setError(cause.message || 'Could not load lab tasks.'));
  }, [ready]);

  const selectedTask = tasks.find((t) => t.task_id === selectedTaskId);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!selectedTaskId || value.trim() === '' || !player?.player_id) return;
    setSubmitting(true);
    setError('');
    setResult(null);
    try {
      const data = await samplingLab.submit(player.player_id, selectedTaskId, Number(value));
      setResult(data);
    } catch (cause) {
      setError(cause.message || 'Submission failed.');
    } finally {
      setSubmitting(false);
    }
  }

  function selectTask(taskId) {
    setSelectedTaskId(taskId);
    setValue('');
    setResult(null);
    setError('');
  }

  if (!ready) {
    return <p className="font-sans text-sm text-[#757682] text-center mt-10">Loading…</p>;
  }

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1 flex items-center gap-1.5">
          <FlaskConical size={12} />
          Virtual Lab · Official Statistics
        </p>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">Sampling Design Lab</h1>
        <p className="font-sans text-sm text-[#757682] mt-1">
          Work through real sample-size calculations. Each task has one deterministic correct
          answer, recomputed from a fixed formula — no code is executed, nothing is graded
          arbitrarily.
        </p>
      </div>

      <Panel>
        <div className="flex flex-wrap gap-2 mb-4">
          {tasks.map((task) => (
            <button
              key={task.task_id}
              type="button"
              onClick={() => selectTask(task.task_id)}
              className={`font-sans text-xs px-3 py-1.5 rounded-full border ${
                task.task_id === selectedTaskId
                  ? 'bg-[#00236f] text-white border-[#00236f]'
                  : 'border-[#c5c5d3]/50 text-[#00236f] hover:bg-[#f2f3ff]'
              }`}
            >
              {task.title}
            </button>
          ))}
        </div>

        {selectedTask && (
          <form onSubmit={handleSubmit} className="flex flex-col gap-3">
            <p className="font-sans text-sm text-[#131b2e]">{selectedTask.prompt}</p>
            <div className="flex gap-2">
              <input
                type="number"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder={selectedTask.answer_label}
                className="flex-1 px-3.5 py-2.5 rounded-lg border border-[#c5c5d3]/60 font-sans text-sm outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]"
              />
              <Button type="submit" disabled={submitting || value.trim() === ''}>
                {submitting ? 'Checking…' : 'Submit'}
              </Button>
            </div>
          </form>
        )}
        {error && <p className="mt-3 font-sans text-xs text-[#b3261e]">{error}</p>}
      </Panel>

      {result && (
        <Panel>
          <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
            <span className="font-sans text-xs font-semibold text-[#757682]">Result</span>
            <Badge tone={result.correct ? 'success' : 'warning'}>
              {result.correct ? (
                <span className="flex items-center gap-1"><CheckCircle2 size={12} /> Correct</span>
              ) : (
                <span className="flex items-center gap-1"><XCircle size={12} /> Not quite</span>
              )}
            </Badge>
          </div>
          <p className="font-sans text-sm text-[#131b2e]">{result.feedback}</p>
          {result.steps?.length > 0 && (
            <ol className="mt-3 list-decimal list-inside flex flex-col gap-2">
              {result.steps.map((step, i) => (
                <li key={i} className="font-sans text-xs text-[#333a49]">
                  <span className="font-semibold">{step.label}:</span> {step.detail}
                </li>
              ))}
            </ol>
          )}
          {result.correct && (
            <p className="mt-3 pt-3 border-t border-[#c5c5d3]/30 font-mono text-[10px] text-[#8a8f9d]">
              Recorded as real practice evidence for Sampling &amp; Design (os_sampling_design).
            </p>
          )}
        </Panel>
      )}
    </div>
  );
}
