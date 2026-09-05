'use client';

import { useAuthStore } from '@/store/useAuthStore';

/** Reserves space for NavBar's fixed two-row height only while it's actually
 * rendered (NavBar hides itself when unauthenticated -- see NavBar.jsx) --
 * otherwise /login and /register would carry a large empty gap at the top. */
export default function MainShell({ children }) {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  return (
    <main className={`max-w-6xl mx-auto px-4 py-6 ${isAuthenticated ? 'pt-[180px]' : ''}`}>
      {children}
    </main>
  );
}
