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
          queries: { retry: 1, refetchOnWindowFocus: false },
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
