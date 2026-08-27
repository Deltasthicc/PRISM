'use client';

import { useEffect, useState } from 'react';
import PixelButton from './ui/PixelButton';
import { heroOrDefault } from '@/lib/sprites/heroSprites';

function minutesUntil(resetsAt) {
  if (!resetsAt) return null;
  const ms = new Date(resetsAt).getTime() - Date.now();
  return ms > 0 ? Math.ceil(ms / 60000) : null;
}

/**
 * Triggers the player's chosen hero's powerup. Uses-remaining/cooldown state
 * comes from the server (Player.powerup_uses_this_window / _window_start) --
 * this just displays it and re-renders every 30s so an expired cooldown
 * clears itself without needing a page refresh.
 */
export default function PowerupButton({ heroId, usesRemaining, resetsAt, onUse, disabled }) {
  const hero = heroOrDefault(heroId);
  const [, forceTick] = useState(0);

  useEffect(() => {
    const id = setInterval(() => forceTick((n) => n + 1), 30000);
    return () => clearInterval(id);
  }, []);

  const onCooldown = !usesRemaining || usesRemaining <= 0;
  const minutesLeft = onCooldown ? minutesUntil(resetsAt) : null;

  return (
    <PixelButton variant="primary" disabled={disabled || onCooldown} onClick={onUse} title={hero.powerupDescription}>
      {onCooldown
        ? `${hero.powerupName} (${minutesLeft ? `${minutesLeft}m` : 'ready soon'})`
        : `${hero.powerupName} — ${usesRemaining}/3`}
    </PixelButton>
  );
}
