'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Scale, ChevronRight } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { judgmentScenarios } from '@/lib/api/client';
import { competencyLabel } from '@/lib/publicPolicyLabels';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';

// Branching "Judgment Simulation" scenarios (backend/routes/judgment_scenarios.py):
// a realistic administrative situation, a real choice among plausible
// actions, and an honest consequence -- not a multiple-choice quiz item.
//
// Not yet translated into the other 10 UI languages -- English only for now,
// same honesty convention as this project's other documented pending items
// (see app/sampling-lab/page.jsx's identical note).
export default function ScenariosListPage() {
  const { ready } = useRequireAuth();
  const [scenarios, setScenarios] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!ready) return;
    judgmentScenarios
      .list()
      .then((data) => setScenarios(data.scenarios || []))
      .catch((cause) => setError(cause.message || 'Could not load scenarios.'))
      .finally(() => setLoading(false));
  }, [ready]);

  if (!ready) {
    return <p className="font-sans text-sm text-[#757682] text-center mt-10">Loading…</p>;
  }

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1 flex items-center gap-1.5">
          <Scale size={12} />
          Judgment Simulations · Public Policy
        </p>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">Judgment Simulations</h1>
        <p className="font-sans text-sm text-[#757682] mt-1">
          Real administrative situations, real trade-offs. Pick a course of action, see its
          honest consequence, and continue to the next decision point.
        </p>
      </div>

      {loading && <p className="font-sans text-sm text-[#757682]">Loading scenarios…</p>}
      {error && <p className="font-sans text-xs text-[#b3261e]">{error}</p>}

      {!loading && !error && scenarios.length === 0 && (
        <Panel>
          <p className="font-sans text-sm text-[#757682]">No scenarios are available yet.</p>
        </Panel>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {scenarios.map((scenario) => (
          <Link key={scenario.scenario_id} href={`/scenarios/${scenario.scenario_id}`}>
            <Panel className="h-full flex flex-col gap-2 hover:border-[#00236f]/40 transition-colors cursor-pointer">
              <Badge tone="accent">{competencyLabel(scenario.competency_id)}</Badge>
              <h2 className="font-sans text-base font-bold text-[#131b2e]">{scenario.title}</h2>
              <p className="font-sans text-sm text-[#757682] flex-1">{scenario.situation_brief}</p>
              <span className="font-sans text-xs font-semibold text-[#00236f] flex items-center gap-1 mt-1">
                Begin scenario <ChevronRight size={14} />
              </span>
            </Panel>
          </Link>
        ))}
      </div>
    </div>
  );
}
