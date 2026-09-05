'use client';

import { useQuery } from '@tanstack/react-query';
import { ShieldAlert, Users, ClipboardCheck, FileQuestion, Target } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { learning } from '@/lib/api/client';
import PixelBadge from '@/components/ui/PixelBadge';
import PixelButton from '@/components/ui/PixelButton';
import PixelPanel from '@/components/ui/PixelPanel';

const PRIORITY_TONE = { critical: 'blood', high: 'ember', medium: 'gold', maintain: 'arcane', unknown: 'stone' };

export default function AdminPage() {
  const { ready } = useRequireAuth();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['admin-overview'],
    queryFn: () => learning.getAdminOverview(),
    enabled: ready,
  });

  if (!ready || isLoading) {
    return <p className="font-body text-parchment-dim text-center mt-10">Loading aggregate overview…</p>;
  }
  if (isError || !data) {
    return (
      <div className="flex flex-col items-center gap-3 mt-10" role="alert">
        <p className="font-body text-blood">The admin overview could not be loaded.</p>
        <PixelButton variant="ghost" onClick={() => refetch()}>RETRY</PixelButton>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <PixelBadge tone="gold">ADMIN &middot; PROTOTYPE</PixelBadge>
        <h1 className="font-display text-base text-parchment mt-3">ORGANIZATION OVERVIEW</h1>
        <p className="font-body text-xl text-parchment-dim mt-2 max-w-3xl">
          Aggregate-only skill-gap demand across every learner. No individual profile, answer, or
          identifying record is ever returned by this endpoint.
        </p>
      </header>

      <PixelPanel>
        <div className="flex items-start gap-3">
          <ShieldAlert className="text-blood shrink-0 mt-1" aria-hidden="true" />
          <div>
            <h2 className="font-display text-[10px] text-blood">NOT PRODUCTION-SECURE</h2>
            <p className="font-body text-parchment-dim mt-2">
              {data.privacy_note} Anyone with a logged-in session can currently reach this page — there is
              no RBAC/OIDC boundary yet. The identity/RBAC primitives this route needs already exist
              (see <span className="text-parchment">docs/contracts/identity-authorization.md</span>{' '}
              section 6, &ldquo;Route handoff and present limitations&rdquo;) but are not yet attached here.
            </p>
          </div>
        </div>
      </PixelPanel>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Stat icon={Users} label="Learners" value={data.learners} />
        <Stat icon={ClipboardCheck} label="Profiles completed" value={data.profiles_completed} />
        <Stat icon={Target} label="Assessments run" value={data.assessments_completed} />
        <Stat icon={FileQuestion} label="Quizzes generated" value={data.quizzes_generated} />
      </div>

      <PixelPanel>
        <h2 className="font-display text-xs text-gold mb-4">TOP SKILL GAPS ACROSS THE ORGANIZATION</h2>
        {data.top_skill_gaps.length === 0 ? (
          <p className="font-body text-parchment-dim">No assessments have been run yet.</p>
        ) : (
          <ol className="flex flex-col gap-2">
            {data.top_skill_gaps.map((row) => (
              <li key={row.competency} className="flex items-center justify-between border-b-2 border-black pb-2">
                <span className="font-body text-parchment">{row.competency}</span>
                <PixelBadge tone="ember">{row.learner_count} learner{row.learner_count === 1 ? '' : 's'}</PixelBadge>
              </li>
            ))}
          </ol>
        )}
      </PixelPanel>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <PixelPanel>
          <h2 className="font-display text-xs text-gold mb-4">GAP PRIORITY BREAKDOWN</h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(data.gap_priorities).length === 0 && (
              <p className="font-body text-parchment-dim">No data yet.</p>
            )}
            {Object.entries(data.gap_priorities).map(([priority, count]) => (
              <PixelBadge key={priority} tone={PRIORITY_TONE[priority] || 'stone'}>
                {priority}: {count}
              </PixelBadge>
            ))}
          </div>
        </PixelPanel>

        <PixelPanel>
          <h2 className="font-display text-xs text-gold mb-4">PROVIDER INTEGRATION STATUS</h2>
          <div className="flex flex-col gap-3">
            {Object.entries(data.integration_status).map(([provider, status]) => (
              <div key={provider} className="border-b-2 border-black pb-2">
                <div className="flex items-center gap-2">
                  <span className="font-display text-[10px] text-parchment uppercase">{provider}</span>
                  <PixelBadge tone={status.mode === 'configured' ? 'arcane' : 'gold'}>{status.mode}</PixelBadge>
                </div>
                <p className="font-body text-sm text-parchment-dim mt-1">{status.detail}</p>
              </div>
            ))}
          </div>
        </PixelPanel>
      </div>
    </div>
  );
}

function Stat({ icon: Icon, label, value }) {
  return (
    <PixelPanel>
      <Icon className="text-arcane mb-2" aria-hidden="true" />
      <p className="font-display text-lg text-parchment">{value}</p>
      <p className="font-body text-sm text-parchment-dim mt-1">{label}</p>
    </PixelPanel>
  );
}
