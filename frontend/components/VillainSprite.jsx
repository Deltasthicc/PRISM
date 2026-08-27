'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import PixelSprite from './PixelSprite';
import { monsterForTopic } from '@/lib/sprites/monsterSprites';

const HIT_FX_FRAMES = [
  '/sprites/fx/hit_frame_1.png',
  '/sprites/fx/hit_frame_2.png',
  '/sprites/fx/hit_frame_3.png',
  '/sprites/fx/hit_frame_4.png',
];
const FX_FRAME_MS = 85;

/**
 * The topic's fixed villain (see lib/sprites/monsterSprites.js for the
 * topic -> monster mapping). Plays a brief recoil + red flash + a 4-frame
 * spark-burst overlay each time `hitKey` changes -- pass something that
 * changes once per landed answer (e.g. lastResult.submission_id), not per
 * render.
 */
export default function VillainSprite({ topic, hitKey, defeated, size = 72 }) {
  const monster = monsterForTopic(topic);
  const [flash, setFlash] = useState(false);
  const [fxFrame, setFxFrame] = useState(0);

  useEffect(() => {
    if (hitKey == null) return undefined;
    setFlash(true);
    setFxFrame(0);
    const flashTimeout = setTimeout(() => setFlash(false), 350);
    const frameInterval = setInterval(
      () => setFxFrame((f) => Math.min(f + 1, HIT_FX_FRAMES.length - 1)),
      FX_FRAME_MS
    );
    return () => {
      clearTimeout(flashTimeout);
      clearInterval(frameInterval);
    };
  }, [hitKey]);

  return (
    <motion.div
      className="relative inline-block"
      animate={flash ? { x: [0, -6, 6, -4, 4, 0] } : { x: 0, opacity: defeated ? 0.35 : 1 }}
      transition={{ duration: 0.35 }}
    >
      <PixelSprite src={monster.image} grid={monster.grid} palette={monster.palette} size={size} title={monster.name} />
      {flash && <div className="absolute inset-0 bg-blood mix-blend-color opacity-60 pointer-events-none" />}
      {flash && (
        // Tiny local FX sprite swapped every ~85ms; not an LCP/optimization candidate.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={HIT_FX_FRAMES[fxFrame]}
          alt=""
          className="absolute pointer-events-none"
          style={{
            width: size * 1.3,
            height: size * 1.3,
            left: '50%',
            top: '50%',
            transform: 'translate(-50%, -50%)',
            imageRendering: 'pixelated',
          }}
        />
      )}
    </motion.div>
  );
}
