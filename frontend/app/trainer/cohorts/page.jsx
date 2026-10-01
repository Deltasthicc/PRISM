'use client';

import { useEffect, useState } from 'react';
import { Users2 } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { cohorts } from '@/lib/api/client';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';

// Trainer's own scoped view -- real cross-learner visibility, newly
// possible because routes/cohorts.py now exists (see that module's
// docstring for the gap this closes). Every read here is already scoped
// server-side to cohorts assigned to this trainer; the UI doesn't need to
// re-implement that boundary, only avoid implying one that isn't there.
export default function TrainerCohortsPage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);
  const [cohortList, setCohortList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState('');

  const [expandedId, setExpandedId] = useState(null);
  const [performance, setPerformance] = useState([]);
  const [performanceLoading, setPerformanceLoading] = useState(false);
  const [performanceError, setPerformanceError] = useState('');

  useEffect(() => {
    if (!ready || !player?.player_id) return;
    setLoading(true);
    setLoadError('');
    cohorts
      .listMine(player.player_id)
      .then((data) => setCohortList(data || []))
      .catch((cause) => setLoadError(cause.message || 'Could not load your cohorts.'))
      .finally(() => setLoading(false));
  }, [ready, player?.player_id]);

  async function toggleExpand(cohortId) {
    if (expandedId === cohortId) {
      setExpandedId(null);
      return;
    }
    setExpandedId(cohortId);
    setPerformanceLoading(true);
    setPerformanceError('');
    try {
      const data = await cohorts.performance(cohortId);
      setPerformance(data || []);
    } catch (cause) {
      setPerformanceError(cause.message || 'Could not load performance data.');
    } finally {
      setPerformanceLoading(false);
    }
  }

  if (!ready) return null;

  return (
    <div className="max-w-2xl mx-auto flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1 flex items-center gap-1.5">
          <Users2 size={12} />
          Trainer
        </p>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">My cohorts</h1>
        <p className="font-sans text-sm text-[#757682] mt-1">
          Trainees assigned to you by an admin. Participation and performance shown here is scoped to these cohorts only.
        </p>
      </div>

      {loading && <p className="font-sans text-sm text-[#757682] text-center mt-6">Loading…</p>}
      {!loading && loadError && <p className="font-sans text-sm text-[#b3261e]">{loadError}</p>}
      {!loading && !loadError && cohortList.length === 0 && (
        <Panel>
          <p className="font-sans text-sm text-[#757682]">
            No cohorts assigned yet. An admin assigns trainees to you as a cohort.
          </p>
        </Panel>
      )}

      {!loading &&
        !loadError &&
        cohortList.map((cohort) => (
          <Panel key={cohort.cohort_id}>
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div>
                <h3 className="font-sans text-sm font-bold text-[#131b2e]">{cohort.name}</h3>
                <p className="font-mono text-[10px] text-[#8a8f9d]">
                  {cohort.member_count} trainee{cohort.member_count === 1 ? '' : 's'}
                </p>
              </div>
              <button
                type="button"
                onClick={() => toggleExpand(cohort.cohort_id)}
                className="font-sans text-xs text-[#00236f] underline"
              >
                {expandedId === cohort.cohort_id ? 'Hide performance' : 'View performance'}
              </button>
            </div>

            {expandedId === cohort.cohort_id && (
              <div className="mt-3 pt-3 border-t border-[#c5c5d3]/30 flex flex-col gap-2">
                {performanceLoading && <p className="font-sans text-xs text-[#757682]">Loading…</p>}
                {!performanceLoading && performanceError && (
                  <p className="font-sans text-xs text-[#b3261e]">{performanceError}</p>
                )}
                {!performanceLoading &&
                  !performanceError &&
                  performance.map((row) => (
                    <div
                      key={row.player_id}
                      className="flex items-center justify-between gap-2 py-1.5 border-b border-[#c5c5d3]/20 last:border-0"
                    >
                      <span className="font-sans text-xs text-[#131b2e]">{row.username}</span>
                      <div className="flex items-center gap-2 flex-wrap justify-end">
                        <Badge tone={row.courses_completed > 0 ? 'success' : 'default'}>
                          {row.courses_completed}/{row.courses_enrolled} courses
                        </Badge>
                        {row.assessments_taken > 0 ? (
                          <Badge tone={row.open_skill_gaps > 0 ? 'warning' : 'success'}>
                            {row.assessments_taken} assessment{row.assessments_taken === 1 ? '' : 's'}
                            {row.open_skill_gaps != null ? ` · ${row.open_skill_gaps} gap${row.open_skill_gaps === 1 ? '' : 's'}` : ''}
                          </Badge>
                        ) : (
                          <Badge>No assessments yet</Badge>
                        )}
                      </div>
                    </div>
                  ))}
                {!performanceLoading && !performanceError && performance.length === 0 && (
                  <p className="font-sans text-xs text-[#757682]">No members in this cohort yet.</p>
                )}
              </div>
            )}
          </Panel>
        ))}
    </div>
  );
}
