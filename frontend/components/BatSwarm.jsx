'use client';

import { useEffect, useRef, useState } from 'react';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import PixelSprite from './PixelSprite';
import { BAT_FRAMES, BAT_PALETTE } from '@/lib/sprites/batSprite';

// Quest mode's own routes only -- the professional workspace (Academy,
// dashboard, admin, profile, login/register, the landing page) must not be
// gamified, per the team's own recorded "Quest is optional, not the base
// product" decision. A flying bat swarm over an official-statistics
// competency form is exactly the kind of thing that decision rules out.
const QUEST_ROUTE_PREFIXES = ['/dungeon', '/combat', '/boss', '/character', '/guild', '/leaderboard'];

function isQuestRoute(pathname) {
  return QUEST_ROUTE_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

// A real swarm, not the occasional lone bat -- lots of these on screen
// constantly. Each one is just a cached 10-11KB PNG + a motion.div, so even
// 30 concurrent bats is cheap.
const MAX_CONCURRENT_BATS = 30;
const MIN_SPAWN_MS = 120;
const MAX_SPAWN_MS = 350;
const FIRST_SPAWN_MS = 150;
const FLAP_MS = 160;

function randomBetween(min, max) {
  return min + Math.random() * (max - min);
}

function FlappingBat() {
  const [frame, setFrame] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setFrame((f) => 1 - f), FLAP_MS);
    return () => clearInterval(id);
  }, []);
  return (
    <div style={{ filter: 'drop-shadow(0 0 4px rgba(0,0,0,0.8))' }}>
      <PixelSprite src={BAT_FRAMES[frame].image} grid={BAT_FRAMES[frame].grid} palette={BAT_PALETTE} size={36} title="bat" />
    </div>
  );
}

/**
 * Ambient cave atmosphere: bats occasionally swoop across the screen.
 * Mounted once in app/layout.jsx so it's mountable on every page, but only
 * actually renders anything on Quest mode's own routes (see
 * QUEST_ROUTE_PREFIXES above) -- the professional workspace stays
 * non-gamified. Capped at MAX_CONCURRENT_BATS on screen at once.
 *
 * Deliberately does NOT gate on prefers-reduced-motion: that media feature
 * was found to be permanently ON in this environment (and reportedly the
 * dev's own browser too), which made the whole feature bail out on mount
 * and never spawn a single bat -- no matter how long you waited. This is
 * decorative-only ambiance for an explicitly-requested demo aesthetic, not
 * essential motion, so it always runs on Quest routes. The vignette/scanline
 * CSS elsewhere still honors reduced-motion for real UI transitions.
 */
export default function BatSwarm() {
  const pathname = usePathname();
  const questRoute = isQuestRoute(pathname);
  const [bats, setBats] = useState([]);
  const timeoutRef = useRef(null);
  const countRef = useRef(0);

  useEffect(() => {
    if (!questRoute) {
      // Leaving (or never entering) a Quest route: stop spawning and clear
      // anything already in flight, so a bat can't linger mid-animation
      // into a professional page after a navigation.
      setBats([]);
      countRef.current = 0;
      return undefined;
    }

    function spawnOne() {
      if (countRef.current < MAX_CONCURRENT_BATS) {
        countRef.current += 1;
        setBats((current) => [
          ...current,
          {
            id: `${Date.now()}-${Math.random()}`,
            fromLeft: Math.random() < 0.5,
            startY: randomBetween(8, 70),
            endY: randomBetween(8, 70),
            duration: randomBetween(3.5, 6),
          },
        ]);
      }
    }

    function scheduleNext() {
      timeoutRef.current = setTimeout(() => {
        spawnOne();
        scheduleNext();
      }, randomBetween(MIN_SPAWN_MS, MAX_SPAWN_MS));
    }

    // First bat arrives fast so the feature is obvious right away, instead
    // of the visitor having to wait out a full spawn interval to see one.
    const firstTimeout = setTimeout(() => {
      spawnOne();
      scheduleNext();
    }, FIRST_SPAWN_MS);
    timeoutRef.current = firstTimeout;
    return () => clearTimeout(timeoutRef.current);
  }, [questRoute]);

  function removeBat(id) {
    countRef.current = Math.max(0, countRef.current - 1);
    setBats((current) => current.filter((bat) => bat.id !== id));
  }

  if (!questRoute) return null;

  return (
    <div className="fixed inset-0 pointer-events-none overflow-hidden z-40" aria-hidden="true">
      <AnimatePresence>
        {bats.map((bat) => (
          <motion.div
            key={bat.id}
            className="absolute"
            initial={{ left: bat.fromLeft ? '-5vw' : '105vw', top: `${bat.startY}vh`, opacity: 0 }}
            animate={{
              left: bat.fromLeft ? '105vw' : '-5vw',
              top: `${bat.endY}vh`,
              opacity: [0, 1, 1, 0],
            }}
            transition={{ duration: bat.duration, ease: 'easeInOut' }}
            onAnimationComplete={() => removeBat(bat.id)}
          >
            <FlappingBat />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
