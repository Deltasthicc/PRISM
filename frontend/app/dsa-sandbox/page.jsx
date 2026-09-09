'use client';

import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import Link from 'next/link';
import clsx from 'clsx';
import { CheckCircle2, XCircle, Loader2 } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import { learning } from '@/lib/api/client';
import Panel from '@/components/ui/Panel';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';

const DIFFICULTY_TONE = { easy: 'success', medium: 'warning', hard: 'danger' };

export default function DsaSandboxPage() {
  const { ready } = useRequireAuth();
  const player = useAuthStore((s) => s.player);
  const { t } = useLanguage();

  const [selectedProblemId, setSelectedProblemId] = useState(null);
  const [codeByProblem, setCodeByProblem] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);
  const [submitError, setSubmitError] = useState('');

  const { data: profileData } = useQuery({
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

  useEffect(() => {
    if (!selectedProblemId && problems.length) setSelectedProblemId(problems[0].id);
  }, [problems, selectedProblemId]);

  const selected = problems.find((p) => p.id === selectedProblemId) || null;
  const code = selected ? codeByProblem[selected.id] ?? selected.starter_code : '';

  function handleSelectProblem(problem) {
    setSelectedProblemId(problem.id);
    setResult(null);
    setSubmitError('');
  }

  function handleCodeChange(value) {
    if (!selected) return;
    setCodeByProblem((prev) => ({ ...prev, [selected.id]: value }));
  }

  async function handleRun() {
    if (!selected || submitting) return;
    setSubmitting(true);
    setSubmitError('');
    setResult(null);
    try {
      const response = await learning.submitDsaSandbox(player.player_id, selected.id, code);
      setResult(response);
    } catch (cause) {
      setSubmitError(cause.message || t('dsaSandboxPage.judgeUnavailable'));
    } finally {
      setSubmitting(false);
    }
  }

  if (!ready) return null;

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
    <div className="max-w-6xl mx-auto flex flex-col gap-5">
      <div>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">{t('dsaSandboxPage.heading')}</h1>
        <p className="font-sans text-sm text-[#757682] mt-1 max-w-2xl">{t('dsaSandboxPage.subtitle')}</p>
      </div>

      {problemsLoading ? (
        <Panel>
          <p className="font-sans text-sm text-[#757682]">{t('dsaSandboxPage.loading')}</p>
        </Panel>
      ) : problemsErrored ? (
        <Panel className="text-center">
          <p className="font-sans text-sm text-[#b3261e] mb-3">{t('dsaSandboxPage.loadFailed')}</p>
          <Button variant="ghost" onClick={() => refetchProblems()}>
            {t('dsaSandboxPage.retry')}
          </Button>
        </Panel>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
          <div className="lg:col-span-4 flex flex-col gap-2">
            <h2 className="font-mono text-[10px] uppercase tracking-wider text-[#757682] px-1">
              {t('dsaSandboxPage.problemsHeading')}
            </h2>
            {problems.map((problem) => (
              <button
                key={problem.id}
                onClick={() => handleSelectProblem(problem)}
                className={clsx(
                  'text-left rounded-xl p-3 border transition-colors',
                  selected?.id === problem.id
                    ? 'bg-[#f2f3ff] border-[#00236f]/40'
                    : 'bg-white border-[#c5c5d3]/30 hover:border-[#00236f]/30'
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-sans text-sm font-semibold text-[#131b2e]">{problem.title}</span>
                  <Badge tone={DIFFICULTY_TONE[problem.difficulty] || 'default'}>{problem.difficulty}</Badge>
                </div>
                <span className="font-mono text-[10px] text-[#757682]">{problem.topic_label}</span>
              </button>
            ))}
          </div>

          <div className="lg:col-span-8 flex flex-col gap-4">
            {selected && (
              <>
                <Panel>
                  <div className="flex items-center justify-between gap-2 mb-2">
                    <h2 className="font-sans text-base font-bold text-[#131b2e]">{selected.title}</h2>
                    <Badge tone="accent">{selected.topic_label}</Badge>
                  </div>
                  <p className="font-sans text-sm text-[#444651] leading-relaxed whitespace-pre-line">
                    {selected.prompt}
                  </p>
                  <p className="font-mono text-[11px] text-[#757682] mt-3">
                    {t('dsaSandboxPage.sampleInput')}: {JSON.stringify(selected.sample_input)}
                  </p>
                </Panel>

                <Panel>
                  <label className="font-mono text-[10px] uppercase tracking-wider text-[#757682]">
                    {t('dsaSandboxPage.yourSolution')}
                  </label>
                  <textarea
                    value={code}
                    onChange={(e) => handleCodeChange(e.target.value)}
                    rows={14}
                    spellCheck={false}
                    className="mt-2 w-full font-mono text-sm bg-[#0d1117] text-[#e6edf3] rounded-lg p-4 outline-none border border-[#c5c5d3]/30 focus:border-[#00236f]/50"
                  />
                  <Button className="mt-3" onClick={handleRun} disabled={submitting}>
                    {submitting ? (
                      <span className="flex items-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin" /> {t('dsaSandboxPage.running')}
                      </span>
                    ) : (
                      t('dsaSandboxPage.run')
                    )}
                  </Button>
                </Panel>

                {submitError && (
                  <Panel className="border-[#f5c6c2] bg-[#fce8e6]">
                    <p className="font-sans text-sm text-[#b3261e]">{submitError}</p>
                  </Panel>
                )}

                {result && (
                  <Panel className={result.status === 'accepted' ? 'border-[#b7e1c4]' : 'border-[#f5c6c2]'}>
                    {result.status === 'accepted' ? (
                      <div className="flex items-center gap-2 text-[#1a7f4b]">
                        <CheckCircle2 className="w-5 h-5" />
                        <span className="font-sans text-sm font-semibold">
                          {t('dsaSandboxPage.resultAccepted')} ({result.passed_count}/{result.total_count}{' '}
                          {t('dsaSandboxPage.passedCount')})
                        </span>
                      </div>
                    ) : (
                      <div className="flex flex-col gap-2">
                        <div className="flex items-center gap-2 text-[#b3261e]">
                          <XCircle className="w-5 h-5" />
                          <span className="font-sans text-sm font-semibold">
                            {t('dsaSandboxPage.resultFailedPrefix')} {(result.first_failure?.test_index ?? 0) + 1}{' '}
                            {t('dsaSandboxPage.of')} {result.total_count} — {result.status.replace(/_/g, ' ')}
                          </span>
                        </div>
                        {result.first_failure && (
                          <div className="font-mono text-xs text-[#444651] flex flex-col gap-1 bg-[#f7f7fb] rounded-lg p-3">
                            <span>args: {JSON.stringify(result.first_failure.args)}</span>
                            <span>
                              {t('dsaSandboxPage.expected')}: {result.first_failure.expected_output}
                            </span>
                            {result.first_failure.actual_output != null && (
                              <span>
                                {t('dsaSandboxPage.actual')}: {result.first_failure.actual_output}
                              </span>
                            )}
                            {(result.first_failure.stderr || result.first_failure.compile_output) && (
                              <span className="text-[#b3261e] whitespace-pre-wrap">
                                {t('dsaSandboxPage.stderr')}:{' '}
                                {result.first_failure.stderr || result.first_failure.compile_output}
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    )}
                  </Panel>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
