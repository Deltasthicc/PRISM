import { Press_Start_2P, VT323 } from 'next/font/google';

import './globals.css';
import Providers from './providers';
import NavBar from '@/components/NavBar';
import MainShell from '@/components/MainShell';

// Press_Start_2P/VT323 stay loaded as CSS custom properties (--font-press-start
// / --font-vt323) purely for Quest mode's own routes (dungeon/combat/boss/
// character/guild), which still use font-display/font-body. The professional
// shell (this layout, NavBar, Academy, login/register, admin, stats,
// dashboard) uses plain system fonts and never opts into these.
import OnboardingModal from '@/components/OnboardingModal';
import MusicPlayer from '@/components/MusicPlayer';
import Footer from '@/components/Footer';

const pressStart = Press_Start_2P({
  subsets: ['latin'],
  weight: '400',
  variable: '--font-press-start',
  display: 'swap',
});

const vt323 = VT323({
  subsets: ['latin'],
  weight: '400',
  variable: '--font-vt323',
  display: 'swap',
});

export const metadata = {
  title: 'PRISM',
  description:
    'A cross-domain skill-intelligence platform with an adaptive practice RPG built in.',
};

export default function RootLayout({ children }) {
  return (
    <html
      lang="en"
      className={`${pressStart.variable} ${vt323.variable}`}
    >
      {/*
        suppressHydrationWarning: browser extensions (Grammarly, password
        managers, etc.) can inject attributes into <body> before React
        hydrates, causing a hydration mismatch warning.
      */}

      <body suppressHydrationWarning>
        <div className="torch-flicker" aria-hidden="true" />

        <MusicPlayer />

        <Providers>
          <NavBar />

          <main className="max-w-6xl mx-auto px-4 py-6 pt-[180px]">
            {children}
          </main>

          <OnboardingModal />

          <Footer />
        </Providers>
      </body>
    </html>
  );
}