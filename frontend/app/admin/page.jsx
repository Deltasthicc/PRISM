'use client';

import { useQuery } from '@tanstack/react-query';
import { ShieldAlert, Users, ClipboardCheck, FileQuestion, Target } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import { learning } from '@/lib/api/client';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Panel from '@/components/ui/Panel';

// An aggregate organization-metrics dashboard has no reason to look like a
// dungeon crawl -- it isn't part of Quest Mode's opt-in gamified layer, so
// it uses the same plain professional-shell components as /stats and
// /academy, not the Pixel* kit reserved for Quest's own opt-in routes.
const PRIORITY_TONE = { critical: 'danger', high: 'warning', medium: 'warning', maintain: 'success', unknown: 'default' };
const PRIORITY_KEY = {
  unassessed: 'priorityUnassessed',
  critical: 'priorityCritical',
  high: 'priorityHigh',
  medium: 'priorityMedium',
  maintain: 'priorityMaintain',
};

export default function AdminPage() {
  const { ready } = useRequireAuth();
  const { t, language } = useLanguage();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['admin-overview', language],
    queryFn: () => learning.getAdminOverview(language),
    enabled: ready,
  });

  if (!ready || isLoading) {
    return <p className="font-sans text-sm text-[#757682] text-center mt-10">{t('admin.loading')}</p>;
  }
  if (isError || !data) {
    return (
      <div className="flex flex-col items-center gap-3 mt-10" role="alert">
        <p className="font-sans text-sm text-[#b3261e]">{t('admin.loadFailed')}</p>
        <Button variant="ghost" onClick={() => refetch()}>{t('admin.retry')}</Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <Badge tone="warning">{t('admin.badge')}</Badge>
        <h1 className="font-sans text-lg font-bold text-[#00236f] mt-3">{t('admin.heading')}</h1>
        <p className="font-sans text-sm text-[#757682] mt-2 max-w-3xl">{t('admin.subtitle')}</p>
      </header>

      <Panel>
        <div className="flex items-start gap-3">
          <ShieldAlert className="text-[#b3261e] shrink-0 mt-1" aria-hidden="true" />
          <div>
            <h2 className="font-sans text-sm font-bold text-[#b3261e]">{t('admin.notSecureHeading')}</h2>
            <p className="font-sans text-sm text-[#757682] mt-2">
              {data.privacy_note} {t('admin.notSecureBodyBefore')}{' '}
              <span className="text-[#131b2e] font-mono text-xs">docs/contracts/identity-authorization.md</span>{' '}
              {t('admin.notSecureBodySection')}
            </p>
          </div>
        </div>
      </Panel>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Stat icon={Users} label={t('admin.learners')} value={data.learners} />
        <Stat icon={ClipboardCheck} label={t('admin.profilesCompleted')} value={data.profiles_completed} />
        <Stat icon={Target} label={t('admin.assessmentsRun')} value={data.assessments_completed} />
        <Stat icon={FileQuestion} label={t('admin.quizzesGenerated')} value={data.quizzes_generated} />
      </div>

      <Panel>
        <h2 className="font-sans text-base font-bold text-[#131b2e] mb-4">{t('admin.topSkillGaps')}</h2>
        {data.top_skill_gaps.length === 0 ? (
          <p className="font-sans text-sm text-[#757682]">{t('admin.noAssessments')}</p>
        ) : (
          <ol className="flex flex-col gap-2">
            {data.top_skill_gaps.map((row) => (
              <li key={row.competency} className="flex items-center justify-between border-b border-[#c5c5d3]/40 pb-2">
                <span className="font-sans text-sm text-[#131b2e]">{row.competency}</span>
                <Badge tone="warning">{row.learner_count} {row.learner_count === 1 ? t('admin.learner') : t('admin.learnerPlural')}</Badge>
              </li>
            ))}
          </ol>
        )}
      </Panel>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Panel>
          <h2 className="font-sans text-base font-bold text-[#131b2e] mb-4">{t('admin.gapPriorityBreakdown')}</h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(data.gap_priorities).length === 0 && (
              <p className="font-sans text-sm text-[#757682]">{t('admin.noData')}</p>
            )}
            {Object.entries(data.gap_priorities).map(([priority, count]) => (
              <Badge key={priority} tone={PRIORITY_TONE[priority] || 'default'}>
                {t(`enums.${PRIORITY_KEY[priority] || 'priorityUnassessed'}`)}: {count}
              </Badge>
            ))}
          </div>
        </Panel>

        <Panel>
          <h2 className="font-sans text-base font-bold text-[#131b2e] mb-4">{t('admin.providerIntegrationStatus')}</h2>
          <div className="flex flex-col gap-3">
            {Object.entries(data.integration_status).map(([provider, status]) => (
              <div key={provider} className="border-b border-[#c5c5d3]/40 pb-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs text-[#131b2e] uppercase">{provider}</span>
                  <Badge tone={status.mode === 'LIVE' ? 'accent' : 'warning'}>{status.mode}</Badge>
                </div>
                <p className="font-sans text-sm text-[#757682] mt-1">{status.detail}</p>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}

function Stat({ icon: Icon, label, value }) {
  return (
    <Panel>
      <Icon className="text-[#00236f] mb-2" aria-hidden="true" />
      <p className="font-sans text-lg font-bold text-[#131b2e]">{value}</p>
      <p className="font-sans text-sm text-[#757682] mt-1">{label}</p>
    </Panel>
  );
}
