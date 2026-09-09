'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import { learning } from '@/lib/api/client';
import { RadarChart } from '@/components/RadarChart';
import { VectorBalanceCard } from '@/components/VectorBalanceCard';
import { CompetencyVectorCard } from '@/components/CompetencyVectorCard';
import { InferenceRationaleCard } from '@/components/InferenceRationaleCard';
import Panel from '@/components/ui/Panel';
import { BarChart3, Code, Gavel, Sparkles } from 'lucide-react';

// This page shows a gap analysis backed entirely by
// backend/services/learning_engine.py::analyse_competencies() (fetched via
// the idempotent GET /learning/pathway, not the assessment-creating POST) --
// every number here is real player data. An earlier version of this page
// used a hardcoded fictional 6-competency "MoSPI officer" mockup with no
// backend behind it; see git history (navya_hu branch) if that visual
// reference is ever needed again.
const CURRICULUM_ICON = {
  'dsa-fundamentals': Code,
  'official-statistics': BarChart3,
  'public-policy': Gavel,
  'digital-literacy': Sparkles,
};

const PRIORITY_STATUS = {
  critical: 'critical',
  high: 'moderate',
  medium: 'moderate',
  maintain: 'matched',
  unassessed: 'unassessed',
};

function toDimension(item, curriculum, t) {
  const requiredLevel = Math.max(1, Math.round(item.pathway_target ?? item.role_target ?? 3));
  const officerLevel = Math.round(item.observed_level ?? 0);
  const gapText =
    item.priority === 'unassessed'
      ? t('stats.notYetAssessed')
      : item.gap <= 0.05
        ? t('stats.onTarget')
        : `-${item.gap.toFixed(1)} ${t('stats.levels')}`;

  return {
    id: item.competency_id,
    name: item.label,
    subtitle: item.description,
    category: curriculum.name,
    status: PRIORITY_STATUS[item.priority] || 'moderate',
    officerLevel,
    requiredLevel,
    gapText,
    icon: CURRICULUM_ICON[curriculum.slug] || Sparkles,
    rationale: {
      observedLevel: item.observed_level ?? 0,
      observedLabel: item.observed_label || t('stats.notYetEvidenced'),
      pathwayTarget: item.pathway_target ?? item.role_target ?? requiredLevel,
      matchedRole: item.matched_role,
      gap: item.gap ?? 0,
      priority: item.priority,
      confidence: item.confidence || 'none',
      evidenceSources: item.evidence_sources || [],
      evidenceRecords: (item.evidence_records || []).map((r) => ({
        evidenceType: r.evidence_type,
        value: r.value,
        detail: r.detail,
      })),
      evidenceNote: item.evidence,
      recommendedAction: item.recommended_action,
    },
  };
}

export default function StatsPage() {
  const { ready } = useRequireAuth();
  const router = useRouter();
  const player = useAuthStore((s) => s.player);
  const { t, language } = useLanguage();
  const [selectedSlug, setSelectedSlug] = useState(null);
  const [selectedDimId, setSelectedDimId] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');

  const { data: profileData } = useQuery({
    queryKey: ['learning-profile', player?.player_id],
    queryFn: () => learning.getProfile(player.player_id),
    enabled: ready && !!player,
  });

  const { data: curriculaData } = useQuery({
    queryKey: ['curricula', language],
    queryFn: () => learning.getCurricula(language),
    enabled: ready && !!player,
  });

  const profile = profileData?.profile;
  const displayName = profile?.full_name || player?.username || '';
  const initials = displayName
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || '?';
  const curricula = curriculaData?.curricula || [];
  const targetSlugs = profile?.target_domains?.length ? profile.target_domains : curricula.map((c) => c.slug);
  const activeSlug = selectedSlug || targetSlugs[0] || curricula[0]?.slug;
  const activeCurriculum = curricula.find((c) => c.slug === activeSlug);

  const {
    data: pathwayData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['pathway', player?.player_id, activeSlug, language],
    queryFn: () => learning.getPathway(player.player_id, activeSlug, language),
    enabled: ready && !!player && !!activeSlug,
  });

  if (!ready || !player) return null;

  const gapItems = pathwayData?.pathway?.length ? pathwayData.pathway : pathwayData?.competencies || [];
  const dimensions = activeCurriculum
    ? [...gapItems].sort((a, b) => (b.gap ?? 0) - (a.gap ?? 0)).map((item) => toDimension(item, activeCurriculum, t))
    : [];
  const filteredDimensions = statusFilter === 'all' ? dimensions : dimensions.filter((d) => d.status === statusFilter);
  const radarDimensions = dimensions.slice(0, 8);
  const activeDimId = selectedDimId && dimensions.some((d) => d.id === selectedDimId) ? selectedDimId : dimensions[0]?.id;
  const selectedDimension = dimensions.find((d) => d.id === activeDimId);

  return (
    <div className="max-w-5xl mx-auto flex flex-col gap-5">
      <Panel>
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-11 h-11 rounded-xl bg-[#00236f] text-white flex items-center justify-center font-bold text-base shrink-0 shadow-sm">
              {initials}
            </div>
            <div className="flex flex-col">
              <h2 className="font-sans text-base text-[#00236f] font-bold">{displayName}</h2>
              <span className="font-sans text-xs text-[#444651] mt-0.5">
                {profile?.designation || t('stats.designationNotSet')} · {profile?.department || t('stats.departmentNotSet')}
                {' — '}
                <button
                  type="button"
                  onClick={() => router.push('/academy')}
                  className="text-[#00236f] underline cursor-pointer"
                >
                  {t('stats.completeProfile')}
                </button>
              </span>
            </div>
          </div>

          {curricula.length > 0 && (
            <div className="flex items-center gap-2 bg-[#f2f3ff] px-3 py-1.5 rounded-lg border border-[#c5c5d3]/30">
              <span className="font-mono text-xs text-[#757682]">{t('stats.curriculumLabel')}</span>
              <select
                value={activeSlug || ''}
                onChange={(e) => {
                  setSelectedSlug(e.target.value);
                  setSelectedDimId(null);
                }}
                className="bg-transparent text-[#00236f] font-mono text-xs font-semibold outline-none cursor-pointer pr-1"
              >
                {curricula.map((c) => (
                  <option key={c.slug} value={c.slug}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </Panel>

      {isLoading ? (
        <Panel>
          <p className="font-sans text-sm text-[#757682]">{t('stats.loading')}</p>
        </Panel>
      ) : isError ? (
        <Panel className="text-center">
          <p className="font-sans text-sm text-[#b3261e] mb-3">{t('stats.loadFailed')}</p>
          <button type="button" onClick={() => refetch()} className="text-sm text-[#00236f] underline cursor-pointer">
            {t('stats.retry')}
          </button>
        </Panel>
      ) : dimensions.length === 0 ? (
        <Panel className="text-center">
          <p className="font-sans text-sm text-[#444651]">
            {t('stats.noTrackedPrefix')} {activeCurriculum?.name || t('stats.thisCurriculum')}
            {t('stats.completeSelfAssessmentIn')}{' '}
            <button
              type="button"
              onClick={() => router.push('/academy')}
              className="text-[#00236f] underline cursor-pointer"
            >
              {t('stats.academyLink')}
            </button>{' '}
            {t('stats.toSeeGapAnalysis')}
          </p>
        </Panel>
      ) : (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
            <div className="lg:col-span-5 flex flex-col gap-4">
              {radarDimensions.length >= 3 ? (
                <RadarChart
                  dimensions={radarDimensions}
                  selectedDimensionId={activeDimId}
                  onSelectDimension={setSelectedDimId}
                />
              ) : (
                <Panel>
                  <p className="font-sans text-sm text-[#757682]">{t('stats.trackAtLeast3')}</p>
                </Panel>
              )}
              <VectorBalanceCard dimensions={dimensions} selectedFilter={statusFilter} onFilterChange={setStatusFilter} />
            </div>

            <div className="lg:col-span-7 flex flex-col gap-3">
              <div className="flex items-center justify-between px-1">
                <div>
                  <span className="font-mono text-[10px] text-[#757682] uppercase font-bold tracking-wider">
                    {activeCurriculum?.name}
                  </span>
                  <h2 className="font-sans text-base text-[#131b2e] font-bold">
                    {filteredDimensions.length} {t('stats.trackedSuffix')}{' '}
                    {filteredDimensions.length === 1 ? t('stats.competency') : t('stats.competencies')}
                  </h2>
                </div>
                {statusFilter !== 'all' && (
                  <button
                    type="button"
                    onClick={() => setStatusFilter('all')}
                    className="text-xs font-mono text-[#00236f] hover:underline cursor-pointer"
                  >
                    {t('stats.clearFilter')}
                  </button>
                )}
              </div>

              <div className="flex flex-col gap-2.5">
                {filteredDimensions.map((dim) => (
                  <CompetencyVectorCard
                    key={dim.id}
                    dimension={dim}
                    isSelected={activeDimId === dim.id}
                    onSelect={() => setSelectedDimId(dim.id)}
                  />
                ))}
              </div>
            </div>
          </div>

          {selectedDimension && (
            <InferenceRationaleCard dimension={selectedDimension} onViewLearningPathway={() => router.push('/academy')} />
          )}
        </>
      )}
    </div>
  );
}
