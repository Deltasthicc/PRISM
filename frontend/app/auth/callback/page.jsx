'use client';

import { Suspense, useEffect, useRef, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { completeLogin } from '@/lib/auth/oidc';
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
  const [error, setError] = useState('');
  const attempted = useRef(false);

  useEffect(() => {
    if (attempted.current) return;
    attempted.current = true;

    completeLogin(searchParams)
      .then(() => {
        // Player identity isn't known yet -- it's resolved server-side
        // through the identity binding this account either already has or
        // is about to request. Always land on the registration-completion
        // screen next; it detects an already-registered account itself
        // (see that page's own comment) rather than this page guessing.
        router.replace('/auth/complete-registration');
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
