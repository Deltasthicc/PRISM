import { Press_Start_2P, VT323 } from 'next/font/google';
import './globals.css';
import Providers from './providers';
import NavBar from '@/components/NavBar';
import BatSwarm from '@/components/BatSwarm';
import OnboardingModal from '@/components/OnboardingModal';
import MusicPlayer from '@/components/MusicPlayer';

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
  title: 'SIH Learning Tool',
  description: 'A cross-domain skill-intelligence platform with an adaptive practice RPG built in.',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${pressStart.variable} ${vt323.variable}`}>
      <body>
        <div className="torch-flicker" aria-hidden="true" />
        <BatSwarm />
        <MusicPlayer />
        <Providers>
          <NavBar />
          <main className="max-w-6xl mx-auto px-4 py-6">{children}</main>
          <OnboardingModal />
        </Providers>
      </body>
    </html>
  );
}
