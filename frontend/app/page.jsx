'use client';

import Link from 'next/link';
import { BarChart3, FileCheck2, ListChecks } from 'lucide-react';
import { useAuthStore } from '@/store/useAuthStore';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Panel from '@/components/ui/Panel';

export default function LandingPage() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const { t } = useLanguage();

  const pillars = [
    { icon: BarChart3, title: t('landing.pillarGapTitle'), body: t('landing.pillarGapBody') },
    { icon: ListChecks, title: t('landing.pillarQuizTitle'), body: t('landing.pillarQuizBody') },
    { icon: FileCheck2, title: t('landing.pillarGroundedTitle'), body: t('landing.pillarGroundedBody') },
  ];

  return (
    <div className="min-h-[80vh] flex flex-col items-center justify-center text-center gap-8 py-10 px-4">
      <div className="w-full flex flex-col items-center gap-3">
        <Badge tone="accent">{t('landing.badge')}</Badge>
        <h1 className="font-sans text-4xl md:text-5xl font-bold text-[#00236f] tracking-tight">
          {t('brand.name')}
        </h1>
        <p className="font-sans text-sm text-[#757682] tracking-wide">{t('brand.tagline')}</p>
      </div>

      <p className="font-sans text-lg text-[#444651] max-w-xl">{t('landing.description')}</p>

      <Link href={isAuthenticated ? '/academy' : '/login'}>
        <Button variant="primary" className="text-sm px-6 py-3">
          {isAuthenticated ? t('landing.ctaAuthenticated') : t('landing.ctaGuest')}
        </Button>
      </Link>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6 w-full max-w-4xl">
        {pillars.map(({ icon: Icon, title, body }) => (
          <Panel key={title} variant="accent" className="text-left">
            <Icon className="w-5 h-5 text-[#00236f] mb-3" strokeWidth={2} />
            <h3 className="font-sans text-sm font-bold text-[#131b2e] mb-2">{title}</h3>
            <p className="font-sans text-sm text-[#757682]">{body}</p>
          </Panel>
        ))}
      </div>
    </div>
  );
}
