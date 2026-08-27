'use client';

import Link from 'next/link';
import { useAuthStore } from '@/store/useAuthStore';
import PixelPanel from '@/components/ui/PixelPanel';
import PixelButton from '@/components/ui/PixelButton';
import PixelBadge from '@/components/ui/PixelBadge';

const PILLARS = [
  { tone: 'arcane', title: 'LLM monster engine', body: 'Every fight is a fresh, never-repeated question — generated live for the topic you walk into.' },
  { tone: 'gold', title: 'RL difficulty tuner', body: 'A bandit watches your accuracy and keeps you in the zone — challenged, never crushed.' },
  { tone: 'ember', title: 'NLP answer judge', body: 'Free-text answers, scored by meaning, not by matching exact keywords.' },
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
      <div className="w-full">
        <PixelBadge tone="arcane" className="mb-4">DATA STRUCTURES & ALGORITHMS</PixelBadge>
        {/* eslint-disable-next-line @next/next/no-img-element -- fixed local
            asset, not a candidate for next/image's remote optimization pipeline */}
        <img
          src="/sprites/bats/logo.png"
          alt="SkillQuest: The AI Dungeon"
          className="mx-auto"
          style={{ imageRendering: 'pixelated', maxWidth: '45%', height: 'auto' }}
        />
      </div>

      <p className="font-body text-xl text-parchment-dim max-w-xl">
        Your stats are a mirror of what you actually know. The dungeon routes its monsters
        straight at your weakest topics — so studying finally has a feedback loop.
      </p>

      <Link href={isAuthenticated ? '/dungeon' : '/login'}>
        <PixelButton variant="primary" className="text-sm">
          {isAuthenticated ? 'RETURN TO THE DUNGEON' : 'ENTER THE DUNGEON'}
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
