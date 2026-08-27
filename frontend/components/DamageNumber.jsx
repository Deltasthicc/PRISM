'use client';

import { motion, AnimatePresence } from 'framer-motion';

const TONE_COLOR = {
  damage: '#c43d3d',
  heal: '#6ee7d0',
  xp: '#e8b339',
};

/**
 * Render a list of transient floating numbers above a combat element.
 * `items` = [{ id, text, tone }]. Parent is responsible for adding an item
 * on each event and pruning it after ~1s (or just always pass a fresh array
 * keyed by a counter — AnimatePresence handles the exit unmount).
 */
export default function DamageNumber({ items }) {
  return (
    <div className="relative h-0 pointer-events-none">
      <AnimatePresence>
        {items.map((item, i) => (
          <motion.span
            key={item.id}
            initial={{ opacity: 0, y: 0, scale: 0.6 }}
            animate={{ opacity: 1, y: -40, scale: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.9, ease: 'easeOut' }}
            className="absolute font-display text-sm whitespace-nowrap"
            style={{
              color: TONE_COLOR[item.tone] || '#ece3cf',
              left: `${i * 6}px`,
              top: `${-(i * 22)}px`,
            }}
          >
            {item.text}
          </motion.span>
        ))}
      </AnimatePresence>
    </div>
  );
}
