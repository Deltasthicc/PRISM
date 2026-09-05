'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { User, LogOut } from 'lucide-react';
import { useAuthStore } from '@/store/useAuthStore';

export default function NavBar() {
  const pathname = usePathname();
  const player = useAuthStore((s) => s.player);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const logout = useAuthStore((s) => s.logout);

  if (!isAuthenticated) return null;
  const navTabs = [
    {
      href: '/competency-and-gap-analysis',
      label: 'Competency & Gap Analysis',
      hasDot: true,
    },
    {
      href: '/dungeon',
      label: 'Prerequisite Pathways',
      hasDot: false,
    },
    {
      href: '/quiz',
      label: 'Source Quiz Generator',
      hasDot: false,
    },
    {
      href: '/guild',
      label: 'Adaptive Practice (DSA Quest)',
      hasDot: false,
    },
    {
      href: '/integration-registry',
      label: 'Integration Registry',
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
              PRISM
            </span>

            <span className="font-mono text-[9px] sm:text-[10px] text-[#757682] uppercase tracking-wider">
              Personalized Readiness Intelligence &amp; Skill Mapping
            </span>
          </div>
        </Link>

        {/* ================= USER ================= */}
        <div className="flex items-center gap-3">
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
            title="Sign out"
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
