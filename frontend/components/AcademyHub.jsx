'use client';

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { BookOpen, BrainCircuit, FileQuestion, ShieldCheck } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { game, learning } from '@/lib/api/client';
import { useAuthStore } from '@/store/useAuthStore';
import PixelBadge from '@/components/ui/PixelBadge';
import PixelButton from '@/components/ui/PixelButton';
import PixelInput from '@/components/ui/PixelInput';
import PixelPanel from '@/components/ui/PixelPanel';

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

const PRIORITY_TONE = { critical: 'blood', high: 'ember', medium: 'gold', maintain: 'arcane' };
const LINK_BUTTON_CLASS = [
  'inline-block font-display text-xs px-4 py-3 border-4 border-black shadow-pixel-sm',
  'transition-transform active:translate-y-1 active:shadow-none',
  'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-arcane',
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
    return <p className="font-body text-parchment-dim text-center mt-10">Preparing your academy…</p>;
  }
  if (isError || !data) {
    return (
      <div className="flex flex-col items-center gap-3 mt-10" role="alert">
        <p className="font-body text-blood">The academy could not be loaded.</p>
        <PixelButton variant="ghost" onClick={() => refetch()}>RETRY</PixelButton>
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
        <PixelBadge tone="arcane">SKILL INTELLIGENCE BETA</PixelBadge>
        <h1 className="font-display text-base text-parchment mt-3">LEARNING ACADEMY</h1>
        <p className="font-body text-xl text-parchment-dim mt-2 max-w-4xl">
          Build a role-aware competency profile, diagnose gaps, follow an explainable learning path,
          practise through adaptive quests, and generate source-grounded quizzes from your own material.
        </p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Capability icon={BrainCircuit} title="Explainable diagnosis" body="Combines demonstrated performance with self-assessment and exposes every score." />
        <Capability icon={BookOpen} title="Multiple disciplines" body="Official statistics, public policy, digital literacy, and DSA share one data-driven engine." />
        <Capability icon={ShieldCheck} title="Honest integrations" body={`iGOT mode: ${data.integrations.igot.mode}. No fake enrolment or progress sync.`} />
      </div>

      {error && <div className="border-4 border-blood bg-blood/10 p-3 font-body text-blood" role="alert">{error}</div>}

      <PixelPanel variant="arcane">
        <h2 className="font-display text-xs text-arcane mb-4">1. YOUR COMPETENCY PROFILE</h2>
        <form onSubmit={saveProfile} className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <PixelInput id="designation" label="DESIGNATION" value={profile.designation || ''} onChange={(event) => setProfile({ ...profile, designation: event.target.value })} placeholder="Statistical Officer" />
          <PixelInput id="department" label="DEPARTMENT / ORGANISATION" value={profile.department || ''} onChange={(event) => setProfile({ ...profile, department: event.target.value })} placeholder="MoSPI / State department / University" />
          <PixelInput id="job-role" label="JOB ROLE" value={profile.job_role || ''} onChange={(event) => setProfile({ ...profile, job_role: event.target.value })} placeholder="Survey design and data quality" />
          <PixelInput id="years-experience" label="YEARS OF EXPERIENCE" type="number" min="0" max="60" value={profile.years_experience ?? 0} onChange={(event) => setProfile({ ...profile, years_experience: event.target.value })} />
          <PixelInput id="current-assignment" label="CURRENT ASSIGNMENT" textarea rows="3" value={profile.current_assignment || ''} onChange={(event) => setProfile({ ...profile, current_assignment: event.target.value })} placeholder="Responsibilities, datasets, programmes, or decisions you currently support" />
          <PixelInput
            id="previous-trainings"
            label="PREVIOUS TRAINING (COMMA-SEPARATED)"
            textarea
            rows="3"
            value={(profile.previous_trainings || []).join(', ')}
            onChange={(event) => setProfile({
              ...profile,
              previous_trainings: event.target.value.split(',').map((item) => item.trim()).filter(Boolean),
            })}
            placeholder="Survey sampling, Python foundations, data visualisation"
          />
          <label className="flex flex-col gap-2">
            <span className="font-display text-[10px] text-arcane">CURRENT EXPERIENCE LEVEL</span>
            <select value={profile.experience_level} onChange={(event) => setProfile({ ...profile, experience_level: event.target.value })} className="bg-void text-parchment font-body text-lg px-3 py-2 border-4 border-black focus:border-arcane">
              <option value="beginner">Beginner</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
              <option value="expert">Expert</option>
            </select>
          </label>
          <PixelInput id="preferred-language" label="PREFERRED LANGUAGE" value={profile.preferred_language || 'English'} onChange={(event) => setProfile({ ...profile, preferred_language: event.target.value })} placeholder="English" />
          <PixelInput id="qualifications" label="EDUCATIONAL QUALIFICATIONS" textarea rows="3" value={profile.educational_qualifications || ''} onChange={(event) => setProfile({ ...profile, educational_qualifications: event.target.value })} placeholder="Degrees, certifications, or equivalent experience" />
          <PixelInput id="career-goal" label="LEARNING / CAREER GOAL" textarea rows="3" value={profile.career_goal || ''} onChange={(event) => setProfile({ ...profile, career_goal: event.target.value })} placeholder="What should this pathway help you do?" />
          <div className="md:col-span-2">
            <PixelButton type="submit" variant="arcane" disabled={working === 'profile'}>
              {working === 'profile' ? 'SAVING…' : profile.profile_id ? 'UPDATE PROFILE' : 'CREATE PROFILE'}
            </PixelButton>
          </div>
        </form>
      </PixelPanel>

      <section aria-labelledby="paths-heading">
        <h2 id="paths-heading" className="font-display text-xs text-gold mb-4">2. CHOOSE A LEARNING PATH</h2>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {data.curricula.map((curriculum) => {
            const dungeon = dungeonBySlug[curriculum.slug];
            const active = curriculum.slug === selectedSlug;
            return (
              <PixelPanel key={curriculum.slug} variant={active ? 'arcane' : 'default'}>
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="font-display text-[11px] text-parchment">{curriculum.name}</h3>
                    <p className="font-body text-parchment-dim mt-2">{curriculum.description}</p>
                  </div>
                  <PixelBadge tone={curriculum.source.includes('demo') ? 'ember' : 'stone'}>{curriculum.source}</PixelBadge>
                </div>
                <div className="flex gap-2 flex-wrap mt-3">
                  <PixelBadge tone="gold">{curriculum.level_band}</PixelBadge>
                  <PixelBadge tone="arcane">{curriculum.competency_count} competencies</PixelBadge>
                </div>
                <p className="font-body text-sm text-parchment-dim mt-3">For: {curriculum.audience}</p>
                <div className="flex flex-wrap gap-2 mt-4">
                  <PixelButton variant={active ? 'arcane' : 'ghost'} onClick={() => { setSelectedSlug(curriculum.slug); setAssessment(null); setRatings({}); }}>
                    {active ? 'SELECTED' : 'ASSESS THIS PATH'}
                  </PixelButton>
                  {dungeon && (
                    <Link
                      href={`/dungeon/${dungeon.dungeon_id}`}
                      className={`${LINK_BUTTON_CLASS} bg-gold text-void hover:bg-gold/90`}
                    >
                      START QUEST
                    </Link>
                  )}
                </div>
              </PixelPanel>
            );
          })}
        </div>
      </section>

      {selected && (
        <PixelPanel>
          <h2 className="font-display text-xs text-gold mb-2">3. QUICK COMPETENCY DIAGNOSTIC</h2>
          <p className="font-body text-parchment-dim mb-5">
            Rate your current proficiency from 0 (no evidence) to 5 (expert). Quest performance is weighted more heavily when available.
          </p>
          <div className="flex flex-col gap-4">
            {selected.competencies.map((competency) => (
              <label key={competency.id} className="grid grid-cols-1 md:grid-cols-[1fr_240px] gap-3 border-b-2 border-black pb-4">
                <span>
                  <span className="font-display text-[10px] text-parchment">{competency.label}</span>
                  <span className="font-body text-sm text-parchment-dim block mt-1">{competency.description}</span>
                </span>
                <span className="flex items-center gap-3">
                  <input type="range" min="0" max="5" step="0.5" value={ratings[competency.id] ?? 0} onChange={(event) => setRatings({ ...ratings, [competency.id]: Number(event.target.value) })} className="w-full accent-teal-300" />
                  <output className="font-display text-xs text-gold w-8">{ratings[competency.id] ?? 0}</output>
                </span>
              </label>
            ))}
          </div>
          <PixelButton className="mt-5" variant="arcane" onClick={runAssessment} disabled={working === 'assessment'}>
            {working === 'assessment' ? 'ANALYSING…' : 'IDENTIFY MY GAPS'}
          </PixelButton>
        </PixelPanel>
      )}

      {assessment && <AssessmentResults assessment={assessment} dungeon={dungeonBySlug[selectedSlug]} />}

      <PixelPanel variant="arcane">
        <div className="flex items-center gap-2 mb-2">
          <FileQuestion className="text-arcane" aria-hidden="true" />
          <h2 className="font-display text-xs text-arcane">4. CREATE A GROUNDED QUIZ</h2>
        </div>
        <p className="font-body text-parchment-dim mb-4">
          Upload up to 5 MB in TXT, Markdown, PDF, or DOCX. Every generated answer includes a source excerpt; ungrounded model output is rejected.
          Without a configured model key, the deterministic fallback retains source wording and uses an English question template.
        </p>
        <form onSubmit={createQuiz} className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <PixelInput id="quiz-title" name="title" label="QUIZ TITLE" required defaultValue="My learning material quiz" />
          <PixelInput id="quiz-language" name="language" label="OUTPUT LANGUAGE" required defaultValue={profile.preferred_language || 'English'} />
          <label className="flex flex-col gap-2">
            <span className="font-display text-[10px] text-arcane">DIFFICULTY</span>
            <select name="difficulty" defaultValue="mixed" className="bg-void text-parchment font-body text-lg px-3 py-2 border-4 border-black focus:border-arcane">
              <option value="foundation">Foundation</option>
              <option value="intermediate">Intermediate</option>
              <option value="advanced">Advanced</option>
              <option value="mixed">Mixed</option>
            </select>
          </label>
          <PixelInput id="question-count" name="question_count" label="QUESTIONS (3-10)" type="number" min="3" max="10" defaultValue="5" />
          <label className="md:col-span-2 flex flex-col gap-2">
            <span className="font-display text-[10px] text-arcane">LEARNING MATERIAL</span>
            <input name="learning_file" type="file" required accept=".txt,.md,.pdf,.docx" className="bg-void text-parchment font-body text-base px-3 py-3 border-4 border-black file:bg-arcane file:text-void file:border-0 file:px-3 file:py-2" />
          </label>
          <div className="md:col-span-2">
            <PixelButton type="submit" variant="gold" disabled={working === 'quiz'}>
              {working === 'quiz' ? 'GENERATING & VALIDATING…' : 'GENERATE QUIZ'}
            </PixelButton>
          </div>
        </form>
      </PixelPanel>

      {quiz && <QuizPreview quiz={quiz} />}
    </div>
  );
}

function Capability({ icon: Icon, title, body }) {
  return (
    <PixelPanel>
      <Icon className="text-arcane mb-2" aria-hidden="true" />
      <h2 className="font-display text-[10px] text-parchment">{title.toUpperCase()}</h2>
      <p className="font-body text-base text-parchment-dim mt-2">{body}</p>
    </PixelPanel>
  );
}

function AssessmentResults({ assessment, dungeon }) {
  return (
    <PixelPanel variant="arcane">
      <h2 className="font-display text-xs text-arcane">YOUR PERSONALISED PATHWAY</h2>
      <p className="font-body text-parchment-dim mt-2">{assessment.method.note}</p>
      {assessment.pathway.length === 0 ? (
        <p className="font-body text-gold mt-4">No material gap was detected at your current pathway target. Use applied diagnostics to verify mastery.</p>
      ) : (
        <ol className="flex flex-col gap-3 mt-4">
          {assessment.pathway.map((step) => (
            <li key={step.competency_id} className="border-2 border-black bg-stone-dark p-3">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-display text-[10px] text-parchment">{step.step}. {step.label}</span>
                <PixelBadge tone={PRIORITY_TONE[step.priority] || 'stone'}>{step.priority}</PixelBadge>
                <PixelBadge tone="gold">gap {step.gap.toFixed(1)}</PixelBadge>
              </div>
              <p className="font-body text-sm text-parchment-dim mt-2">
                Observed {step.observed_level.toFixed(1)}/5 via {step.evidence}; pathway target {step.pathway_target.toFixed(1)}/5.
              </p>
              <p className="font-body text-parchment mt-1">{step.recommended_action}</p>
            </li>
          ))}
        </ol>
      )}

      <h3 className="font-display text-[10px] text-gold mt-6">RECOMMENDED LEARNING</h3>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mt-3">
        {assessment.courses.map((course) => {
          const external = course.url.startsWith('http');
          const href = course.provider_type === 'internal-practice' && dungeon
            ? `/dungeon/${dungeon.dungeon_id}`
            : course.url;
          return (
            <div key={course.course_id} className="border-2 border-black bg-stone-dark p-3">
              <div className="flex gap-2 flex-wrap">
                <PixelBadge tone={course.provider_type === 'internal-practice' ? 'arcane' : 'gold'}>{course.provider}</PixelBadge>
                <PixelBadge tone="stone">score {course.relevance_score.toFixed(1)}</PixelBadge>
              </div>
              <p className="font-display text-[9px] text-parchment mt-3">{course.title}</p>
              <p className="font-body text-sm text-parchment-dim mt-2">{course.verification_note}</p>
              {external ? (
                <a href={href} target="_blank" rel="noreferrer" className="font-body text-arcane underline mt-2 inline-block">Open authoritative catalog ↗</a>
              ) : (
                <Link href={href} className="font-body text-arcane underline mt-2 inline-block">Start adaptive practice →</Link>
              )}
            </div>
          );
        })}
      </div>
    </PixelPanel>
  );
}

function QuizPreview({ quiz }) {
  return (
    <PixelPanel>
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="font-display text-xs text-gold">{quiz.title}</h2>
        <PixelBadge tone="arcane">{quiz.generation_mode}</PixelBadge>
        <PixelBadge tone="stone">{quiz.language}</PixelBadge>
      </div>
      <ol className="flex flex-col gap-5 mt-5">
        {quiz.questions.map((question, questionIndex) => (
          <li key={`${question.question}-${questionIndex}`} className="border-2 border-black bg-stone-dark p-4">
            <p className="font-display text-[10px] text-parchment">{questionIndex + 1}. {question.question}</p>
            <ol className="font-body text-base text-parchment-dim mt-3 grid gap-1">
              {question.options.map((option, optionIndex) => (
                <li key={option} className={optionIndex === question.answer_index ? 'text-arcane' : ''}>
                  {String.fromCharCode(65 + optionIndex)}. {option}{optionIndex === question.answer_index ? ' ✓' : ''}
                </li>
              ))}
            </ol>
            <p className="font-body text-parchment mt-3">{question.explanation}</p>
            <blockquote className="font-body text-sm text-parchment-dim border-l-4 border-gold pl-3 mt-2">Source: {question.source_excerpt}</blockquote>
          </li>
        ))}
      </ol>
    </PixelPanel>
  );
}
