'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuthStore } from '@/store/useAuthStore';

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
    if (ok) router.push('/academy');
  }

  return (
    <div className="flex justify-center pt-16">
      <div className="w-full max-w-sm bg-white border border-[#c5c5d3]/40 rounded-xl shadow-sm p-6">
        <h1 className="font-sans text-lg font-bold text-[#00236f] mb-1 text-center">Create an account</h1>
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
          <button
            type="submit"
            disabled={submitting}
            className="mt-2 font-sans text-sm font-semibold px-4 py-2.5 rounded-lg bg-[#00236f] text-white hover:bg-[#001a54] transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {submitting ? 'Creating…' : 'Create account'}
          </button>
        </form>
        <p className="font-sans text-sm text-[#757682] text-center mt-5">
          Already have an account?{' '}
          <Link href="/login" className="text-[#00236f] font-medium hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
