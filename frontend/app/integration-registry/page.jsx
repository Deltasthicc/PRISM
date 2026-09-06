'use client';

import { useQuery } from '@tanstack/react-query';
import { ShieldCheck, ExternalLink } from 'lucide-react';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import { learning } from '@/lib/api/client';

export default function IntegrationRegistryPage() {
  const { ready } = useRequireAuth();
  const { t, language } = useLanguage();
  const PROVIDER_LABEL = { igot: t('integrationRegistry.providerIgot'), nssta: t('integrationRegistry.providerNssta') };

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['integration-status', language],
    queryFn: () => learning.getIntegrationStatus(language),
    enabled: ready,
  });

  if (!ready || isLoading) {
    return <p className="font-sans text-sm text-[#757682] text-center mt-10">{t('integrationRegistry.loading')}</p>;
  }
  if (isError || !data) {
    return (
      <div className="flex flex-col items-center gap-3 mt-10" role="alert">
        <p className="font-sans text-sm text-[#b3261e]">{t('integrationRegistry.loadFailed')}</p>
        <button
          onClick={() => refetch()}
          className="font-sans text-sm font-semibold px-4 py-2 rounded-lg border border-[#c5c5d3]/60 text-[#00236f] hover:bg-[#f2f3ff]"
        >
          {t('integrationRegistry.retry')}
        </button>
      </div>
    );
  }

  const providers = Object.entries(data).filter(([, status]) => status && typeof status === 'object');

  return (
    <div className="flex flex-col gap-6 max-w-3xl">
      <header>
        <h1 className="font-sans text-xl font-bold text-[#00236f]">{t('integrationRegistry.heading')}</h1>
        <p className="font-sans text-sm text-[#757682] mt-2">{t('integrationRegistry.subtitle')}</p>
      </header>

      <div className="flex flex-col gap-3">
        {providers.map(([key, status]) => (
          <div key={key} className="bg-white border border-[#c5c5d3]/40 rounded-xl p-4 shadow-sm">
            <div className="flex items-center gap-2">
              <ShieldCheck size={16} className={status.mode === 'configured' ? 'text-[#1a7f4b]' : 'text-[#757682]'} aria-hidden="true" />
              <span className="font-sans text-sm font-semibold text-[#131b2e]">
                {PROVIDER_LABEL[key] || key}
              </span>
              <span
                className={`ml-auto font-mono text-[10px] uppercase tracking-wide px-2 py-0.5 rounded border ${
                  status.mode === 'configured'
                    ? 'bg-[#e6f4ea] text-[#1a7f4b] border-[#b7e1c4]'
                    : 'bg-[#f2f3ff] text-[#444651] border-[#c5c5d3]/60'
                }`}
              >
                {status.mode}
              </span>
            </div>
            <p className="font-sans text-sm text-[#444651] mt-2">{status.detail}</p>
          </div>
        ))}
        {providers.length === 0 && (
          <p className="font-sans text-sm text-[#757682]">{t('integrationRegistry.noIntegrations')}</p>
        )}
      </div>

      <a
        href="https://igotkarmayogi.gov.in/"
        target="_blank"
        rel="noreferrer"
        className="inline-flex items-center gap-1.5 font-sans text-sm text-[#00236f] hover:underline w-fit"
      >
        {t('integrationRegistry.openIgotCatalog')} <ExternalLink size={14} aria-hidden="true" />
      </a>
    </div>
  );
}
