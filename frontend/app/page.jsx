'use client';

import Link from 'next/link';
import { useAuthStore } from '@/store/useAuthStore';
import PixelPanel from '@/components/ui/PixelPanel';
import PixelButton from '@/components/ui/PixelButton';
import PixelBadge from '@/components/ui/PixelBadge';

const PILLARS = [
  { tone: 'arcane', title: 'Explainable gap analysis', body: 'Demonstrated practice evidence blended with self-assessment — every score shows exactly where it came from.' },
  { tone: 'gold', title: 'Adaptive practice engine', body: 'Fresh, never-repeated questions generated live, at a difficulty tuned to your recent accuracy.' },
  { tone: 'ember', title: 'Grounded quiz generation', body: 'Upload your own material and get back questions with an exact source citation for every answer.' },
];

export default function LandingPage() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  return (
    <div
      className="min-h-[80vh] flex flex-col items-center justify-center text-center gap-8 py-10"
      style={{
        backgroundImage:
          'repeating-linear-gradient(0deg, #15101f 0 2px, transparent 2px 32px), repeating-linear-gradient(90deg, #15101f 0 2px, transparent 2px 32px)',
      }}
    >
      <div className="w-full flex flex-col items-center">
        {/* items-center (not inline-block + mx-auto, which only reliably
            centers a block-level box, not this span-based badge) keeps the
            badge and the wordmark on the same centerline instead of the
            badge drifting to the left edge of the full-width wrapper. */}
        <PixelBadge tone="arcane" className="mb-4">SKILL-INTELLIGENCE PLATFORM</PixelBadge>
        {/* Text wordmark, not the old logo.png sprite -- that asset's pixels
            spell out the inherited "SkillQuest: The AI Dungeon" branding, and
            an alt-text change alone doesn't fix what's actually rendered. */}
        <PixelPanel as="div" className="px-8 py-5 text-center">
          <p className="font-display text-3xl md:text-4xl text-arcane leading-tight">PRISM</p>
          <p className="font-display text-[9px] md:text-[11px] text-gold mt-2 tracking-wide leading-relaxed">
            Personalized Readiness Intelligence
            <br />
            &amp; Skill Mapping
          </p>
        </PixelPanel>
      </div>

      <p className="font-body text-xl text-parchment-dim max-w-xl">
        Your stats are a mirror of what you actually know. Across Official Statistics, Public
        Policy, Digital Literacy, and DSA, practice routes straight at your weakest competencies —
        so studying finally has a feedback loop.
      </p>

      <Link href={isAuthenticated ? '/academy' : '/login'}>
        <PixelButton variant="primary" className="text-sm">
          {isAuthenticated ? 'RETURN TO THE ACADEMY' : 'ENTER THE ACADEMY'}
        </PixelButton>
      </Link>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6 w-full max-w-4xl">
        {PILLARS.map((p) => (
          <PixelPanel key={p.title} variant={p.tone === 'arcane' ? 'arcane' : 'default'}>
            <h3 className="font-display text-[10px] text-parchment mb-2">{p.title.toUpperCase()}</h3>
            <p className="font-body text-base text-parchment-dim">{p.body}</p>
          </PixelPanel>
        ))}
      </div>
    </div>
  );
}
