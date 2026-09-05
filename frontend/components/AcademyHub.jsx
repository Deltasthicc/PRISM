'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { BookOpen, BrainCircuit, FileQuestion, ShieldCheck } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { game, learning } from '@/lib/api/client';
import { useAuthStore } from '@/store/useAuthStore';
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

const PRIORITY_TONE = { critical: 'danger', high: 'warning', medium: 'accent', maintain: 'success' };
const LINK_BUTTON_CLASS = [
  'inline-flex items-center font-sans text-sm font-semibold px-4 py-2.5 rounded-lg transition-colors',
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#00236f]',
].join(' ');

export default function AcademyHub() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((state) => state.player);
  const [profile, setProfile] = useState(EMPTY_PROFILE);
  const [selectedSlug, setSelectedSlug] = useState('official-statistics');
  const [ratings, setRatings] = useState({});
  const [assessment, setAssessment] = useState(null);
  const [quiz, setQuiz] = useState(null);
  const [working, setWorking] = useState('');
  const [error, setError] = useState('');

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['academy', player?.player_id],
    queryFn: async () => {
      const [curricula, dungeons, profileData, integrations] = await Promise.all([
        learning.getCurricula(),
        game.listDungeons(),
        learning.getProfile(player.player_id),
        learning.getIntegrationStatus(),
      ]);
      return { curricula: curricula.curricula, dungeons, profile: profileData.profile, integrations };
    },
    enabled: ready && Boolean(player),
  });

  useEffect(() => {
    if (data?.profile) setProfile({ ...EMPTY_PROFILE, ...data.profile });
  }, [data?.profile]);

  const selected = useMemo(
    () => data?.curricula?.find((curriculum) => curriculum.slug === selectedSlug),
    [data?.curricula, selectedSlug]
  );

  if (!ready || isLoading) {
    return <p className="font-sans text-sm text-[#757682] text-center mt-10">Preparing your academy…</p>;
  }
  if (isError || !data) {
    return (
      <div className="flex flex-col items-center gap-3 mt-10" role="alert">
        <p className="font-sans text-sm text-[#b3261e]">The academy could not be loaded.</p>
        <Button variant="ghost" onClick={() => refetch()}>Retry</Button>
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

  async function runAssessment() {
    setWorking('assessment');
    setError('');
    setAssessment(null);
    try {
      setAssessment(await learning.assess(player.player_id, selectedSlug, ratings));
    } catch (cause) {
      setError(cause.message);
    } finally {
      setWorking('');
    }
  }

  async function createQuiz(event) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const file = form.get('learning_file');
    if (!(file instanceof File) || !file.size) {
      setError('Choose a .txt, .md, .pdf, or .docx learning file first.');
      return;
    }
    setWorking('quiz');
    setError('');
    setQuiz(null);
    try {
      setQuiz(await learning.generateQuiz({
        playerId: player.player_id,
        title: form.get('title'),
        difficulty: form.get('difficulty'),
        language: form.get('language'),
        questionCount: Number(form.get('question_count')),
        file,
      }));
    } catch (cause) {
      setError(cause.message);
    } finally {
      setWorking('');
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <header>
        <Badge tone="accent">Skill Intelligence Beta</Badge>
        <h1 className="font-sans text-xl font-bold text-[#00236f] mt-3">Learning Academy</h1>
        <p className="font-sans text-sm text-[#757682] mt-2 max-w-4xl">
          Build a role-aware competency profile, diagnose gaps, follow an explainable learning path,
          practise through adaptive quests, and generate source-grounded quizzes from your own material.
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Capability icon={BrainCircuit} title="Explainable diagnosis" body="Combines demonstrated performance with self-assessment and exposes every score." />
        <Capability icon={BookOpen} title="Multiple disciplines" body="Official statistics, public policy, digital literacy, and DSA share one data-driven engine." />
        <Capability icon={ShieldCheck} title="Honest integrations" body={`iGOT mode: ${data.integrations.igot.mode}. No fake enrolment or progress sync.`} />
      </div>

      {error && (
        <div className="border border-[#f5c6c2] bg-[#fce8e6] rounded-lg p-3 font-sans text-sm text-[#b3261e]" role="alert">
          {error}
        </div>
      )}

      <Panel variant="accent">
        <h2 className="font-sans text-base font-bold text-[#00236f] mb-4">1. Your competency profile</h2>
        <form onSubmit={saveProfile} className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input id="designation" label="Designation" value={profile.designation || ''} onChange={(event) => setProfile({ ...profile, designation: event.target.value })} placeholder="Statistical Officer" />
          <Input id="department" label="Department / Organisation" value={profile.department || ''} onChange={(event) => setProfile({ ...profile, department: event.target.value })} placeholder="MoSPI / State department / University" />
          <Input id="job-role" label="Job role" value={profile.job_role || ''} onChange={(event) => setProfile({ ...profile, job_role: event.target.value })} placeholder="Survey design and data quality" />
          <Input id="years-experience" label="Years of experience" type="number" min="0" max="60" value={profile.years_experience ?? 0} onChange={(event) => setProfile({ ...profile, years_experience: event.target.value })} />
          <Input id="current-assignment" label="Current assignment" textarea rows="3" value={profile.current_assignment || ''} onChange={(event) => setProfile({ ...profile, current_assignment: event.target.value })} placeholder="Responsibilities, datasets, programmes, or decisions you currently support" />
          <Input
            id="previous-trainings"
            label="Previous training (comma-separated)"
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
            <span className="font-sans text-xs font-semibold text-[#444651]">Current experience level</span>
            <select value={profile.experience_level} onChange={(event) => setProfile({ ...profile, experience_level: event.target.value })} className="bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]">
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
              <option value="expert">Expert</option>
            </select>
          </label>
          <Input id="preferred-language" label="Preferred language" value={profile.preferred_language || 'English'} onChange={(event) => setProfile({ ...profile, preferred_language: event.target.value })} placeholder="English" />
          <Input id="qualifications" label="Educational qualifications" textarea rows="3" value={profile.educational_qualifications || ''} onChange={(event) => setProfile({ ...profile, educational_qualifications: event.target.value })} placeholder="Degrees, certifications, or equivalent experience" />
          <Input id="career-goal" label="Learning / career goal" textarea rows="3" value={profile.career_goal || ''} onChange={(event) => setProfile({ ...profile, career_goal: event.target.value })} placeholder="What should this pathway help you do?" />
          <div className="md:col-span-2">
            <Button type="submit" disabled={working === 'profile'}>
              {working === 'profile' ? 'Saving…' : profile.profile_id ? 'Update profile' : 'Create profile'}
            </Button>
          </div>
        </form>
      </Panel>

      <section aria-labelledby="paths-heading">
        <h2 id="paths-heading" className="font-sans text-base font-bold text-[#00236f] mb-4">2. Choose a learning path</h2>
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
                <p className="font-sans text-sm text-[#757682] mt-3">For: {curriculum.audience}</p>
                <div className="flex flex-wrap gap-2 mt-4">
                  <Button variant={active ? 'primary' : 'ghost'} onClick={() => { setSelectedSlug(curriculum.slug); setAssessment(null); setRatings({}); }}>
                    {active ? 'Selected' : 'Assess this path'}
                  </Button>
                  {dungeon && (
                    <Link
                      href={`/dungeon/${dungeon.dungeon_id}`}
                      className={`${LINK_BUTTON_CLASS} bg-[#fe932c] text-white hover:bg-[#e57e1a]`}
                    >
                      Start quest
                    </Link>
                  )}
                </div>
              </Panel>
            );
          })}
        </div>
      </section>

      {selected && (
        <Panel>
          <h2 className="font-sans text-base font-bold text-[#00236f] mb-2">3. Quick competency diagnostic</h2>
          <p className="font-sans text-sm text-[#757682] mb-5">
            Rate your current proficiency from 0 (no evidence) to 5 (expert). Quest performance is weighted more heavily when available.
          </p>
          <div className="flex flex-col gap-4">
            {selected.competencies.map((competency) => (
              <label key={competency.id} className="grid grid-cols-1 md:grid-cols-[1fr_240px] gap-3 border-b border-[#c5c5d3]/40 pb-4">
                <span>
                  <span className="font-sans text-sm font-semibold text-[#131b2e]">{competency.label}</span>
                  <span className="font-sans text-sm text-[#757682] block mt-1">{competency.description}</span>
                </span>
                <span className="flex items-center gap-3">
                  <input type="range" min="0" max="5" step="0.5" value={ratings[competency.id] ?? 0} onChange={(event) => setRatings({ ...ratings, [competency.id]: Number(event.target.value) })} className="w-full accent-[#00236f]" />
                  <output className="font-sans text-sm font-semibold text-[#00236f] w-8">{ratings[competency.id] ?? 0}</output>
                </span>
              </label>
            ))}
          </div>
          <Button className="mt-5" onClick={runAssessment} disabled={working === 'assessment'}>
            {working === 'assessment' ? 'Analysing…' : 'Identify my gaps'}
          </Button>
        </Panel>
      )}

      {assessment && <AssessmentResults assessment={assessment} dungeon={dungeonBySlug[selectedSlug]} />}

      <Panel variant="accent">
        <div className="flex items-center gap-2 mb-2">
          <FileQuestion className="text-[#00236f]" size={18} aria-hidden="true" />
          <h2 className="font-sans text-base font-bold text-[#00236f]">4. Create a grounded quiz</h2>
        </div>
        <p className="font-sans text-sm text-[#757682] mb-4">
          Upload up to 5 MB in TXT, Markdown, PDF, or DOCX. Every generated answer includes a source excerpt; ungrounded model output is rejected.
          Without a configured model key, the deterministic fallback retains source wording and uses an English question template.
        </p>
        <form onSubmit={createQuiz} className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Input id="quiz-title" name="title" label="Quiz title" required defaultValue="My learning material quiz" />
          <Input id="quiz-language" name="language" label="Output language" required defaultValue={profile.preferred_language || 'English'} />
          <label className="flex flex-col gap-1.5">
            <span className="font-sans text-xs font-semibold text-[#444651]">Difficulty</span>
            <select name="difficulty" defaultValue="mixed" className="bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]">
              <option value="foundation">Foundation</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
              <option value="mixed">Mixed</option>
            </select>
          </label>
          <Input id="question-count" name="question_count" label="Questions (3-10)" type="number" min="3" max="10" defaultValue="5" />
          <label className="md:col-span-2 flex flex-col gap-1.5">
            <span className="font-sans text-xs font-semibold text-[#444651]">Learning material</span>
            <input name="learning_file" type="file" required accept=".txt,.md,.pdf,.docx" className="bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 file:bg-[#00236f] file:text-white file:border-0 file:rounded-md file:px-3 file:py-1.5 file:mr-3" />
          </label>
          <div className="md:col-span-2">
            <Button type="submit" variant="accent" disabled={working === 'quiz'}>
              {working === 'quiz' ? 'Generating & validating…' : 'Generate quiz'}
            </Button>
          </div>
        </form>
      </Panel>

      {quiz && <QuizPreview quiz={quiz} />}
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

function AssessmentResults({ assessment, dungeon }) {
  return (
    <Panel variant="accent">
      <h2 className="font-sans text-base font-bold text-[#00236f]">Your personalised pathway</h2>
      <p className="font-sans text-sm text-[#757682] mt-2">{assessment.method.note}</p>
      {assessment.pathway.length === 0 ? (
        <p className="font-sans text-sm text-[#904d00] mt-4">No material gap was detected at your current pathway target. Use applied diagnostics to verify mastery.</p>
      ) : (
        <ol className="flex flex-col gap-3 mt-4">
          {assessment.pathway.map((step) => (
            <li key={step.competency_id} className="border border-[#c5c5d3]/40 rounded-lg bg-[#f2f3ff] p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-sans text-sm font-semibold text-[#131b2e]">{step.step}. {step.label}</span>
                <Badge tone={PRIORITY_TONE[step.priority] || 'default'}>{step.priority}</Badge>
                <Badge tone="accent">gap {step.gap.toFixed(1)}</Badge>
              </div>
              <p className="font-sans text-sm text-[#757682] mt-2">
                Observed {step.observed_level.toFixed(1)}/5 via {step.evidence}; pathway target {step.pathway_target.toFixed(1)}/5.
              </p>
              <p className="font-sans text-sm text-[#131b2e] mt-1">{step.recommended_action}</p>
            </li>
          ))}
        </ol>
      )}

      <h3 className="font-sans text-sm font-bold text-[#00236f] mt-6">Recommended learning</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
        {assessment.courses.map((course) => {
          const external = course.url.startsWith('http');
          const href = course.provider_type === 'internal-practice' && dungeon
            ? `/dungeon/${dungeon.dungeon_id}`
            : course.url;
          return (
            <div key={course.course_id} className="border border-[#c5c5d3]/40 rounded-lg bg-[#f2f3ff] p-3">
              <div className="flex gap-2 flex-wrap">
                <Badge tone={course.provider_type === 'internal-practice' ? 'accent' : 'warning'}>{course.provider}</Badge>
                <Badge tone="default">score {course.relevance_score.toFixed(1)}</Badge>
              </div>
              <p className="font-sans text-sm font-semibold text-[#131b2e] mt-3">{course.title}</p>
              <p className="font-sans text-sm text-[#757682] mt-2">{course.verification_note}</p>
              {external ? (
                <a href={href} target="_blank" rel="noreferrer" className="font-sans text-sm text-[#00236f] hover:underline mt-2 inline-block">Open authoritative catalog ↗</a>
              ) : (
                <Link href={href} className="font-sans text-sm text-[#00236f] hover:underline mt-2 inline-block">Start adaptive practice →</Link>
              )}
            </div>
          );
        })}
      </div>
    </Panel>
  );
}

function QuizPreview({ quiz }) {
  return (
    <Panel>
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-sans text-base font-bold text-[#00236f]">{quiz.title}</h2>
        <Badge tone="accent">{quiz.generation_mode}</Badge>
        <Badge tone="default">{quiz.language}</Badge>
      </div>
      <ol className="flex flex-col gap-5 mt-5">
        {quiz.questions.map((question, questionIndex) => (
          <li key={`${question.question}-${questionIndex}`} className="border border-[#c5c5d3]/40 rounded-lg bg-[#f2f3ff] p-4">
            <p className="font-sans text-sm font-semibold text-[#131b2e]">{questionIndex + 1}. {question.question}</p>
            <ol className="font-sans text-sm text-[#444651] mt-3 grid gap-1">
              {question.options.map((option, optionIndex) => (
                <li key={option} className={optionIndex === question.answer_index ? 'text-[#00236f] font-medium' : ''}>
                  {String.fromCharCode(65 + optionIndex)}. {option}{optionIndex === question.answer_index ? ' ✓' : ''}
                </li>
              ))}
            </ol>
            <p className="font-sans text-sm text-[#131b2e] mt-3">{question.explanation}</p>
            <blockquote className="font-sans text-sm text-[#757682] border-l-4 border-[#fe932c] pl-3 mt-2">Source: {question.source_excerpt}</blockquote>
          </li>
        ))}
      </ol>
    </Panel>
  );
}
