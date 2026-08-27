'use client';

import { motion } from 'framer-motion';

const XP_PER_LEVEL = 150;

export default function XPBar({ level, totalXp }) {
  const xpIntoLevel = totalXp % XP_PER_LEVEL;
  const pct = (xpIntoLevel / XP_PER_LEVEL) * 100;

  return (
    <div className="flex items-center gap-3">
      <div className="font-display text-xs bg-gold text-void border-4 border-black px-2 py-1 shrink-0">
        LV {level}
      </div>
      <div className="flex-1">
        <div className="relative h-4 w-full border-4 border-black bg-black p-[2px] overflow-hidden">
          <motion.div
            className="h-full bg-gold"
            animate={{ width: `${pct}%` }}
            transition={{ type: 'spring', stiffness: 100, damping: 20 }}
          />
          <div
            className="absolute inset-[2px] pointer-events-none mix-blend-multiply opacity-70"
            style={{
              backgroundImage:
                'repeating-linear-gradient(to right, transparent 0px, transparent 5px, #000 5px, #000 7px)',
            }}
          />
        </div>
        <div className="font-body text-xs text-parchment-dim mt-0.5">
          {xpIntoLevel} / {XP_PER_LEVEL} XP to next level
        </div>
      </div>
    </div>
  );
}
