'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { useQuery } from '@tanstack/react-query';
import { auth, learning } from '@/lib/api/client';
import { useAuthStore } from '@/store/useAuthStore';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import LanguageSwitcher from '@/components/LanguageSwitcher';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Panel from '@/components/ui/Panel';

// Real account creation + a deliberately short profile (name, occupation,
// and which curriculum you want to focus on) -- not the old form's fake
// cadre/band/target-promotion fields, none of which this app ever used for
// anything real. Every field here maps straight onto a genuine, persisted
// backend column (models/learning.py's LearnerProfile: full_name,
// designation, target_domains), so this is real data from the first screen
// a learner sees, not a placeholder to swap out later.
function RegisterForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t, language } = useLanguage();

  const [username, setUsername] = useState(searchParams.get('username') || '');
  const [fullName, setFullName] = useState('');
  const [designation, setDesignation] = useState('');
  const [curriculumSlug, setCurriculumSlug] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');

  const { data: curricula } = useQuery({
    queryKey: ['register-curricula', language],
    queryFn: async () => (await learning.getCurricula(language)).curricula,
  });

  useEffect(() => {
    if (curricula?.length && !curriculumSlug) setCurriculumSlug(curricula[0].slug);
  }, [curricula, curriculumSlug]);

  async function resolvePlayer(seed) {
    try {
      return (await auth.register(seed)).player;
    } catch (cause) {
      if (cause.code === 400) {
        // Username already exists -- this is really a returning learner who
        // landed on /register directly; fall back to a real login instead
        // of failing outright.
        return (await auth.login(seed)).player;
      }
      throw cause;
    }
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setFormError('');
    const seed = username.trim().toLowerCase();
    if (!seed || !fullName.trim() || !designation.trim() || !curriculumSlug) return;

    setSubmitting(true);
    try {
      const player = await resolvePlayer(seed);
      useAuthStore.setState({ player, isAuthenticated: true });
      await learning.updateProfile(player.player_id, {
        full_name: fullName.trim(),
        designation: designation.trim(),
        target_domains: [curriculumSlug],
      });
      router.push('/baseline-assessment');
    } catch (cause) {
      setFormError(cause.message || t('register.genericError'));
    } finally {
      setSubmitting(false);
    }
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

      <Panel className="w-full max-w-md p-6">
        <h1 className="font-sans text-lg font-bold text-[#00236f] mb-1 text-center">{t('register.heading')}</h1>
        <p className="font-sans text-sm text-[#757682] mb-6 text-center">{t('register.profileSubtitle')}</p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Input
            id="username"
            label={t('register.usernameLabel')}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            required
            autoComplete="username"
          />
          <Input
            id="full-name"
            label={t('register.fullNameLabel')}
            value={fullName}
            onChange={(event) => setFullName(event.target.value)}
            required
            placeholder={t('register.fullNamePlaceholder')}
          />
          <Input
            id="designation"
            label={t('register.occupationLabel')}
            value={designation}
            onChange={(event) => setDesignation(event.target.value)}
            required
            placeholder={t('register.occupationPlaceholder')}
          />
          <label className="flex flex-col gap-1.5">
            <span className="font-sans text-xs font-semibold text-[#444651]">{t('register.specialtyLabel')}</span>
            <select
              value={curriculumSlug}
              onChange={(event) => setCurriculumSlug(event.target.value)}
              required
              className="bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]"
            >
              {!curricula?.length && <option value="">{t('register.loadingSpecialties')}</option>}
              {curricula?.map((curriculum) => (
                <option key={curriculum.slug} value={curriculum.slug}>
                  {curriculum.name}
                </option>
              ))}
            </select>
          </label>
          {formError && (
            <p className="font-sans text-sm text-[#b3261e] bg-[#fce8e6] border border-[#f5c6c2] rounded-lg px-3 py-2">
              {formError}
            </p>
          )}
          <Button type="submit" disabled={submitting || !curricula?.length} className="mt-2 w-full">
            {submitting ? t('register.submitting') : t('register.submit')}
          </Button>
        </form>
        <p className="font-sans text-sm text-[#757682] text-center mt-5">
          {t('register.haveAccount')}{' '}
          <Link href="/login" className="text-[#00236f] font-medium hover:underline">
            {t('register.signIn')}
          </Link>
        </p>
      </Panel>
    </div>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={null}>
      <RegisterForm />
    </Suspense>
  );
}
