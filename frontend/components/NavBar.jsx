'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { User, LogOut, Gamepad2 } from 'lucide-react';
import { useAuthStore } from '@/store/useAuthStore';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import { learning } from '@/lib/api/client';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import AccessibilityMenu from '@/components/AccessibilityMenu';

export default function NavBar() {
  const pathname = usePathname();
  const player = useAuthStore((s) => s.player);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const logout = useAuthStore((s) => s.logout);
  const setPreferredMode = useAuthStore((s) => s.setPreferredMode);
  const { t } = useLanguage();

  // Only fetched to decide whether the DSA Sandbox tab shows at all -- per
  // the "not all users will have DSA" requirement, a learner who hasn't
  // picked dsa-fundamentals in their profile shouldn't see an entry point
  // for it. Cheap: this profile fetch shares its cache (same queryKey) with
  // every other page that already calls learning.getProfile.
  const { data: profileData } = useQuery({
    queryKey: ['learning-profile', player?.player_id],
    queryFn: () => learning.getProfile(player.player_id),
    enabled: isAuthenticated && !!player,
  });
  const hasDsaFundamentals = Boolean(
    profileData?.profile?.target_domains?.includes('dsa-fundamentals')
  );
  const hasOfficialStatistics = Boolean(
    profileData?.profile?.target_domains?.includes('official-statistics')
  );
  const hasPublicPolicy = Boolean(
    profileData?.profile?.target_domains?.includes('public-policy')
  );

  if (!isAuthenticated) return null;

  // Quest mode (character/boss fights/leaderboard) is an explicit opt-in,
  // off by default (models/enums.py's LearningMode, player.preferred_mode).
  // Prerequisite Pathways and the DSA Sandbox are NOT part of that gate --
  // the toggle is a placeholder for now and doesn't change their
  // availability; both nav tabs always show (DSA Sandbox is instead gated
  // on the learner having picked dsa-fundamentals, above).
  const questModeOn = player?.preferred_mode === 'quest';
  const navTabs = [
    { href: '/stats', label: t('nav.competencyGapAnalysis'), hasDot: false },
    { href: '/dungeon', label: t('nav.prerequisitePathways'), hasDot: false },
    {
      href: '/quiz',
      label: t('nav.sourceQuizGenerator'),
      hasDot: false,
    },
    ...(hasDsaFundamentals
      ? [{ href: '/dsa-sandbox', label: t('nav.dsaSandbox'), hasDot: false }]
      : []),
    // Not yet run through the i18n pipeline (see the page's own header
    // comment) -- a plain English label rather than a fake/missing t() key.
    ...(hasOfficialStatistics
      ? [{ href: '/sampling-lab', label: 'Sampling Lab', hasDot: false }]
      : []),
    // Same convention: gated behind the learner having picked public-policy
    // as a target domain, and not yet run through the i18n pipeline (see
    // app/scenarios/page.jsx's own header comment).
    ...(hasPublicPolicy
      ? [{ href: '/scenarios', label: 'Judgment Simulations', hasDot: false }]
      : []),
    { href: '/assistant', label: t('nav.assistant'), hasDot: false },
    { href: '/voice', label: t('nav.voiceAssistant'), hasDot: false },
    {
      href: '/integration-registry',
      label: t('nav.integrationRegistry'),
      hasDot: false,
    },
  ];

  return (
    <header className="fixed top-0 left-0 right-0 z-50 flex flex-col bg-white shadow-[0_2px_12px_rgba(0,0,0,0.04)]">
      {/* =========================================
          PRIMARY BRAND / USER BAR
          ========================================= */}
      <div className="h-16 sm:h-20 px-4 sm:px-8 flex items-center justify-between gap-4 border-b border-[#c5c5d3]/40">
        {/* ================= BRAND ================= */}
        <Link href="/academy" className="flex items-center gap-3 shrink-0">
          <div className="h-9 w-9 rounded-lg bg-[#00236f] text-white flex items-center justify-center font-bold text-sm shrink-0">
            P
          </div>

          <div className="flex flex-col">
            <span className="text-base sm:text-lg font-bold text-[#00236f] leading-tight tracking-tight">
              {t('brand.name')}
            </span>

            <span className="font-mono text-[9px] sm:text-[10px] text-[#757682] uppercase tracking-wider">
              {t('brand.tagline')}
            </span>
          </div>
        </Link>

        {/* ================= USER ================= */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => setPreferredMode(questModeOn ? 'professional' : 'quest')}
            title={t('nav.questModeToggleTitle')}
            aria-pressed={questModeOn}
            className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
              questModeOn
                ? 'bg-[#eef1ff] border-[#00236f]/30 text-[#00236f]'
                : 'border-[#c5c5d3]/40 text-[#757682] hover:text-[#00236f] hover:border-[#00236f]/30'
            }`}
          >
            <Gamepad2 size={14} />
            {questModeOn ? t('nav.questModeOn') : t('nav.questModeOff')}
          </button>
          <LanguageSwitcher />
          <AccessibilityMenu />
          <Link
            href="/stats"
            className="flex items-center gap-2.5 bg-[#f2f3ff]/80 px-3 py-1.5 rounded-lg border border-[#c5c5d3]/30 hover:bg-[#e2e7ff] hover:border-[#00236f]/30 transition-all"
          >
            <div className="flex flex-col text-right hidden sm:block">
              <span className="font-mono text-xs font-semibold text-[#131b2e] leading-tight">
                {player?.username}
              </span>
            </div>

            <div className="w-8 h-8 rounded-full bg-[#00236f] flex items-center justify-center text-white shadow-sm">
              <User size={18} className="text-white" />
            </div>
          </Link>

          <button
            type="button"
            onClick={() => logout()}
            title={t('nav.signOut')}
            className="p-2 rounded-lg border border-[#c5c5d3]/40 text-[#757682] hover:text-[#00236f] hover:border-[#00236f]/30 transition-colors"
          >
            <LogOut size={16} />
          </button>
        </div>
      </div>

      {/* =========================================
          NAVIGATION SUB-BAR
          ========================================= */}
      <nav className="h-11 px-4 sm:px-8 bg-white border-b border-[#c5c5d3]/20 flex items-center gap-6 sm:gap-8 overflow-x-auto no-scrollbar">
        {navTabs.map((tab, index) => {
          // Three tabs currently share the /academy destination (it's one
          // continuous flow, not three separate pages yet -- see AcademyHub)
          // -- only the first one lights up as "active" so all three don't
          // simultaneously highlight.
          const isFirstWithThisHref = navTabs.findIndex((t) => t.href === tab.href) === index;
          const isActive = isFirstWithThisHref && pathname.startsWith(tab.href);

          return (
            <Link
              key={tab.label}
              href={tab.href}
              className={`h-full flex items-center gap-1.5 text-xs sm:text-sm whitespace-nowrap transition-colors border-b-2 font-medium ${
                isActive
                  ? 'border-[#00236f] text-[#00236f] font-semibold'
                  : 'border-transparent text-[#444651] hover:text-[#00236f]'
              }`}
            >
              <span>{tab.label}</span>
            </Link>
          );
        })}
      </nav>
    </header>
  );
}
