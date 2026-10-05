'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { auth } from '@/lib/api/client';
import { useAuthStore } from '@/store/useAuthStore';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Input from '@/components/ui/Input';
import Panel from '@/components/ui/Panel';

// Reached after a real OIDC sign-in whenever the account is not ready to use
// yet. The page asks the backend (GET /auth/me, via the auth store) which of
// five states the verified identity is actually in, and renders exactly that
// state -- it never infers status from a failed registration attempt:
//
//   loading           -> status request in flight
//   not_registered    -> the registration form
//   pending_approval  -> waiting on an administrator
//   rejected          -> an administrator declined the request
//   approved, no role -> binding active, but the identity provider has not
//                        granted the requested role claim yet
//   approved + role   -> bound to its player and sent on to the app
export default function CompleteRegistrationPage() {
  const router = useRouter();
  const { t } = useLanguage();
  const resolveOidcSession = useAuthStore((s) => s.resolveOidcSession);
  const logout = useAuthStore((s) => s.logout);

  const [status, setStatus] = useState(null);
  const [loadError, setLoadError] = useState('');
  const [username, setUsername] = useState('');
  const [fullName, setFullName] = useState('');
  const [designation, setDesignation] = useState('');
  const [department, setDepartment] = useState('');
  const [requestedRole, setRequestedRole] = useState('learner');
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const checked = useRef(false);

  const refreshStatus = useCallback(async () => {
    setLoadError('');
    try {
      const next = await resolveOidcSession();
      if (next.status === 'approved' && next.roles.length > 0) {
        router.replace('/');
        return;
      }
      setStatus(next);
    } catch (cause) {
      if (cause.code === 401) {
        router.replace('/login');
        return;
      }
      setLoadError(cause.message || 'Could not check your registration status.');
    }
  }, [resolveOidcSession, router]);

  useEffect(() => {
    if (checked.current) return;
    checked.current = true;
    refreshStatus();
  }, [refreshStatus]);

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
      await refreshStatus();
    } catch (cause) {
      if (cause.code === 409) {
        // Registered in another tab or session: show the real status.
        await refreshStatus();
      } else {
        setFormError(cause.message || 'Registration could not be completed.');
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleSignOut() {
    await logout();
    router.push('/login');
  }

  if (loadError) {
    return (
      <StatusScreen
        heading="Could not check your account"
        body={loadError}
        actionLabel="Try again"
        onAction={refreshStatus}
        onSignOut={handleSignOut}
      />
    );
  }
  if (!status) {
    return (
      <StatusScreen heading="Checking your account" body="One moment while we look up your registration." busy />
    );
  }
  if (status.status === 'pending_approval') {
    return (
      <StatusScreen
        heading="Waiting for admin approval"
        body={`Your request to join as ${roleLabel(status.requested_role)} has been submitted. You can sign in with full access once an administrator approves it.`}
        actionLabel="Check again"
        onAction={refreshStatus}
        onSignOut={handleSignOut}
      />
    );
  }
  if (status.status === 'rejected') {
    return (
      <StatusScreen
        heading="Access request declined"
        body="An administrator declined this access request. Contact your organization's administrator if you think this is a mistake."
        onSignOut={handleSignOut}
      />
    );
  }
  if (status.status === 'approved') {
    return (
      <StatusScreen
        heading="Approved, role not assigned yet"
        body="Your account is approved, but your organization's identity provider has not granted your role yet, so there is nothing you can open. Ask an administrator to assign it, then check again."
        actionLabel="Check again"
        onAction={refreshStatus}
        onSignOut={handleSignOut}
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
            <p role="alert" className="font-sans text-sm text-[#b3261e] bg-[#fce8e6] border border-[#f5c6c2] rounded-lg px-3 py-2">
              {formError}
            </p>
          )}
          <Button type="submit" disabled={submitting} className="mt-2 w-full">
            {submitting ? 'Submitting...' : 'Request access'}
          </Button>
        </form>
        <button
          type="button"
          onClick={handleSignOut}
          className="font-sans text-sm text-[#757682] hover:underline mt-4 block mx-auto"
        >
          Sign out
        </button>
      </Panel>
    </div>
  );
}

function roleLabel(role) {
  if (role === 'trainer') return 'a trainer';
  if (role === 'learner') return 'a trainee';
  return 'a member';
}

function StatusScreen({ heading, body, busy = false, actionLabel, onAction, onSignOut }) {
  return (
    <div className="flex flex-col items-center pt-16 gap-6 px-4 pb-16">
      <Panel className="w-full max-w-md p-6 text-center" aria-busy={busy}>
        <h1 className="font-sans text-lg font-bold text-[#00236f] mb-2">{heading}</h1>
        <p role="status" className="font-sans text-sm text-[#757682]">{body}</p>
        {actionLabel && onAction && (
          <button
            type="button"
            onClick={onAction}
            className="font-sans text-sm text-[#00236f] font-medium hover:underline mt-5 block mx-auto"
          >
            {actionLabel}
          </button>
        )}
        {onSignOut && (
          <button
            type="button"
            onClick={onSignOut}
            className="font-sans text-sm text-[#757682] hover:underline mt-3 block mx-auto"
          >
            Sign out
          </button>
        )}
      </Panel>
    </div>
  );
}
