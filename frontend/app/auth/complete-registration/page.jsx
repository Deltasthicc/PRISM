'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/api/client';
import { useAuthStore } from '@/store/useAuthStore';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Panel from '@/components/ui/Panel';

// Reached after every real OIDC sign-in (app/auth/callback), whether this
// is a brand-new identity or a returning one -- the frontend has no way
// to tell those apart without calling something, so this page doubles as
// that check: submitting to POST /auth/register (security/rbac.py's
// create_self_service_registration) either succeeds (first time) or comes
// back 409 "already registered" (returning user), and both are handled
// below as expected outcomes, not errors.
//
// Known gap, not silently swallowed: a returning, already-*approved* user
// still lands here and sees "already registered" rather than going
// straight to their dashboard, because resolving an existing account's
// player_id from just a verified token has no endpoint yet (would need a
// dedicated GET /auth/me -- out of scope for this pass). Approval status
// itself is real; only the post-approval "skip this screen" polish isn't.
export default function CompleteRegistrationPage() {
  const router = useRouter();
  const { t } = useLanguage();
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [designation, setDesignation] = useState('');
  const [department, setDepartment] = useState('');
  const [requestedRole, setRequestedRole] = useState('learner');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [outcome, setOutcome] = useState(null); // 'pending' | 'already-registered'

  async function handleSubmit(event) {
    event.preventDefault();
    setFormError('');
    if (!username.trim() || !fullName.trim()) return;

    setSubmitting(true);
    try {
      await auth.registerOidcAccount({
        username: username.trim(),
        full_name: fullName.trim(),
        requested_role: requestedRole,
        designation: designation.trim(),
        department: department.trim(),
      });
      setOutcome('pending');
    } catch (cause) {
      if (cause.code === 409) {
        setOutcome('already-registered');
      } else {
        setFormError(cause.message || 'Registration could not be completed.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  if (outcome === 'pending') {
    return (
      <StatusScreen
        heading="Registration submitted"
        body="Your account has been created and is waiting on admin approval. You'll be able to sign in with full access once an administrator approves it."
      />
    );
  }
  if (outcome === 'already-registered') {
    return (
      <StatusScreen
        heading="You're already registered"
        body="This account has already requested access. If you're still waiting, check with an administrator on its approval status."
      />
    );
  }

  return (
    <div className="flex flex-col items-center pt-16 gap-6 px-4 pb-16">
      <div className="flex flex-col items-center gap-2">
        <Badge tone="accent">{t('brand.name')}</Badge>
        <span className="font-sans text-xl font-bold text-[#00236f] tracking-tight">{t('brand.name')}</span>
      </div>

      <Panel className="w-full max-w-md p-6">
        <h1 className="font-sans text-lg font-bold text-[#00236f] mb-1 text-center">Complete your registration</h1>
        <p className="font-sans text-sm text-[#757682] mb-6 text-center">
          You&rsquo;re signed in with your organization account. A few details, then an admin reviews your access request.
        </p>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <Input id="username" label="Username" value={username} onChange={(event) => setUsername(event.target.value)} required autoComplete="username" />
          <Input id="full-name" label="Full name" value={fullName} onChange={(event) => setFullName(event.target.value)} required />
          <label className="flex flex-col gap-1.5">
            <span className="font-sans text-xs font-semibold text-[#444651]">I am a</span>
            <select
              value={requestedRole}
              onChange={(event) => setRequestedRole(event.target.value)}
              className="bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60 outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f]"
            >
              <option value="learner">Trainee</option>
              <option value="trainer">Trainer</option>
            </select>
          </label>
          <Input id="designation" label="Designation (optional)" value={designation} onChange={(event) => setDesignation(event.target.value)} />
          <Input id="department" label="Department (optional)" value={department} onChange={(event) => setDepartment(event.target.value)} />
          {formError && (
            <p className="font-sans text-sm text-[#b3261e] bg-[#fce8e6] border border-[#f5c6c2] rounded-lg px-3 py-2">
              {formError}
            </p>
          )}
          <Button type="submit" disabled={submitting} className="mt-2 w-full">
            {submitting ? 'Submitting...' : 'Request access'}
          </Button>
        </form>
      </Panel>
    </div>
  );
}

function StatusScreen({ heading, body }) {
  const router = useRouter();
  return (
    <div className="flex flex-col items-center pt-16 gap-6 px-4 pb-16">
      <Panel className="w-full max-w-md p-6 text-center">
        <h1 className="font-sans text-lg font-bold text-[#00236f] mb-2">{heading}</h1>
        <p className="font-sans text-sm text-[#757682]">{body}</p>
        <button
          type="button"
          onClick={() => router.push('/login')}
          className="font-sans text-sm text-[#00236f] font-medium hover:underline mt-5"
        >
          Back to sign in
        </button>
      </Panel>
    </div>
  );
}
