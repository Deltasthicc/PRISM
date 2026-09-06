'use client';

import { useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuthStore } from '@/store/useAuthStore';

// The shared Render-hosted Keycloak spins down after periods of no traffic,
// and a cold boot has been measured taking several minutes. Without this,
// a cold-start login just sits on "Signing in..." with no explanation --
// which reads as a broken/looping login rather than a slow one. This nudges
// in only once the wait is already unusual for a warm instance.
const SLOW_LOGIN_HINT_MS = 8000;

export default function LoginPage() {
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const error = useAuthStore((s) => s.error);
  const clearError = useAuthStore((s) => s.clearError);
  const [username, setUsername] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [slowHint, setSlowHint] = useState(false);
  const slowHintTimer = useRef(null);

  useEffect(() => () => clearTimeout(slowHintTimer.current), []);

  async function handleSubmit(e) {
    e.preventDefault();
    clearError();
    setSubmitting(true);
    setSlowHint(false);
    slowHintTimer.current = setTimeout(() => setSlowHint(true), SLOW_LOGIN_HINT_MS);
    const ok = await login(username);
    clearTimeout(slowHintTimer.current);
    setSlowHint(false);
    setSubmitting(false);
    if (ok) router.push('/academy');
  }

  return (
    <div className="flex justify-center pt-16">
      <div className="w-full max-w-sm bg-white border border-[#c5c5d3]/40 rounded-xl shadow-sm p-6">
        <h1 className="font-sans text-lg font-bold text-[#00236f] mb-1 text-center">Sign in</h1>
        <p className="font-sans text-sm text-[#757682] mb-6 text-center">
          Username only for now — no password yet.
        </p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="font-sans text-xs font-semibold text-[#444651]">Username</span>
            <input
              id="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              autoComplete="username"
              autoFocus
              className="bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]"
            />
          </label>
          {error && (
            <p className="font-sans text-sm text-[#b3261e] bg-[#fce8e6] border border-[#f5c6c2] rounded-lg px-3 py-2">
              {error}
            </p>
          )}
          {submitting && slowHint && (
            <p className="font-sans text-sm text-[#00236f] bg-[#eef1fb] border border-[#c5d0f5] rounded-lg px-3 py-2">
              Still working — the sign-in service can take a few minutes to wake up after being idle. No need to retry, this should finish on its own.
            </p>
          )}
          <button
            type="submit"
            disabled={submitting}
            className="mt-2 font-sans text-sm font-semibold px-4 py-2.5 rounded-lg bg-[#00236f] text-white hover:bg-[#001a54] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
        <p className="font-sans text-sm text-[#757682] text-center mt-5">
          New here?{' '}
          <Link href="/register" className="text-[#00236f] font-medium hover:underline">
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}
