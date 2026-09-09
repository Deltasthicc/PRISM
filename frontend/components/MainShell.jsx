'use client';

import { usePathname } from 'next/navigation';

import NavBar from '@/components/NavBar';
import Footer from '@/components/Footer';

export default function MainShell({ children }) {
  const pathname = usePathname();

  // Login and register are both pre-authentication entry pages -- neither
  // should show the navbar, footer, or the 180px top spacing. Without this,
  // a stale authenticated session left in localStorage (NavBar renders
  // whenever useAuthStore's isAuthenticated is true, regardless of route)
  // makes /register render with the full app chrome around it while /login
  // stays clean, which is exactly backwards: register is for someone who
  // isn't (or shouldn't assume they're) already signed in.
  const isAuthEntryPage = pathname === '/login' || pathname === '/register';

  if (isAuthEntryPage) {
    return (
      <main className="w-full">
        {children}
      </main>
    );
  }

  return (
    <>
      <NavBar />

      <main className="max-w-6xl mx-auto px-4 py-6 pt-[180px]">
        {children}
      </main>

      <Footer />
    </>
  );
}