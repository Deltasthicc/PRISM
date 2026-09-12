import { Press_Start_2P, VT323 } from 'next/font/google';
import './globals.css';
import './a11y.css';
import Providers from './providers';
import MainShell from '@/components/MainShell';
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
  title: 'PRISM',
  description:
    'Personalized Readiness Intelligence & Skill Mapping -- an explainable competency gap-analysis and learning-pathway platform.',
};

export default function RootLayout({ children }) {
  return (
    <html
      lang="en"
      className={`${pressStart.variable} ${vt323.variable}`}
    >
      <body suppressHydrationWarning>
        <MusicPlayer />

        <Providers>
          <MainShell>
            {children}
          </MainShell>

          <OnboardingModal />
        </Providers>
      </body>
    </html>
  );
}