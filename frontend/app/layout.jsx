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
  description: 'A cross-domain skill-intelligence platform with an adaptive practice RPG built in.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${pressStart.variable} ${vt323.variable}`}>
      {/* suppressHydrationWarning: browser extensions (Grammarly, password
          managers, etc.) inject their own attributes -- e.g.
          data-new-gr-c-s-check-loaded, data-gr-ext-installed -- into <body>
          before React hydrates. React then reports a mismatch between the
          server-rendered HTML and what it finds in the DOM, but the
          "mismatch" is the extension's own attribute, not anything this app
          rendered differently. This only silences that one, one-level-deep
          false positive on <body> itself; a real mismatch inside the page
          content still reports normally. */}
      <body suppressHydrationWarning>
        <Providers>
          <NavBar />
          <MainShell>{children}</MainShell>
        </Providers>
      </body>
    </html>
  );
}
