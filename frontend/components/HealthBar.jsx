'use client';

import { useEffect, useState, useRef } from 'react';
import { motion } from 'framer-motion';

/**
 * Reusable HP bar — used by both Combat.jsx and BossFight.jsx (per spec).
 * Renders as a chunky pixel-notched bar rather than a smooth gradient,
 * and briefly shakes whenever `current` drops.
 */
export default function HealthBar({ current, max, label, kind = 'player' }) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (current / max) * 100)) : 0;
  const prevRef = useRef(current);
  const [shake, setShake] = useState(false);

  useEffect(() => {
    if (current < prevRef.current) {
      setShake(true);
      const t = setTimeout(() => setShake(false), 400);
      prevRef.current = current;
      return () => clearTimeout(t);
    }
    prevRef.current = current;
  }, [current]);

  const color =
    pct > 60 ? (kind === 'player' ? '#6ee7d0' : '#ff6b3d') : pct > 25 ? '#e8b339' : '#c43d3d';

  return (
    <div className={shake ? 'animate-shake' : ''}>
      <div className="flex justify-between items-baseline mb-1">
        <span className="font-display text-[10px] text-parchment">{label}</span>
        <span className="font-body text-sm text-parchment-dim">
          {Math.max(0, Math.round(current))}/{max}
        </span>
      </div>
      <div className="relative h-6 w-full border-4 border-black bg-black p-[3px] overflow-hidden">
        <motion.div
          className="h-full"
          style={{ backgroundColor: color }}
          animate={{ width: `${pct}%` }}
          transition={{ type: 'spring', stiffness: 120, damping: 18 }}
        />
        {/* static pixel-notch overlay, independent of fill width */}
        <div
          className="absolute inset-[3px] pointer-events-none mix-blend-multiply opacity-70"
          style={{
            backgroundImage:
              'repeating-linear-gradient(to right, transparent 0px, transparent 5px, #000 5px, #000 7px)',
          }}
        />
      </div>
    </div>
  );
}
