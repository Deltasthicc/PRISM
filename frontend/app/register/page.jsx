'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuthStore } from '@/store/useAuthStore';
import PixelPanel from '@/components/ui/PixelPanel';
import PixelInput from '@/components/ui/PixelInput';
import PixelButton from '@/components/ui/PixelButton';

export default function RegisterPage() {
  const router = useRouter();
  const register = useAuthStore((s) => s.register);
  const error = useAuthStore((s) => s.error);
  const clearError = useAuthStore((s) => s.clearError);
  const [username, setUsername] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    clearError();
    setSubmitting(true);
    const ok = await register(username);
    setSubmitting(false);
    if (ok) {
      const player = useAuthStore.getState().player;
      router.push(player?.hero_id ? '/dungeon' : '/character');
    }
  }

  return (
    <div className="flex justify-center pt-10">
      <PixelPanel variant="arcane" className="w-full max-w-sm">
        <h1 className="font-display text-sm text-arcane mb-6 text-center">CREATE A CHARACTER</h1>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <PixelInput
            id="username"
            label="USERNAME"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoComplete="username"
          />
          {error && <p className="font-body text-blood text-sm">{error}</p>}
          <PixelButton type="submit" variant="arcane" disabled={submitting} className="mt-2">
            {submitting ? 'FORGING…' : 'BEGIN'}
          </PixelButton>
        </form>
        <p className="font-body text-parchment-dim text-sm text-center mt-4">
          Already have a character?{' '}
          <Link href="/login" className="text-arcane underline">
            Log in
          </Link>
        </p>
      </PixelPanel>
    </div>
  );
}
