'use client';

import { useEffect, useState } from 'react';
import { useAuthStore } from '@/store/useAuthStore';
import { useOnboardingStore } from '@/store/useOnboardingStore';
import Panel from './ui/Panel';
import Button from './ui/Button';

// Professional-shell tour of the real, always-on feature set. Quest Mode
// (the opt-in gamified practice layer) gets one honest, clearly-labeled
// mention at the end rather than most of the tour, since this modal shows
// to every learner on every page -- including ones who never turn Quest
// Mode on and only ever see the professional path.
const SLIDES = [
  {
    title: 'Build your competency profile',
    body: 'Add your role, occupation, and the domains you want to focus on, then take a real baseline assessment -- no self-rating. Every question is source-cited.',
  },
  {
    title: 'See your real gaps',
    body: 'Your competency vector is judged only by questions you have actually answered. Every score shows its evidence and how it was computed -- nothing here is a guess.',
  },
  {
    title: 'Follow your pathway',
    body: 'Prerequisite Pathways orders your gaps by what actually depends on what, across DSA, Official Statistics, Public Policy, and Digital Literacy.',
  },
  {
    title: 'Practice for real',
    body: 'The DSA Sandbox runs your code against a real judge, not a simulated pass/fail. Solving a problem writes real evidence back into your competency vector.',
  },
  {
    title: 'Generate quizzes from your own material',
    body: 'Upload a document and the Source Quiz Generator produces a grounded quiz from it -- every answer traces back to a real excerpt.',
  },
  {
    title: 'Optional: Quest Mode',
    body: 'A separate, opt-in gamified practice layer exists if you want it (dungeon-style rooms, an AI-judged combat loop) -- off by default, and switchable any time from the toggle in the top bar. Nothing about your real competency data changes because of it.',
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
    <div className="fixed inset-0 z-[9997] flex items-center justify-center bg-black/40 px-4">
      <Panel className="w-full max-w-lg">
        <h2 className="font-sans text-base font-bold text-[#00236f] mb-2">{current.title}</h2>
        <p className="font-sans text-sm text-[#444651] leading-relaxed">{current.body}</p>
        <div className="flex items-center justify-between mt-6">
          <span className="font-mono text-xs text-[#757682]">
            {slide + 1} / {SLIDES.length}
          </span>
          <div className="flex gap-2">
            {slide > 0 && (
              <Button variant="ghost" onClick={() => setSlide((s) => s - 1)}>
                Back
              </Button>
            )}
            <Button onClick={() => (isLast ? handleClose() : setSlide((s) => s + 1))}>
              {isLast ? "Let's go" : 'Next'}
            </Button>
          </div>
        </div>
      </Panel>
    </div>
  );
}
