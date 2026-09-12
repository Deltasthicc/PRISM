'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { Scale, CheckCircle2, ArrowRight, Award, ArrowLeft } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { judgmentScenarios } from '@/lib/api/client';
import { competencyLabel } from '@/lib/publicPolicyLabels';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';

// The Judgment Simulation player: fetch the start node, let the learner pick
// one of the offered choices, reveal that choice's honest consequence (the
// backend only returns feedback/is_recommended *after* the choice is
// committed -- see routes/judgment_scenarios.py), then continue to the next
// decision point or an ending. A full completion is re-validated and scored
// server-side (POST /complete): the recommended/total counts shown at the
// end are always the server's own recount, never a client-side tally.
//
// Not yet translated into the other 10 UI languages -- English only for now,
// same honesty convention as app/sampling-lab/page.jsx's identical note.
export default function ScenarioPlayerPage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);
  const router = useRouter();
  const params = useParams();
  const scenarioId = params?.scenarioId;

  const [scenarioMeta, setScenarioMeta] = useState(null);
  const [currentNode, setCurrentNode] = useState(null);
  const [pathTaken, setPathTaken] = useState([]);
  const [revealed, setRevealed] = useState(null);
  const [endingNode, setEndingNode] = useState(null);
  const [completionResult, setCompletionResult] = useState(null);

  const [loading, setLoading] = useState(true);
  const [choosing, setChoosing] = useState(false);
  const [continuing, setContinuing] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!ready || !scenarioId) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError('');
      try {
        const [{ scenarios }, startNode] = await Promise.all([
          judgmentScenarios.list(),
          judgmentScenarios.getNode(scenarioId, 'start'),
        ]);
        if (cancelled) return;
        setScenarioMeta(scenarios.find((s) => s.scenario_id === scenarioId) || null);
        setCurrentNode(startNode);
      } catch (cause) {
        if (!cancelled) setError(cause.message || 'Could not load this scenario.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [ready, scenarioId]);

  async function handleChoice(choiceId) {
    if (!player?.player_id || !currentNode) return;
    setChoosing(true);
    setError('');
    try {
      const response = await judgmentScenarios.choose(
        scenarioId,
        player.player_id,
        currentNode.node_id,
        choiceId
      );
      setPathTaken((prev) => [...prev, { node_id: currentNode.node_id, choice_id: choiceId }]);
      setRevealed(response);
    } catch (cause) {
      setError(cause.message || 'Could not record that choice.');
    } finally {
      setChoosing(false);
    }
  }

  async function handleContinue() {
    if (!revealed) return;
    setContinuing(true);
    setError('');
    try {
      if (revealed.next_node_id) {
        const nextNode = await judgmentScenarios.getNode(scenarioId, revealed.next_node_id);
        if (revealed.is_ending) {
          setEndingNode(nextNode);
        } else {
          setCurrentNode(nextNode);
          setRevealed(null);
        }
      } else {
        // No further node to show -- the choice itself was the dead end.
        setEndingNode(null);
      }
    } catch (cause) {
      setError(cause.message || 'Could not load the next step.');
    } finally {
      setContinuing(false);
    }
  }

  async function handleFinish() {
    if (!player?.player_id) return;
    setFinishing(true);
    setError('');
    try {
      const result = await judgmentScenarios.complete(scenarioId, player.player_id, pathTaken);
      setCompletionResult(result);
    } catch (cause) {
      setError(cause.message || 'Could not record this completed run.');
    } finally {
      setFinishing(false);
    }
  }

  if (!ready || loading) {
    return <p className="font-sans text-sm text-[#757682] text-center mt-10">Loading…</p>;
  }

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-4">
      <div>
        <Link
          href="/scenarios"
          className="font-sans text-xs text-[#757682] hover:text-[#00236f] flex items-center gap-1 mb-2"
        >
          <ArrowLeft size={12} /> All scenarios
        </Link>
        <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1 flex items-center gap-1.5">
          <Scale size={12} />
          Judgment Simulation
        </p>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">
          {scenarioMeta?.title || 'Scenario'}
        </h1>
        {scenarioMeta?.situation_brief && (
          <p className="font-sans text-sm text-[#757682] mt-1">{scenarioMeta.situation_brief}</p>
        )}
      </div>

      {error && <p className="font-sans text-xs text-[#b3261e]">{error}</p>}

      {completionResult ? (
        <Panel>
          <div className="flex items-center gap-2 mb-3">
            <Award size={18} className="text-[#00236f]" />
            <span className="font-sans text-base font-bold text-[#131b2e]">Scenario complete</span>
          </div>
          <p className="font-sans text-sm text-[#131b2e]">
            You made{' '}
            <span className="font-semibold">
              {completionResult.recommended_choice_count} of {completionResult.total_choice_count}
            </span>{' '}
            recommended decisions along the path you took.
          </p>
          <p className="mt-3 pt-3 border-t border-[#c5c5d3]/30 font-mono text-[10px] text-[#8a8f9d]">
            Recorded as real practice evidence for {competencyLabel(scenarioMeta?.competency_id)}.
          </p>
          <div className="flex gap-2 mt-4">
            <Button variant="ghost" onClick={() => router.push('/scenarios')}>
              Back to scenarios
            </Button>
            <Button onClick={() => window.location.reload()}>Play again</Button>
          </div>
        </Panel>
      ) : endingNode !== null || (revealed?.is_ending && !revealed.next_node_id) ? (
        <Panel>
          <Badge tone="accent">Ending</Badge>
          {endingNode?.prompt && (
            <p className="font-sans text-sm text-[#131b2e] mt-3">{endingNode.prompt}</p>
          )}
          <Button className="mt-4" onClick={handleFinish} disabled={finishing}>
            {finishing ? 'Recording…' : 'Finish scenario'}
          </Button>
        </Panel>
      ) : revealed ? (
        <Panel>
          <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
            <span className="font-sans text-xs font-semibold text-[#757682]">Consequence</span>
            <Badge tone={revealed.is_recommended ? 'success' : 'warning'}>
              {revealed.is_recommended ? (
                <span className="flex items-center gap-1">
                  <CheckCircle2 size={12} /> Sound judgment
                </span>
              ) : (
                <span>Worth reconsidering</span>
              )}
            </Badge>
          </div>
          <p className="font-sans text-sm text-[#131b2e]">{revealed.feedback}</p>
          <Button className="mt-4 flex items-center gap-1.5" onClick={handleContinue} disabled={continuing}>
            {continuing ? 'Loading…' : 'Continue'} <ArrowRight size={14} />
          </Button>
        </Panel>
      ) : currentNode ? (
        <Panel>
          <p className="font-sans text-sm text-[#131b2e] mb-4">{currentNode.prompt}</p>
          <div className="flex flex-col gap-2">
            {currentNode.choices.map((choice) => (
              <button
                key={choice.choice_id}
                type="button"
                disabled={choosing}
                onClick={() => handleChoice(choice.choice_id)}
                className="text-left font-sans text-sm px-4 py-3 rounded-lg border border-[#c5c5d3]/60 text-[#131b2e] hover:border-[#00236f]/50 hover:bg-[#f2f3ff] transition-colors disabled:opacity-50"
              >
                {choice.text}
              </button>
            ))}
          </div>
        </Panel>
      ) : null}
    </div>
  );
}
