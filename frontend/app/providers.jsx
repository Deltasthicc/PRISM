'use client';

import { useEffect, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from '@/store/useAuthStore';
import { LanguageProvider } from '@/lib/i18n/LanguageContext';
import { AccessibilityProvider } from '@/lib/a11y/AccessibilityContext';

function AuthBootstrap() {
  const fetchMe = useAuthStore((s) => s.fetchMe);
  useEffect(() => {
    fetchMe();
  }, [fetchMe]);
  return null;
}

export default function Providers({ children }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            refetchOnWindowFocus: false,
            // Without a default staleTime, react-query's own default (0) marks
            // every query stale the instant it resolves, so navigating back to
            // an already-visited route (nav bar, browser back) always re-fires
            // its fetches before showing anything -- this is what made
            // ordinary navigation feel slow. 30s is short enough that genuinely
            // changing data (accuracy history, dungeon room state, quiz
            // progress) still looks fresh within a session, but long enough
            // that clicking between tabs a few times in a row reuses the
            // cache instead of re-fetching. Queries that need something
            // different (near-static reference data, or live/polling state)
            // override this per-call -- see queryKey 'curricula' and
            // 'competency-quiz-topics' for the former, and host-session's/
            // join's 'live-session-state' (refetchInterval: 3000) for the
            // latter, which is intentionally left alone.
            staleTime: 30 * 1000,
            gcTime: 5 * 60 * 1000,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={client}>
      <LanguageProvider>
        <AccessibilityProvider>
          <AuthBootstrap />
          {children}
        </AccessibilityProvider>
      </LanguageProvider>
    </QueryClientProvider>
  );
}
