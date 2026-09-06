'use client';

import React from 'react';
import { BadgeCheck } from 'lucide-react';
import { useLanguage } from '@/lib/i18n/LanguageContext';

export default function Footer() {
  const { t } = useLanguage();
  return (
    <footer className="w-full bg-[#f2f3ff] py-4 px-4 sm:px-8 text-[#444651] text-xs border-t border-[#c5c5d3]/30 mt-auto">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3 text-center md:text-left">
        <div className="flex items-center gap-2 justify-center md:justify-start">
          <BadgeCheck size={30} />
          <p className="text-xs">{t('footer.copyright')}</p>
        </div>
        <div className="flex items-center gap-3 font-mono text-[11px] text-[#757682] flex-wrap justify-center">
          <span className="flex items-center gap-1">
            <span className="material-symbols-outlined text-[14px]">history</span>{t('footer.auditBadge')}
          </span>
          <span>•</span>
          <span className="flex items-center gap-1">
            <span className="material-symbols-outlined text-[14px]">policy</span>{t('footer.ndsapBadge')}
          </span>
          <span>•</span>
          <span>{t('footer.syncBadge')}</span>
        </div>
      </div>
    </footer>
  );
}
