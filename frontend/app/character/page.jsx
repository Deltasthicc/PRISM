'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useRequireAuth } from '@/lib/useRequireAuth';
import { useAuthStore } from '@/store/useAuthStore';
import { HEROES } from '@/lib/sprites/heroSprites';
import PixelPanel from '@/components/ui/PixelPanel';
import PixelButton from '@/components/ui/PixelButton';
import PixelBadge from '@/components/ui/PixelBadge';
import PixelSprite from '@/components/PixelSprite';

export default function CharacterSelectPage() {
  const { ready } = useRequireAuth();
  const router = useRouter();
  const player = useAuthStore((s) => s.player);
  const selectHero = useAuthStore((s) => s.selectHero);
  const [selected, setSelected] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  if (!ready || !player) return null;

  async function handleConfirm() {
    if (!selected) return;
    setSaving(true);
    setError(null);
    const ok = await selectHero(selected);
    setSaving(false);
    if (ok) router.push('/dungeon');
    else setError('Could not save your choice. Try again.');
  }

  return (
    <div className="max-w-4xl mx-auto flex flex-col gap-5">
      <div className="text-center">
        <h1 className="font-display text-sm text-parchment">CHOOSE YOUR HERO</h1>
        <p className="font-body text-parchment-dim mt-2">
          Every hero carries one unique power, usable 3 times per hour. Pick whoever suits how you fight.
        </p>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {Object.entries(HEROES).map(([id, hero]) => {
          const isSelected = selected === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => setSelected(id)}
              className="text-left"
            >
              <PixelPanel
                variant={isSelected ? 'arcane' : 'default'}
                className={isSelected ? 'ring-4 ring-arcane' : ''}
              >
                <div className="flex flex-col items-center gap-2 text-center">
                  <PixelSprite src={hero.image} grid={hero.grid} palette={hero.palette} size={64} title={hero.name} />
                  <span className="font-display text-[10px] text-parchment">{hero.name}</span>
                  <PixelBadge tone={hero.gender === 'male' ? 'arcane' : 'gold'}>{hero.gender}</PixelBadge>
                  <div className="mt-1 border-t-2 border-black w-full pt-2">
                    <p className="font-display text-[8px] text-ember">{hero.powerupName}</p>
                    <p className="font-body text-base text-parchment-dim mt-1">{hero.powerupDescription}</p>
                  </div>
                </div>
              </PixelPanel>
            </button>
          );
        })}
      </div>

      {error && <p className="font-body text-blood text-center">{error}</p>}

      <div className="flex justify-center">
        <PixelButton variant="gold" disabled={!selected || saving} onClick={handleConfirm}>
          {saving ? 'ENTERING THE DUNGEON…' : 'BEGIN YOUR JOURNEY'}
        </PixelButton>
      </div>
    </div>
  );
}
