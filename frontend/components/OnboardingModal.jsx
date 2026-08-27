'use client';

import { useEffect, useState } from 'react';
import { useAuthStore } from '@/store/useAuthStore';
import { useOnboardingStore } from '@/store/useOnboardingStore';
import PixelPanel from './ui/PixelPanel';
import PixelButton from './ui/PixelButton';

const SLIDES = [
  {
    title: 'WELCOME TO THE DUNGEON',
    body: "SkillQuest turns learning Data Structures & Algorithms into a dungeon crawl. Your real knowledge is your character sheet — the dungeon routes its monsters straight at whatever topic you're weakest in.",
  },
  {
    title: 'ONE VILLAIN PER TOPIC',
    body: "Each room on the map (Arrays, Trees, Graphs...) is guarded by a single fixed villain. Every question you answer chips away at that same villain's health — it does not reset between questions. Enough correct answers and the villain falls, unlocking rooms deeper in the dungeon.",
  },
  {
    title: 'ANSWER IN YOUR OWN WORDS',
    body: 'Combat is free-text. An AI judge scores your answer by meaning, not exact wording. CORRECT lands a heavy blow and full XP, PARTIAL lands a lighter hit, INCORRECT misses entirely.',
  },
  {
    title: 'HINTS & STREAKS',
    body: 'Stuck? Spend a hint token to reveal a nudge toward the answer. Tokens are limited but replenish as your daily streak grows, so playing consistently pays off.',
  },
  {
    title: "YOUR HERO'S POWER",
    body: 'Your chosen hero carries one unique power, usable up to 3 times per hour — anything from a devastating instant strike to a free hint, a full heal, or doubled XP. Save it for a fight that needs it.',
  },
  {
    title: 'THE BOSS',
    body: 'Clear every topic in the dungeon and the door to The Big-O Devourer opens: a final fight that pulls questions from everything you have learned.',
  },
];

export default function OnboardingModal() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const open = useOnboardingStore((s) => s.open);
  const closeModal = useOnboardingStore((s) => s.closeModal);
  const openIfUnseen = useOnboardingStore((s) => s.openIfUnseen);
  const [slide, setSlide] = useState(0);

  useEffect(() => {
    if (isAuthenticated) openIfUnseen();
  }, [isAuthenticated, openIfUnseen]);

  function handleClose() {
    closeModal();
    setSlide(0);
  }

  if (!open) return null;

  const current = SLIDES[slide];
  const isLast = slide === SLIDES.length - 1;

  return (
    <div className="fixed inset-0 z-[9997] flex items-center justify-center bg-black/70 px-4">
      <PixelPanel variant="arcane" className="w-full max-w-lg">
        <h2 className="font-display text-sm text-arcane mb-3">{current.title}</h2>
        <p className="font-body text-lg text-parchment leading-relaxed">{current.body}</p>
        <div className="flex items-center justify-between mt-6">
          <span className="font-body text-sm text-parchment-dim">
            {slide + 1} / {SLIDES.length}
          </span>
          <div className="flex gap-2">
            {slide > 0 && (
              <PixelButton variant="ghost" onClick={() => setSlide((s) => s - 1)}>
                BACK
              </PixelButton>
            )}
            <PixelButton variant="gold" onClick={() => (isLast ? handleClose() : setSlide((s) => s + 1))}>
              {isLast ? "LET'S GO" : 'NEXT'}
            </PixelButton>
          </div>
        </div>
      </PixelPanel>
    </div>
  );
}
