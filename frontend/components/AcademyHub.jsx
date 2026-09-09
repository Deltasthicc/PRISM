'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { BookOpen, BrainCircuit, FileQuestion, ShieldCheck } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { game, learning } from '@/lib/api/client';
import { useAuthStore } from '@/store/useAuthStore';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Panel from '@/components/ui/Panel';

const EMPTY_PROFILE = {
  designation: '',
  department: '',
  job_role: '',
  current_assignment: '',
  educational_qualifications: '',
  years_experience: 0,
  previous_trainings: [],
  career_goal: '',
  preferred_language: 'English',
  experience_level: 'beginner',
  target_domains: [],
};

const LINK_BUTTON_CLASS = [
  'inline-flex items-center font-sans text-sm font-semibold px-4 py-2.5 rounded-lg transition-colors',
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#00236f]',
].join(' ');

export default function AcademyHub() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((state) => state.player);
  const { t, language } = useLanguage();
  const [profile, setProfile] = useState(EMPTY_PROFILE);
  const [selectedSlug, setSelectedSlug] = useState('official-statistics');
  const [working, setWorking] = useState('');
  const [error, setError] = useState('');

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['academy', player?.player_id, language],
    queryFn: async () => {
      const [curricula, dungeons, profileData, integrations] = await Promise.all([
        learning.getCurricula(language),
        game.listDungeons(),
        learning.getProfile(player.player_id),
        learning.getIntegrationStatus(language),
      ]);
      return { curricula: curricula.curricula, dungeons, profile: profileData.profile, integrations };
    },
    enabled: ready && Boolean(player),
  });

  useEffect(() => {
    if (data?.profile) setProfile({ ...EMPTY_PROFILE, ...data.profile });
  }, [data?.profile]);

  if (!ready || isLoading) {
    return <p className="font-sans text-sm text-[#757682] text-center mt-10">{t('academy.loadingAcademy')}</p>;
  }
  if (isError || !data) {
    return (
      <div className="flex flex-col items-center gap-3 mt-10" role="alert">
        <p className="font-sans text-sm text-[#b3261e]">{t('academy.loadFailed')}</p>
        <Button variant="ghost" onClick={() => refetch()}>{t('academy.retry')}</Button>
      </div>
    );
  }

  const dungeonBySlug = Object.fromEntries(data.dungeons.map((dungeon) => [dungeon.slug, dungeon]));

  async function saveProfile(event) {
    event.preventDefault();
    setWorking('profile');
    setError('');
    try {
      const result = await learning.updateProfile(player.player_id, {
        ...profile,
        years_experience: Number(profile.years_experience) || 0,
        target_domains: Array.from(new Set([selectedSlug, ...(profile.target_domains || [])])),
        previous_trainings: Array.isArray(profile.previous_trainings) ? profile.previous_trainings : [],
      });
      setProfile({ ...EMPTY_PROFILE, ...result.profile });
    } catch (cause) {
      setError(cause.message);
    } finally {
      setWorking('');
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <Badge tone="accent">{t('academy.betaBadge')}</Badge>
        <h1 className="font-sans text-xl font-bold text-[#00236f] mt-3">{t('academy.heading')}</h1>
        <p className="font-sans text-sm text-[#757682] mt-2 max-w-4xl">{t('academy.description')}</p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Capability icon={BrainCircuit} title={t('academy.capabilityDiagnosisTitle')} body={t('academy.capabilityDiagnosisBody')} />
        <Capability icon={BookOpen} title={t('academy.capabilityDisciplinesTitle')} body={t('academy.capabilityDisciplinesBody')} />
        <Capability icon={ShieldCheck} title={t('academy.capabilityIntegrationsTitle')} body={`iGOT mode: ${data.integrations.igot.mode}. No fake enrolment or progress sync.`} />
      </div>

      {error && (
        <div className="border border-[#f5c6c2] bg-[#fce8e6] rounded-lg p-3 font-sans text-sm text-[#b3261e]" role="alert">
          {error}
        </div>
      )}

      <Panel variant="accent">
        <h2 className="font-sans text-base font-bold text-[#00236f] mb-4">{t('academy.section1Heading')}</h2>
        <form onSubmit={saveProfile} className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input id="designation" label={t('academy.designationLabel')} value={profile.designation || ''} onChange={(event) => setProfile({ ...profile, designation: event.target.value })} placeholder="Statistical Officer" />
          <Input id="department" label={t('academy.departmentLabel')} value={profile.department || ''} onChange={(event) => setProfile({ ...profile, department: event.target.value })} placeholder="MoSPI / State department / University" />
          <Input id="job-role" label={t('academy.jobRoleLabel')} value={profile.job_role || ''} onChange={(event) => setProfile({ ...profile, job_role: event.target.value })} placeholder="Survey design and data quality" />
          <Input id="years-experience" label={t('academy.yearsExperienceLabel')} type="number" min="0" max="60" value={profile.years_experience ?? 0} onChange={(event) => setProfile({ ...profile, years_experience: event.target.value })} />
          <Input id="current-assignment" label={t('academy.currentAssignmentLabel')} textarea rows="3" value={profile.current_assignment || ''} onChange={(event) => setProfile({ ...profile, current_assignment: event.target.value })} placeholder="Responsibilities, datasets, programmes, or decisions you currently support" />
          <Input
            id="previous-trainings"
            label={t('academy.previousTrainingLabel')}
            textarea
            rows="3"
            value={(profile.previous_trainings || []).join(', ')}
            onChange={(event) => setProfile({
              ...profile,
              previous_trainings: event.target.value.split(',').map((item) => item.trim()).filter(Boolean),
            })}
            placeholder="Survey sampling, Python foundations, data visualisation"
          />
          <label className="flex flex-col gap-1.5">
            <span className="font-sans text-xs font-semibold text-[#444651]">{t('academy.experienceLevelLabel')}</span>
            <select value={profile.experience_level} onChange={(event) => setProfile({ ...profile, experience_level: event.target.value })} className="bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]">
              <option value="beginner">{t('academy.levelBeginner')}</option>
              <option value="intermediate">{t('academy.levelIntermediate')}</option>
              <option value="advanced">{t('academy.levelAdvanced')}</option>
              <option value="expert">{t('academy.levelExpert')}</option>
            </select>
          </label>
          <Input id="preferred-language" label={t('academy.preferredLanguageLabel')} value={profile.preferred_language || 'English'} onChange={(event) => setProfile({ ...profile, preferred_language: event.target.value })} placeholder="English" />
          <Input id="qualifications" label={t('academy.qualificationsLabel')} textarea rows="3" value={profile.educational_qualifications || ''} onChange={(event) => setProfile({ ...profile, educational_qualifications: event.target.value })} placeholder="Degrees, certifications, or equivalent experience" />
          <Input id="career-goal" label={t('academy.careerGoalLabel')} textarea rows="3" value={profile.career_goal || ''} onChange={(event) => setProfile({ ...profile, career_goal: event.target.value })} placeholder="What should this pathway help you do?" />
          <div className="md:col-span-2">
            <Button type="submit" disabled={working === 'profile'}>
              {working === 'profile' ? t('academy.savingButton') : profile.profile_id ? t('academy.saveProfileButton') : t('academy.createProfileButton')}
            </Button>
          </div>
        </form>
      </Panel>

      <section aria-labelledby="paths-heading">
        <h2 id="paths-heading" className="font-sans text-base font-bold text-[#00236f] mb-4">{t('academy.section2Heading')}</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {data.curricula.map((curriculum) => {
            const dungeon = dungeonBySlug[curriculum.slug];
            const active = curriculum.slug === selectedSlug;
            return (
              <Panel key={curriculum.slug} variant={active ? 'accent' : 'default'}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-sans text-sm font-semibold text-[#131b2e]">{curriculum.name}</h3>
                    <p className="font-sans text-sm text-[#757682] mt-2">{curriculum.description}</p>
                  </div>
                  <Badge tone={curriculum.source.includes('demo') ? 'warning' : 'default'}>{curriculum.source}</Badge>
                </div>
                <div className="flex gap-2 flex-wrap mt-3">
                  <Badge tone="accent">{curriculum.level_band}</Badge>
                  <Badge tone="default">{curriculum.competency_count} competencies</Badge>
                </div>
                <p className="font-sans text-sm text-[#757682] mt-3">{t('academy.forAudience')} {curriculum.audience}</p>
                <div className="flex flex-wrap gap-2 mt-4">
                  <Button variant={active ? 'primary' : 'ghost'} onClick={() => setSelectedSlug(curriculum.slug)}>
                    {active ? t('academy.selectedBadge') : t('academy.assessThisPath')}
                  </Button>
                  {dungeon && (
                    <Link
                      href="/dungeon"
                      className={`${LINK_BUTTON_CLASS} bg-[#fe932c] text-white hover:bg-[#e57e1a]`}
                    >
                      {t('academy.startQuest')}
                    </Link>
                  )}
                </div>
              </Panel>
            );
          })}
        </div>
      </section>

      <Panel variant="accent">
        <h2 className="font-sans text-base font-bold text-[#00236f] mb-2">{t('academy.section3Heading')}</h2>
        <p className="font-sans text-sm text-[#757682] mb-5">{t('academy.section3Body')}</p>
        <Link href="/stats" className={`${LINK_BUTTON_CLASS} bg-[#00236f] text-white hover:bg-[#001a54]`}>
          {t('academy.viewCompetencyVector')}
        </Link>
      </Panel>

      <Panel variant="accent">
        <div className="flex items-center gap-2 mb-2">
          <FileQuestion className="text-[#00236f]" size={18} aria-hidden="true" />
          <h2 className="font-sans text-base font-bold text-[#00236f]">{t('academy.section4Heading')}</h2>
        </div>
        <p className="font-sans text-sm text-[#757682] mb-5">{t('academy.section4Body')}</p>
        <Link href="/quiz" className={`${LINK_BUTTON_CLASS} bg-[#00236f] text-white hover:bg-[#001a54]`}>
          {t('nav.sourceQuizGenerator')}
        </Link>
      </Panel>
    </div>
  );
}

function Capability({ icon: Icon, title, body }) {
  return (
    <Panel>
      <Icon className="text-[#00236f] mb-2" size={20} aria-hidden="true" />
      <h2 className="font-sans text-sm font-semibold text-[#131b2e]">{title}</h2>
      <p className="font-sans text-sm text-[#757682] mt-2">{body}</p>
    </Panel>
  );
}
