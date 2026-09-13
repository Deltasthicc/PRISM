'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

// Merged into /assistant as a side-by-side "Voice" mode toggle instead of a
// separate nav tab -- kept as a redirect, not a deleted route, so any
// existing bookmark or link to /voice still lands somewhere real.
export default function VoiceAssistantRedirectPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace('/assistant');
  }, [router]);

  return null;
}
