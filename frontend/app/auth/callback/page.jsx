'use client';

import { Suspense, useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { completeLogin } from '@/lib/auth/oidc';
import { useAuthStore } from '@/store/useAuthStore';
import { useLanguage } from '@/lib/i18n/LanguageContext';
import Badge from '@/components/ui/Badge';
import Panel from '@/components/ui/Panel';

// Keycloak redirects here after the user authenticates (see
// lib/auth/oidc.js::beginLogin). Token exchange happens exactly once --
// React 18 StrictMode's dev-only double-invoke of effects would otherwise
// replay the authorization code, which Keycloak correctly rejects the
// second time (a code is single-use), surfacing a confusing error for
// what is actually a successful sign-in.
function CallbackHandler() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { t } = useLanguage();
  const resolveOidcSession = useAuthStore((s) => s.resolveOidcSession);
  const [error, setError] = useState('');
  const attempted = useRef(false);

  useEffect(() => {
    if (attempted.current) return;
    attempted.current = true;

    completeLogin(searchParams)
      .then(async ({ returnTo }) => {
        // Ask the backend (GET /auth/me) who this verified identity is:
        // an approved account with a role goes straight to where it was
        // headed; everyone else (new, pending, rejected, or approved but
        // not yet granted a role) lands on the screen that explains their
        // actual state.
        const status = await resolveOidcSession();
        const ready = status.status === 'approved' && status.roles.length > 0;
        router.replace(ready ? returnTo || '/' : '/auth/complete-registration');
      })
      .catch((cause) => {
        setError(cause.message || 'Sign-in failed.');
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex flex-col items-center pt-16 gap-6 px-4 pb-16">
      <div className="flex flex-col items-center gap-2">
        <Badge tone="accent">{t('brand.name')}</Badge>
      </div>
      <Panel className="w-full max-w-sm p-6 text-center">
        {error ? (
          <>
            <p className="font-sans text-sm text-[#b3261e] bg-[#fce8e6] border border-[#f5c6c2] rounded-lg px-3 py-2">
              {error}
            </p>
            <a href="/login" className="font-sans text-sm text-[#00236f] font-medium hover:underline mt-4 inline-block">
              Back to sign in
            </a>
          </>
        ) : (
          <p className="font-sans text-sm text-[#757682]">Completing sign-in...</p>
        )}
      </Panel>
    </div>
  );
}

export default function AuthCallbackPage() {
  return (
    <Suspense fallback={null}>
      <CallbackHandler />
    </Suspense>
  );
}
