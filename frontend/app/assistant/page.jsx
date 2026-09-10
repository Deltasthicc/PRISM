'use client';

import { useState } from 'react';
import { Search, BookOpen, ShieldAlert, CheckCircle2 } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import { ai } from '@/lib/api/client';
import Panel from '@/components/ui/Panel';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';

// A real Retrieval-Augmented Generation assistant (backend/ai/retrieval.py +
// ai/assistant.py, exposed at POST /ai/assistant/query) -- access-filtered
// BM25 retrieval over a real, source-cited corpus (the same excerpts
// data/hand_authored_questions.json quotes for the competency quiz), with
// honest abstention when evidence is too weak rather than an invented
// answer. Deliberately framed as "grounded evidence with citations," not a
// general chatbot -- that is what this engine actually does.
const EXAMPLE_QUESTIONS_KEYS = ['example1', 'example2', 'example3'];

const STATUS_TONE = {
  supported: 'success',
  insufficient_evidence: 'warning',
  prompt_injection_detected: 'danger',
  out_of_scope: 'default',
  retrieval_failure: 'danger',
  system_failure: 'danger',
};

export default function AssistantPage() {
  const { ready } = useRequireAuth();
  const { t } = useLanguage();
  const [query, setQuery] = useState('');
  const [asking, setAsking] = useState(false);
  const [error, setError] = useState('');
  const [response, setResponse] = useState(null);

  async function ask(q) {
    const text = (q ?? query).trim();
    if (!text) return;
    setAsking(true);
    setError('');
    try {
      const result = await ai.assistantQuery(text);
      setResponse(result);
      setQuery(text);
    } catch (cause) {
      setError(cause.message || t('assistantPage.genericError'));
    } finally {
      setAsking(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    ask();
  }

  if (!ready) {
    return <p className="font-sans text-sm text-[#757682] text-center mt-10">{t('assistantPage.loadingShell')}</p>;
  }

  return (
    <div className="max-w-3xl mx-auto flex flex-col gap-4">
      <div>
        <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#757682] mb-1">
          {t('assistantPage.eyebrow')}
        </p>
        <h1 className="font-sans text-lg font-bold text-[#00236f]">{t('assistantPage.title')}</h1>
        <p className="font-sans text-sm text-[#757682] mt-1 max-w-xl">{t('assistantPage.subtitle')}</p>
      </div>

      <Panel>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="flex gap-2">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={t('assistantPage.placeholder')}
              className="flex-1 px-3.5 py-2.5 rounded-lg border border-[#c5c5d3]/60 font-sans text-sm outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]"
            />
            <Button type="submit" disabled={asking || !query.trim()}>
              <Search size={15} className="inline mr-1.5 -mt-0.5" />
              {asking ? t('assistantPage.asking') : t('assistantPage.askButton')}
            </Button>
          </div>
          {!response && !asking && (
            <div className="flex flex-wrap gap-2">
              {EXAMPLE_QUESTIONS_KEYS.map((key) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => ask(t(`assistantPage.${key}`))}
                  className="font-sans text-xs px-3 py-1.5 rounded-full border border-[#c5c5d3]/50 text-[#00236f] hover:bg-[#f2f3ff]"
                >
                  {t(`assistantPage.${key}`)}
                </button>
              ))}
            </div>
          )}
        </form>
        {error && <p className="mt-3 font-sans text-xs text-[#b3261e]">{error}</p>}
      </Panel>

      {response && (
        <Panel>
          <div className="flex items-center justify-between gap-3 flex-wrap mb-3">
            <span className="font-sans text-xs font-semibold text-[#757682]">
              {t('assistantPage.answerHeading')}
            </span>
            <Badge tone={STATUS_TONE[response.status] || 'default'}>
              {response.status === 'supported'
                ? t('assistantPage.statusSupported')
                : response.status === 'insufficient_evidence'
                  ? t('assistantPage.statusInsufficientEvidence')
                  : response.status}
            </Badge>
          </div>

          <p className="font-sans text-sm text-[#131b2e] leading-6">{response.answer}</p>

          {response.status === 'insufficient_evidence' && (
            <p className="mt-2 flex items-center gap-1.5 font-mono text-[10px] text-[#904d00]">
              <ShieldAlert size={12} />
              {t('assistantPage.abstentionNote')}
            </p>
          )}

          {response.citations?.length > 0 && (
            <div className="mt-4 pt-3 border-t border-[#c5c5d3]/30">
              <p className="font-mono text-[10px] font-bold uppercase text-[#757682] mb-2 flex items-center gap-1.5">
                <BookOpen size={12} />
                {t('assistantPage.citationsHeading')}
              </p>
              <div className="flex flex-col gap-2">
                {response.citations.map((c) => (
                  <div key={c.citation_id} className="p-3 rounded-lg bg-[#f7f7fb] border border-[#c5c5d3]/40">
                    <p className="font-mono text-[10px] text-[#8a8f9d] mb-1">
                      {c.filename} — {c.locator_label}
                    </p>
                    <p className="font-sans text-xs text-[#333a49] italic">&ldquo;{c.quote}&rdquo;</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="mt-3 pt-3 border-t border-[#c5c5d3]/30 flex items-center gap-1.5">
            <CheckCircle2 size={12} className="text-[#757682]" />
            <p className="font-mono text-[10px] text-[#8a8f9d]">{t('assistantPage.provenanceNote')}</p>
          </div>
        </Panel>
      )}
    </div>
  );
}
