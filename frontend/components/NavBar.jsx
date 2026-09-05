'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { Search, User } from 'lucide-react';

export default function NavBar({ searchQuery, setSearchQuery }) {
  const pathname = usePathname();

  const navTabs = [
    {
      href: '/competency-and-gap-analysis',
      label: 'Competency & Gap Analysis',
      hasDot: true,
    },
    {
      href: '/prerequisite-pathways',
      label: 'Prerequisite Pathways',
      hasDot: false,
    },
    {
      href: '/source-quiz-generator',
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
          PRIMARY BRAND / SEARCH / USER BAR
          ========================================= */}
      <div className="h-16 sm:h-20 px-4 sm:px-8 flex items-center justify-between gap-4 border-b border-[#c5c5d3]/40">

        {/* ================= BRAND ================= */}
        <Link
          href="/competency-and-gap-analysis"
          className="flex items-center gap-3 shrink-0"
        >
          <img
            alt="MoSPI Skill Intelligence Logo"
            className="h-8 sm:h-9 w-auto object-contain cursor-pointer"
            src="https://lh3.googleusercontent.com/aida/AEtjO1X2HmAWuTERiKBpSMjZTAJb93ncwDjSPHeHfuYT3E7GYJ7g4rwxI9weXopyodSrfcDM7-axk3a2BgAqFL6ddQObM93edN1b_Yb5KEfuY9YbqGIbJTqrguqs-pwBVV-e2W7_i_NEDbwdLxgwZkKb7MU7zaCvRS5OnpN0HW20u_dVUer0qf1eZLIOQD_rNcqbElu7ZK0mziERc6UkN8TSHLKYPahPkm4timPyoe-M3ZqnBP3A98grXD8z5l61"
          />

          <div className="flex flex-col">
            <span className="text-base sm:text-lg font-bold text-[#00236f] leading-tight tracking-tight">
              MoSPI Skill-Intelligence
            </span>

            <span className="font-mono text-[9px] sm:text-[10px] text-[#757682] uppercase tracking-wider">
              MINISTRY OF STATISTICS &amp; PROGRAMME IMPLEMENTATION
            </span>
          </div>
        </Link>

        {/* ================= SEARCH + USER ================= */}
        <div className="flex items-center gap-4">

          {/* Search */}
          <div className="hidden md:flex items-center bg-[#f2f3ff] px-3.5 py-1.5 rounded-lg w-64 lg:w-80 border border-[#c5c5d3]/40">

            <Search
              size={18}
              className="text-[#757682] mr-2 shrink-0"
            />

            <input
              className="w-full bg-transparent border-none outline-none text-xs text-[#131b2e] placeholder:text-[#757682]"
              placeholder="Search competencies, iGOT..."
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />

          </div>

          {/* ================= USER PROFILE ================= */}
          <Link
            href="/stats"
            className="flex items-center gap-2.5 bg-[#f2f3ff]/80 px-3 py-1.5 rounded-lg border border-[#c5c5d3]/30 hover:bg-[#e2e7ff] hover:border-[#00236f]/30 transition-all cursor-pointer"
          >

            <div className="flex flex-col text-right hidden sm:block">
              <span className="font-mono text-xs font-semibold text-[#131b2e] leading-tight">
                rajesh.sharma
              </span>
            </div>

            <div className="w-8 h-8 rounded-full bg-[#00236f] flex items-center justify-center text-white shadow-sm">
              <User
                size={18}
                className="text-white"
              />
            </div>

          </Link>
        </div>
      </div>

      {/* =========================================
          NAVIGATION SUB-BAR
          ========================================= */}
      <nav className="h-11 px-4 sm:px-8 bg-white border-b border-[#c5c5d3]/20 flex items-center gap-6 sm:gap-8 overflow-x-auto no-scrollbar">

        {navTabs.map((tab) => {
          const isActive = pathname.startsWith(tab.href);

          return (
            <Link
              key={tab.href}
              href={tab.href}
              className={`
                h-full
                flex
                items-center
                gap-1.5
                text-xs
                sm:text-sm
                whitespace-nowrap
                transition-colors
                border-b-2
                font-medium
                ${
                  isActive
                    ? 'border-[#00236f] text-[#00236f] font-semibold'
                    : 'border-transparent text-[#444651] hover:text-[#00236f]'
                }
              `}
            >
              <span>{tab.label}</span>

              {tab.hasDot && (
                <span className="w-1.5 h-1.5 rounded-full bg-[#fe932c] inline-block" />
              )}
            </Link>
          );
        })}

      </nav>
    </header>
  );
}