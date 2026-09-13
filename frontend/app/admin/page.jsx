'use client';

import { useQuery } from '@tanstack/react-query';
import { ShieldAlert, Users, ClipboardCheck, FileQuestion, Target, TrendingUp, GraduationCap, Activity } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import { learning } from '@/lib/api/client';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Panel from '@/components/ui/Panel';

// The three panels below (Training Effectiveness, Course Completion,
// Activity Trend) are new this session and not yet translated into the
// other 10 UI languages -- plain English strings only, same "not yet
// translated" honesty convention app/sampling-lab/page.jsx's own header
// comment documents for its new UI text, rather than a partial/guessed
// translation into 10 languages this session cannot verify.

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

      <Panel>
        <div className="flex items-center gap-2 mb-1">
          <TrendingUp size={16} className="text-[#00236f]" aria-hidden="true" />
          <h2 className="font-sans text-base font-bold text-[#131b2e]">Training Effectiveness</h2>
        </div>
        <p className="font-sans text-xs text-[#757682] mb-4">
          Per competency: the average change from each learner&rsquo;s earliest to latest measured score, across every
          learner who has re-assessed that competency at least twice. A learner assessed only once contributes nothing
          here (there is nothing yet to compare).
        </p>
        {data.training_effectiveness.length === 0 ? (
          <p className="font-sans text-sm text-[#757682]">No competency has been assessed more than once by the same learner yet.</p>
        ) : (
          <TrainingEffectivenessTable rows={data.training_effectiveness} />
        )}
      </Panel>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Panel>
          <div className="flex items-center gap-2 mb-4">
            <GraduationCap size={16} className="text-[#00236f]" aria-hidden="true" />
            <h2 className="font-sans text-base font-bold text-[#131b2e]">Course Completion</h2>
          </div>
          <div className="grid grid-cols-3 gap-3 mb-4">
            <MiniStat label="Enrolled" value={data.course_completion.total_enrollments} />
            <MiniStat label="Completed" value={data.course_completion.total_completions} />
            <MiniStat label="Rate" value={`${data.course_completion.completion_rate_pct}%`} />
          </div>
          {data.course_completion.by_course.length > 0 && (
            <ol className="flex flex-col gap-2">
              {data.course_completion.by_course.map((row) => (
                <li key={row.course_id} className="flex items-center justify-between border-b border-[#c5c5d3]/40 pb-2 gap-2">
                  <span className="font-sans text-sm text-[#131b2e] truncate">{row.title}</span>
                  <Badge tone={row.completion_rate_pct >= 50 ? 'success' : 'warning'}>
                    {row.completed}/{row.enrolled} &middot; {row.completion_rate_pct}%
                  </Badge>
                </li>
              ))}
            </ol>
          )}
        </Panel>

        <Panel>
          <div className="flex items-center gap-2 mb-1">
            <Activity size={16} className="text-[#00236f]" aria-hidden="true" />
            <h2 className="font-sans text-base font-bold text-[#131b2e]">Activity Trend</h2>
          </div>
          <p className="font-sans text-xs text-[#757682] mb-4">
            Real quiz attempts, judgment-simulation completions, and course completions per week. Shows only weeks with
            recorded activity -- nothing here is estimated or padded.
          </p>
          {data.activity_trend.length === 0 ? (
            <p className="font-sans text-sm text-[#757682]">No learning activity has been recorded yet.</p>
          ) : (
            <ActivityTrendChart weeks={data.activity_trend} />
          )}
        </Panel>
      </div>

      {data.emerging_skill_gaps.length > 0 && (
        <Panel>
          <h2 className="font-sans text-base font-bold text-[#131b2e] mb-1">Emerging Skill Gaps</h2>
          <p className="font-sans text-xs text-[#757682] mb-4">
            Gaps appearing more often in recent assessments than in earlier ones -- a trend, not just a current count
            (see &ldquo;Top skill gaps&rdquo; above for that).
          </p>
          <div className="flex flex-wrap gap-2">
            {data.emerging_skill_gaps.map((row) => (
              <Badge key={row.competency} tone="warning">
                {row.competency}: {row.earlier_count} &rarr; {row.recent_count}
              </Badge>
            ))}
          </div>
        </Panel>
      )}
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

function MiniStat({ label, value }) {
  return (
    <div className="bg-[#f2f3ff] rounded-lg p-3 text-center">
      <p className="font-sans text-base font-bold text-[#00236f]">{value}</p>
      <p className="font-sans text-xs text-[#757682] mt-1">{label}</p>
    </div>
  );
}

// Hand-built horizontal bar + numeric table -- no charting library, same
// convention as RadarChart.jsx/CompetencyVectorCard.jsx. A plain bar length
// alone would hide the sign (improvement vs. regression), so each row also
// prints the exact signed value and the honest "n=" sample size.
function TrainingEffectivenessTable({ rows }) {
  const maxAbs = Math.max(...rows.map((row) => Math.abs(row.avg_improvement)), 0.01);
  return (
    <div className="flex flex-col gap-3">
      {rows.map((row) => {
        const isImprovement = row.avg_improvement >= 0;
        const widthPct = Math.min(100, (Math.abs(row.avg_improvement) / maxAbs) * 100);
        return (
          <div key={row.competency_id}>
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="font-sans text-sm text-[#131b2e] font-medium truncate">{row.competency}</span>
              <span className="font-mono text-xs text-[#757682] shrink-0">
                {isImprovement ? '+' : ''}{row.avg_improvement} &middot; n={row.learner_count}
              </span>
            </div>
            <div className="w-full h-2 bg-[#eaedff] rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${isImprovement ? 'bg-[#1a7f4b]' : 'bg-[#b3261e]'}`}
                style={{ width: `${widthPct}%` }}
              ></div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Hand-built stacked-bar SVG for weekly activity -- honest substitute for a
// duration-based "learning hours" chart, since this app persists no
// duration field. Only the real weeks the backend returned are drawn; a
// short deployment history renders as a short chart, not a padded one.
function ActivityTrendChart({ weeks }) {
  const width = 320;
  const barGap = 10;
  const barWidth = Math.min(48, (width - barGap * (weeks.length + 1)) / weeks.length);
  const maxTotal = Math.max(...weeks.map((week) => week.total), 1);
  const chartHeight = 110;

  return (
    <div>
      <svg viewBox={`0 0 ${width} ${chartHeight + 30}`} className="w-full max-w-[360px]" role="img" aria-label="Weekly learning activity">
        {weeks.map((week, idx) => {
          const x = barGap + idx * (barWidth + barGap);
          const quizH = (week.quiz_attempts / maxTotal) * chartHeight;
          const scenarioH = (week.scenario_completions / maxTotal) * chartHeight;
          const courseH = (week.course_completions / maxTotal) * chartHeight;
          let yCursor = chartHeight;
          const segments = [
            { value: quizH, color: '#00236f' },
            { value: scenarioH, color: '#fe932c' },
            { value: courseH, color: '#1a7f4b' },
          ];
          return (
            <g key={week.week_start}>
              {segments.map((segment, segIdx) => {
                yCursor -= segment.value;
                return (
                  <rect
                    key={segIdx}
                    x={x}
                    y={yCursor}
                    width={barWidth}
                    height={segment.value}
                    fill={segment.color}
                  />
                );
              })}
              <text
                x={x + barWidth / 2}
                y={chartHeight + 14}
                textAnchor="middle"
                className="fill-[#757682] font-mono"
                style={{ fontSize: '8px' }}
              >
                {week.week_start.slice(5)}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="flex items-center gap-4 pt-2 border-t border-[#eaedff] flex-wrap">
        <Legend color="#00236f" label="Quiz attempts" />
        <Legend color="#fe932c" label="Scenario completions" />
        <Legend color="#1a7f4b" label="Course completions" />
      </div>
    </div>
  );
}

function Legend({ color, label }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="w-2.5 h-2.5 rounded-sm inline-block" style={{ backgroundColor: color }}></span>
      <span className="font-sans text-xs text-[#444651]">{label}</span>
    </div>
  );
}
