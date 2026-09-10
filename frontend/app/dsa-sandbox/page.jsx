'use client';

import { useEffect, useMemo, useState } from 'react';
import dynamic from 'next/dynamic';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import clsx from 'clsx';
import {
  CheckCircle2,
  ChevronRight,
  Clock3,
  Code2,
  Loader2,
  Play,
  RotateCcw,
  Search,
  ServerCog,
  TerminalSquare,
  XCircle,
} from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import { learning } from '@/lib/api/client';
import Panel from '@/components/ui/Panel';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';

const CodeEditor = dynamic(() => import('./CodeEditor'), {
  ssr: false,
  loading: () => <div className="h-[430px] animate-pulse bg-[#0b1020]" />,
});

const DIFFICULTY_TONE = { easy: 'success', medium: 'warning', hard: 'danger' };
const FILE_EXTENSION = {
  python: 'py',
  javascript: 'js',
  java: 'java',
  cpp: 'cpp',
  csharp: 'cs',
};

function displayValue(value) {
  return JSON.stringify(value);
}

export default function DsaSandboxPage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);
  const { t } = useLanguage();

  const [selectedProblemId, setSelectedProblemId] = useState(null);
  const [language, setLanguage] = useState('python');
  const [query, setQuery] = useState('');
  const [difficulty, setDifficulty] = useState('all');
  const [codeByProblemAndLanguage, setCodeByProblemAndLanguage] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [submitError, setSubmitError] = useState('');

  const { data: profileData, isLoading: profileLoading } = useQuery({
    queryKey: ['learning-profile', player?.player_id],
    queryFn: () => learning.getProfile(player.player_id),
    enabled: ready && !!player,
  });
  const hasDsaFundamentals = Boolean(
    profileData?.profile?.target_domains?.includes('dsa-fundamentals')
  );

  const {
    data: problemsData,
    isLoading: problemsLoading,
    isError: problemsErrored,
    refetch: refetchProblems,
  } = useQuery({
    queryKey: ['dsa-sandbox-problems'],
    queryFn: () => learning.getDsaSandboxProblems(),
    enabled: ready && !!player && hasDsaFundamentals,
  });

  const problems = useMemo(() => problemsData?.problems || [], [problemsData]);
  const languages = problemsData?.languages || { python: 'Python' };
  const filteredProblems = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    return problems.filter((problem) => {
      const matchesDifficulty = difficulty === 'all' || problem.difficulty === difficulty;
      const matchesQuery =
        !normalizedQuery ||
        problem.title.toLowerCase().includes(normalizedQuery) ||
        problem.topic_label.toLowerCase().includes(normalizedQuery);
      return matchesDifficulty && matchesQuery;
    });
  }, [difficulty, problems, query]);

  useEffect(() => {
    if (!selectedProblemId && problems.length) setSelectedProblemId(problems[0].id);
  }, [problems, selectedProblemId]);

  const selected = problems.find((problem) => problem.id === selectedProblemId) || null;
  const codeKey = selected ? `${selected.id}::${language}` : null;
  const starterCode = selected
    ? selected.starter_code_by_language?.[language] ?? selected.starter_code
    : '';
  const code = selected
    ? codeByProblemAndLanguage[codeKey] ?? starterCode
    : '';

  function handleSelectProblem(problem) {
    setSelectedProblemId(problem.id);
    setResult(null);
    setSubmitError('');
  }

  function handleLanguageChange(nextLanguage) {
    setLanguage(nextLanguage);
    setResult(null);
    setSubmitError('');
  }

  function handleCodeChange(value) {
    if (!codeKey) return;
    setCodeByProblemAndLanguage((previous) => ({ ...previous, [codeKey]: value }));
  }

  function handleReset() {
    if (!codeKey) return;
    setCodeByProblemAndLanguage((previous) => ({ ...previous, [codeKey]: starterCode }));
    setResult(null);
    setSubmitError('');
  }

  async function handleRun() {
    if (!selected || submitting || !code.trim()) return;
    setSubmitting(true);
    setSubmitError('');
    setResult(null);
    try {
      const response = await learning.submitDsaSandbox(
        player.player_id,
        selected.id,
        code,
        language
      );
      setResult(response);
    } catch (cause) {
      setSubmitError(cause.message || t('dsaSandboxPage.judgeUnavailable'));
    } finally {
      setSubmitting(false);
    }
  }

  if (!ready) return null;

  if (profileLoading) {
    return (
      <Panel className="max-w-lg mx-auto mt-10">
        <div className="flex items-center justify-center gap-2 text-sm text-[#616779]">
          <Loader2 className="h-4 w-4 animate-spin" /> {t('dsaSandboxPage.loading')}
        </div>
      </Panel>
    );
  }

  if (!hasDsaFundamentals) {
    return (
      <Panel className="max-w-lg mx-auto mt-10 text-center">
        <p className="font-sans text-sm text-[#444651] mb-4">{t('dsaSandboxPage.notSelected')}</p>
        <Link href="/academy">
          <Button variant="primary">{t('dsaSandboxPage.addToProfile')}</Button>
        </Link>
      </Panel>
    );
  }

  return (
    <div className="mx-auto flex max-w-[1500px] flex-col gap-5">
      <header className="overflow-hidden rounded-2xl border border-[#d8deea] bg-gradient-to-r from-[#07152f] via-[#0b2450] to-[#12336c] px-5 py-5 text-white shadow-sm sm:px-7">
        <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-end">
          <div>
            <div className="mb-2 flex items-center gap-2 font-mono text-[10px] font-semibold uppercase tracking-[0.16em] text-[#9fc8ff]">
              <TerminalSquare className="h-4 w-4" /> Live coding workspace
            </div>
            <h1 className="text-2xl font-bold tracking-tight">{t('dsaSandboxPage.heading')}</h1>
            <p className="mt-1.5 max-w-3xl text-sm leading-6 text-[#c7d7ef]">
              {t('dsaSandboxPage.subtitle')}
            </p>
          </div>
          <div className="flex shrink-0 gap-2">
            <div className="rounded-xl border border-white/15 bg-white/10 px-3 py-2">
              <div className="font-mono text-lg font-bold">{problems.length}</div>
              <div className="text-[9px] uppercase tracking-wider text-[#b8c9e2]">problems</div>
            </div>
            <div className="rounded-xl border border-white/15 bg-white/10 px-3 py-2">
              <div className="font-mono text-lg font-bold">{Object.keys(languages).length}</div>
              <div className="text-[9px] uppercase tracking-wider text-[#b8c9e2]">languages</div>
            </div>
          </div>
        </div>
      </header>

      {problemsLoading ? (
        <Panel>
          <div className="flex items-center justify-center gap-2 text-sm text-[#616779]">
            <Loader2 className="h-4 w-4 animate-spin" /> {t('dsaSandboxPage.loading')}
          </div>
        </Panel>
      ) : problemsErrored ? (
        <Panel className="text-center">
          <p className="mb-3 text-sm text-[#b3261e]">{t('dsaSandboxPage.loadFailed')}</p>
          <Button variant="ghost" onClick={() => refetchProblems()}>
            {t('dsaSandboxPage.retry')}
          </Button>
        </Panel>
      ) : (
        <div className="grid grid-cols-1 items-start gap-5 xl:grid-cols-[310px_minmax(0,1fr)]">
          <aside className="overflow-hidden rounded-2xl border border-[#d8deea] bg-white shadow-sm xl:sticky xl:top-4">
            <div className="border-b border-[#e5e9f1] p-3">
              <h2 className="mb-2 px-1 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-[#687084]">
                {t('dsaSandboxPage.problemsHeading')}
              </h2>
              <label className="relative block">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[#7c8494]" />
                <input
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder={t('dsaSandboxPage.searchPlaceholder')}
                  className="w-full rounded-lg border border-[#d8deea] bg-[#f8fafc] py-2 pl-9 pr-3 text-xs outline-none transition focus:border-[#315a9e] focus:ring-2 focus:ring-[#315a9e]/10"
                />
              </label>
              <div className="mt-2 grid grid-cols-4 gap-1" aria-label="Difficulty filter">
                {['all', 'easy', 'medium', 'hard'].map((level) => (
                  <button
                    key={level}
                    type="button"
                    onClick={() => setDifficulty(level)}
                    className={clsx(
                      'rounded-md px-1 py-1.5 text-[9px] font-bold uppercase transition',
                      difficulty === level
                        ? 'bg-[#00236f] text-white'
                        : 'bg-[#f2f4f8] text-[#626a7b] hover:bg-[#e6eaf2]'
                    )}
                  >
                    {level}
                  </button>
                ))}
              </div>
            </div>
            <div className="max-h-[680px] space-y-1 overflow-y-auto p-2">
              {filteredProblems.map((problem, index) => (
                <button
                  key={problem.id}
                  type="button"
                  onClick={() => handleSelectProblem(problem)}
                  className={clsx(
                    'group flex w-full items-start gap-2 rounded-xl border px-2.5 py-3 text-left transition',
                    selected?.id === problem.id
                      ? 'border-[#8da9da] bg-[#edf3ff] shadow-sm'
                      : 'border-transparent hover:border-[#dde3ed] hover:bg-[#f8fafc]'
                  )}
                >
                  <span className="mt-0.5 w-6 shrink-0 font-mono text-[10px] text-[#81899a]">
                    {String(index + 1).padStart(2, '0')}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-sm font-semibold text-[#172033]">
                      {problem.title}
                    </span>
                    <span className="mt-1 flex items-center justify-between gap-2">
                      <span className="truncate font-mono text-[9px] text-[#697386]">
                        {problem.topic_label}
                      </span>
                      <Badge tone={DIFFICULTY_TONE[problem.difficulty] || 'default'}>
                        {problem.difficulty}
                      </Badge>
                    </span>
                  </span>
                  <ChevronRight className="mt-1 h-4 w-4 shrink-0 text-[#a0a8b7] group-hover:text-[#315a9e]" />
                </button>
              ))}
              {!filteredProblems.length && (
                <p className="px-3 py-8 text-center text-xs text-[#737b8c]">{t('dsaSandboxPage.noMatches')}</p>
              )}
            </div>
          </aside>

          {selected && (
            <main className="min-w-0 space-y-5">
              <section className="overflow-hidden rounded-2xl border border-[#d8deea] bg-white shadow-sm">
                <div className="border-b border-[#e5e9f1] px-5 py-4 sm:px-6">
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <div className="mb-1 flex items-center gap-2">
                        <Badge tone={DIFFICULTY_TONE[selected.difficulty] || 'default'}>
                          {selected.difficulty}
                        </Badge>
                        <span className="font-mono text-[10px] uppercase tracking-wider text-[#687084]">
                          {selected.topic_label} · {selected.test_case_count} tests
                        </span>
                      </div>
                      <h2 className="text-xl font-bold text-[#10182b]">{selected.title}</h2>
                    </div>
                    <Badge tone="accent">{selected.competency_id.replaceAll('_', ' ')}</Badge>
                  </div>
                </div>

                <div className="space-y-6 px-5 py-5 sm:px-6">
                  <p className="text-sm leading-7 text-[#3f4859]">{selected.prompt}</p>

                  <div>
                    <h3 className="mb-2 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-[#687084]">
                      {t('dsaSandboxPage.examples')}
                    </h3>
                    <div className="grid gap-3 lg:grid-cols-2">
                      {selected.examples.map((example, index) => (
                        <div key={index} className="rounded-xl border border-[#dfe5ee] bg-[#f8fafc] p-4">
                          <div className="mb-2 font-mono text-[10px] font-bold uppercase text-[#315a9e]">
                            {t('dsaSandboxPage.example')} {index + 1}
                          </div>
                          <dl className="space-y-2 font-mono text-xs">
                            <div className="grid grid-cols-[58px_1fr] gap-2">
                              <dt className="text-[#727b8d]">{t('dsaSandboxPage.input')}</dt>
                              <dd className="break-all text-[#14213d]">{displayValue(example.input)}</dd>
                            </div>
                            <div className="grid grid-cols-[58px_1fr] gap-2">
                              <dt className="text-[#727b8d]">{t('dsaSandboxPage.output')}</dt>
                              <dd className="break-all font-semibold text-[#0b6948]">{displayValue(example.output)}</dd>
                            </div>
                          </dl>
                          <p className="mt-3 border-t border-[#e1e7ef] pt-3 text-xs leading-5 text-[#586174]">
                            {example.explanation}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="grid gap-4 lg:grid-cols-2">
                    <div>
                      <h3 className="mb-2 font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-[#687084]">
                        {t('dsaSandboxPage.constraints')}
                      </h3>
                      <ul className="space-y-1.5 text-xs text-[#515b6d]">
                        {selected.constraints.map((constraint) => (
                          <li key={constraint} className="flex gap-2">
                            <span className="text-[#315a9e]">•</span>
                            <code>{constraint}</code>
                          </li>
                        ))}
                      </ul>
                    </div>
                    <details className="rounded-xl border border-[#dfe5ee] bg-[#fbfcfe] p-4">
                      <summary className="cursor-pointer font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-[#315a9e]">
                        {t('dsaSandboxPage.solutionOutline')}
                      </summary>
                      <p className="mt-3 text-xs leading-6 text-[#515b6d]">{selected.solution_outline}</p>
                    </details>
                  </div>
                </div>
              </section>

              <section className="overflow-hidden rounded-2xl border border-[#17233a] bg-[#0b1020] shadow-[0_18px_45px_rgba(11,16,32,0.2)]">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[#22304b] bg-[#111a2d] px-3 py-2.5 sm:px-4">
                  <div className="flex items-center gap-3">
                    <div className="flex gap-1.5" aria-hidden="true">
                      <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
                      <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
                      <span className="h-3 w-3 rounded-full bg-[#28c840]" />
                    </div>
                    <div className="flex items-center gap-2 border-l border-[#2b3952] pl-3 text-xs text-[#c3d1e7]">
                      <Code2 className="h-3.5 w-3.5 text-[#7dd3fc]" />
                      <span className="font-mono">solution.{FILE_EXTENSION[language] || 'txt'}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <select
                      aria-label={t('dsaSandboxPage.language')}
                      value={language}
                      onChange={(event) => handleLanguageChange(event.target.value)}
                      className="rounded-lg border border-[#33435f] bg-[#152038] px-2.5 py-1.5 font-mono text-[11px] text-[#d9e5f7] outline-none focus:border-[#60a5fa]"
                    >
                      {Object.entries(languages).map(([key, label]) => (
                        <option key={key} value={key}>{label}</option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={handleReset}
                      className="inline-flex items-center gap-1.5 rounded-lg border border-[#33435f] px-2.5 py-1.5 font-mono text-[10px] text-[#c5d2e6] transition hover:bg-[#1b2944]"
                    >
                      <RotateCcw className="h-3.5 w-3.5" /> {t('dsaSandboxPage.reset')}
                    </button>
                  </div>
                </div>

                <CodeEditor
                  key={`${selected.id}:${language}`}
                  language={language}
                  value={code}
                  onChange={handleCodeChange}
                  onRun={handleRun}
                />

                <div className="flex flex-wrap items-center justify-between gap-3 border-t border-[#22304b] bg-[#111a2d] px-3 py-3 sm:px-4">
                  <div className="flex items-center gap-2 font-mono text-[10px] text-[#8293ad]">
                    <ServerCog className="h-4 w-4" /> Judge0 · isolated execution
                    <span className="hidden sm:inline">· Ctrl/⌘ + Enter to run</span>
                  </div>
                  <button
                    type="button"
                    onClick={handleRun}
                    disabled={submitting || !code.trim()}
                    className="inline-flex min-w-32 items-center justify-center gap-2 rounded-lg bg-[#2f81f7] px-4 py-2 text-xs font-bold text-white transition hover:bg-[#1f6feb] disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {submitting ? (
                      <><Loader2 className="h-4 w-4 animate-spin" /> {t('dsaSandboxPage.running')}</>
                    ) : (
                      <><Play className="h-4 w-4 fill-current" /> {t('dsaSandboxPage.run')}</>
                    )}
                  </button>
                </div>
              </section>

              {(submitError || result) && (
                <section className="overflow-hidden rounded-2xl border border-[#d8deea] bg-white shadow-sm" aria-live="polite">
                  <div className="flex items-center gap-2 border-b border-[#e5e9f1] bg-[#f8fafc] px-4 py-3">
                    <TerminalSquare className="h-4 w-4 text-[#315a9e]" />
                    <h3 className="font-mono text-[10px] font-bold uppercase tracking-[0.14em] text-[#526078]">
                      {t('dsaSandboxPage.testResults')}
                    </h3>
                  </div>
                  <div className="p-4 sm:p-5">
                    {submitError && (
                      <div className="flex items-start gap-2 text-[#b3261e]" role="alert">
                        <XCircle className="mt-0.5 h-5 w-5 shrink-0" />
                        <p className="text-sm">{submitError}</p>
                      </div>
                    )}

                    {result?.status === 'accepted' && (
                      <div className="flex items-center gap-3 text-[#147a4b]">
                        <CheckCircle2 className="h-6 w-6 shrink-0" />
                        <div>
                          <div className="text-sm font-bold">{t('dsaSandboxPage.resultAccepted')}</div>
                          <div className="mt-1 flex items-center gap-2 font-mono text-[10px] text-[#586174]">
                            <Clock3 className="h-3.5 w-3.5" />
                            {result.passed_count}/{result.total_count} {t('dsaSandboxPage.passedCount')}
                          </div>
                        </div>
                      </div>
                    )}

                    {result && result.status !== 'accepted' && (
                      <div className="space-y-3">
                        <div className="flex items-center gap-2 text-[#b3261e]">
                          <XCircle className="h-5 w-5" />
                          <span className="text-sm font-semibold">
                            {t('dsaSandboxPage.resultFailedPrefix')} {(result.first_failure?.test_index ?? 0) + 1}{' '}
                            {t('dsaSandboxPage.of')} {result.total_count} — {result.status.replaceAll('_', ' ')}
                          </span>
                        </div>
                        {result.first_failure && (
                          <dl className="grid gap-2 rounded-xl bg-[#101827] p-4 font-mono text-xs text-[#dce7f7]">
                            <div><dt className="inline text-[#8092ad]">args: </dt><dd className="inline">{displayValue(result.first_failure.args)}</dd></div>
                            <div><dt className="inline text-[#8092ad]">{t('dsaSandboxPage.expected')}: </dt><dd className="inline text-[#7ee2ad]">{result.first_failure.expected_output}</dd></div>
                            {result.first_failure.actual_output != null && (
                              <div><dt className="inline text-[#8092ad]">{t('dsaSandboxPage.actual')}: </dt><dd className="inline text-[#ffb4a9]">{result.first_failure.actual_output}</dd></div>
                            )}
                            {(result.first_failure.stderr || result.first_failure.compile_output) && (
                              <div className="mt-1 whitespace-pre-wrap border-t border-[#2a3850] pt-3 text-[#ffb4a9]">
                                {result.first_failure.stderr || result.first_failure.compile_output}
                              </div>
                            )}
                          </dl>
                        )}
                      </div>
                    )}
                  </div>
                </section>
              )}
            </main>
          )}
        </div>
      )}
    </div>
  );
}
