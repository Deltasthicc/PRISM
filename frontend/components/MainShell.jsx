'use client';

import { usePathname } from 'next/navigation';

import NavBar from '@/components/NavBar';
import Footer from '@/components/Footer';

export default function MainShell({ children }) {
  const pathname = usePathname();

  // Login should have NO navbar, footer, or the 180px top spacing.
  const isLoginPage = pathname === '/login';

  if (isLoginPage) {
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