'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { useAuthStore } from '@/store/useAuthStore';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Panel from '@/components/ui/Panel';

// Just the login form. A username that doesn't exist yet routes to
// /register instead of silently creating an account here -- login and
// register are genuinely different backend operations (GET .../by-username
// vs POST .../create, see lib/api/client.js's `auth` export) and now stay
// separate routes instead of one state machine that also rendered profile
// setup and the baseline quiz in-place.
export default function LoginPage() {
  const router = useRouter();
  const { t } = useLanguage();
  const [username, setUsername] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  async function handleSubmit(event) {
    event.preventDefault();
    setFormError('');
    const trimmed = username.trim().toLowerCase();
    if (!trimmed) return;

    setSubmitting(true);
    const ok = await useAuthStore.getState().login(trimmed);
    setSubmitting(false);

    if (ok) {
      router.push('/academy');
      return;
    }

    const errorCode = useAuthStore.getState().errorCode;
    if (errorCode === 404) {
      router.push(`/register?username=${encodeURIComponent(trimmed)}`);
      return;
    }
    setFormError(t('login.genericError') || 'Could not sign in. Please try again.');
  }

  return (
    <div className="flex flex-col items-center pt-16 gap-6 px-4 pb-16">
      <LanguageSwitcher className="self-end mr-4 sm:mr-0" />

      <div className="flex flex-col items-center gap-2">
        <Badge tone="accent">{t('brand.name')}</Badge>
        <span className="font-sans text-xl font-bold text-[#00236f] tracking-tight">{t('brand.name')}</span>
        <span className="font-mono text-[11px] text-[#757682] uppercase tracking-wider text-center">
          {t('brand.tagline')}
        </span>
      </div>

      <Panel className="w-full max-w-sm p-6">
        <h1 className="font-sans text-lg font-bold text-[#00236f] mb-1 text-center">{t('login.heading')}</h1>
        <p className="font-sans text-sm text-[#757682] mb-6 text-center">{t('login.subtitle')}</p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5">
            <span className="font-sans text-xs font-semibold text-[#444651]">{t('login.usernameLabel')}</span>
            <input
              id="username"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              required
              autoComplete="username"
              autoFocus
              className="bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]"
            />
          </label>
          {formError && (
            <p className="font-sans text-sm text-[#b3261e] bg-[#fce8e6] border border-[#f5c6c2] rounded-lg px-3 py-2">
              {formError}
            </p>
          )}
          <Button type="submit" disabled={submitting} className="mt-2 w-full">
            {submitting ? t('login.submitting') : t('login.submit')}
          </Button>
        </form>
        <p className="font-sans text-sm text-[#757682] text-center mt-5">
          {t('login.newHere')}{' '}
          <Link href="/register" className="text-[#00236f] font-medium hover:underline">
            {t('login.createAccount')}
          </Link>
        </p>
      </Panel>
    </div>
  );
}
