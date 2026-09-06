'use client';

import { useQuery } from '@tanstack/react-query';
import { ShieldAlert, Users, ClipboardCheck, FileQuestion, Target } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import { learning } from '@/lib/api/client';
import PixelBadge from '@/components/ui/PixelBadge';
import PixelButton from '@/components/ui/PixelButton';
import PixelPanel from '@/components/ui/PixelPanel';

const PRIORITY_TONE = { critical: 'blood', high: 'ember', medium: 'gold', maintain: 'arcane', unknown: 'stone' };
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
    return <p className="font-body text-parchment-dim text-center mt-10">{t('admin.loading')}</p>;
  }
  if (isError || !data) {
    return (
      <div className="flex flex-col items-center gap-3 mt-10" role="alert">
        <p className="font-body text-blood">{t('admin.loadFailed')}</p>
        <PixelButton variant="ghost" onClick={() => refetch()}>{t('admin.retry')}</PixelButton>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <PixelBadge tone="gold">{t('admin.badge')}</PixelBadge>
        <h1 className="font-display text-base text-parchment mt-3">{t('admin.heading')}</h1>
        <p className="font-body text-xl text-parchment-dim mt-2 max-w-3xl">{t('admin.subtitle')}</p>
      </header>

      <PixelPanel>
        <div className="flex items-start gap-3">
          <ShieldAlert className="text-blood shrink-0 mt-1" aria-hidden="true" />
          <div>
            <h2 className="font-display text-[10px] text-blood">{t('admin.notSecureHeading')}</h2>
            <p className="font-body text-parchment-dim mt-2">
              {data.privacy_note} {t('admin.notSecureBodyBefore')}{' '}
              <span className="text-parchment">docs/contracts/identity-authorization.md</span>{' '}
              {t('admin.notSecureBodySection')}
            </p>
          </div>
        </div>
      </PixelPanel>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Stat icon={Users} label={t('admin.learners')} value={data.learners} />
        <Stat icon={ClipboardCheck} label={t('admin.profilesCompleted')} value={data.profiles_completed} />
        <Stat icon={Target} label={t('admin.assessmentsRun')} value={data.assessments_completed} />
        <Stat icon={FileQuestion} label={t('admin.quizzesGenerated')} value={data.quizzes_generated} />
      </div>

      <PixelPanel>
        <h2 className="font-display text-xs text-gold mb-4">{t('admin.topSkillGaps')}</h2>
        {data.top_skill_gaps.length === 0 ? (
          <p className="font-body text-parchment-dim">{t('admin.noAssessments')}</p>
        ) : (
          <ol className="flex flex-col gap-2">
            {data.top_skill_gaps.map((row) => (
              <li key={row.competency} className="flex items-center justify-between border-b-2 border-black pb-2">
                <span className="font-body text-parchment">{row.competency}</span>
                <PixelBadge tone="ember">{row.learner_count} {row.learner_count === 1 ? t('admin.learner') : t('admin.learnerPlural')}</PixelBadge>
              </li>
            ))}
          </ol>
        )}
      </PixelPanel>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <PixelPanel>
          <h2 className="font-display text-xs text-gold mb-4">{t('admin.gapPriorityBreakdown')}</h2>
          <div className="flex flex-wrap gap-2">
            {Object.entries(data.gap_priorities).length === 0 && (
              <p className="font-body text-parchment-dim">{t('admin.noData')}</p>
            )}
            {Object.entries(data.gap_priorities).map(([priority, count]) => (
              <PixelBadge key={priority} tone={PRIORITY_TONE[priority] || 'stone'}>
                {t(`enums.${PRIORITY_KEY[priority] || 'priorityUnassessed'}`)}: {count}
              </PixelBadge>
            ))}
          </div>
        </PixelPanel>

        <PixelPanel>
          <h2 className="font-display text-xs text-gold mb-4">{t('admin.providerIntegrationStatus')}</h2>
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
