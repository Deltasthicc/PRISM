'use client';
import React from 'react';
import Link from 'next/link';
import { Gamepad2 } from 'lucide-react';
import { useAuthStore } from '@/store/useAuthStore';

// Shown in place of Quest-mode-only routes (dungeon, guild) when a learner
// navigates there directly without having opted in via the NavBar toggle.
// Quest mode is preserved as an explicit opt-in per the team's decision
// (SIH26101_MASTER_CHECKLIST.md) rather than the default experience -- this
// component is that boundary, not a redirect, so a learner always
// understands why they landed here and how to proceed either way.
export default function QuestModeGate() {
  const setPreferredMode = useAuthStore((s) => s.setPreferredMode);

  return (
    <div className="flex flex-col items-center justify-center gap-4 py-24 text-center">
      <div className="w-14 h-14 rounded-2xl bg-[#f2f3ff] text-[#00236f] flex items-center justify-center">
        <Gamepad2 size={26} strokeWidth={2} />
      </div>
      <div>
        <h2 className="text-base font-bold text-[#131b2e]">This is part of Quest Mode</h2>
        <p className="mt-1.5 max-w-md text-sm text-[#757682]">
          An optional gamified practice layer, off by default. Turn it on to continue, or head
          back to the professional workspace.
        </p>
      </div>
      <div className="flex items-center gap-3 mt-2">
        <button
          type="button"
          onClick={() => setPreferredMode('quest')}
          className="bg-[#00236f] hover:bg-[#1e3a8a] text-white px-4 py-2.5 rounded-lg text-sm font-semibold transition-colors"
        >
          Turn on Quest Mode
        </button>
        <Link
          href="/academy"
          className="border border-[#c5c5d3]/50 text-[#444651] hover:text-[#00236f] hover:border-[#00236f]/40 px-4 py-2.5 rounded-lg text-sm font-semibold transition-colors"
        >
          Back to Academy
        </Link>
      </div>
    </div>
  );
}
