'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { Menu, X, Sword, ScrollText, Users, Trophy, BrainCircuit, HelpCircle, Volume2, VolumeX, GraduationCap, ShieldCheck } from 'lucide-react';
import clsx from 'clsx';
import { useAuthStore } from '@/store/useAuthStore';
import { useOnboardingStore } from '@/store/useOnboardingStore';
import { useMusicStore } from '@/store/useMusicStore';
import PixelSprite from './PixelSprite';
import { heroOrDefault } from '@/lib/sprites/heroSprites';

const LINKS = [
  { href: '/academy', label: 'Academy', icon: GraduationCap },
  { href: '/dungeon', label: 'Dungeon', icon: Sword },
  { href: '/stats', label: 'Profile', icon: ScrollText },
  { href: '/guild', label: 'Guild', icon: Users },
  { href: '/leaderboard', label: 'Ranks', icon: Trophy },
  { href: '/dashboard', label: 'AI Core', icon: BrainCircuit },
  { href: '/admin', label: 'Admin', icon: ShieldCheck },
];

export default function NavBar() {
  const [open, setOpen] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const player = useAuthStore((s) => s.player);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const logout = useAuthStore((s) => s.logout);
  const openOnboarding = useOnboardingStore((s) => s.openModal);
  const musicEnabled = useMusicStore((s) => s.enabled);
  const toggleMusic = useMusicStore((s) => s.toggle);

  if (!isAuthenticated) return null;

  async function handleLogout() {
    await logout();
    router.push('/login');
  }

  return (
    <nav className="bg-stone-dark border-b-4 border-black sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
        <Link href="/academy" className="font-display text-arcane text-sm tracking-wider">
          PRISM
        </Link>

        <button
          className="md:hidden text-parchment"
          onClick={() => setOpen((v) => !v)}
          aria-label="Toggle menu"
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>

        <div className="hidden md:flex items-center gap-4">
          {LINKS.map((l) => (
            <NavLink key={l.href} {...l} active={pathname.startsWith(l.href)} />
          ))}
        </div>

        <div className="hidden md:flex items-center gap-3">
          <button
            onClick={toggleMusic}
            aria-label={musicEnabled ? 'Mute music' : 'Play music'}
            title={musicEnabled ? 'Mute music' : 'Play music'}
            className="text-parchment-dim hover:text-arcane"
          >
            {musicEnabled ? <Volume2 size={20} /> : <VolumeX size={20} />}
          </button>
          <button
            onClick={openOnboarding}
            aria-label="How to play"
            title="How to play"
            className="text-parchment-dim hover:text-arcane"
          >
            <HelpCircle size={20} />
          </button>
          <Link href="/stats" className="flex items-center gap-2 hover:opacity-80">
            <PixelSprite
              src={heroOrDefault(player?.hero_id).image}
              grid={heroOrDefault(player?.hero_id).grid}
              palette={heroOrDefault(player?.hero_id).palette}
              size={28}
              title={heroOrDefault(player?.hero_id).name}
              className="border-2 border-black shrink-0"
            />
            <span className="font-body text-parchment-dim text-sm">{player?.username}</span>
          </Link>
          <button
            onClick={handleLogout}
            className="font-display text-[9px] bg-blood text-parchment px-2 py-2 border-2 border-black"
          >
            LOGOUT
          </button>
        </div>
      </div>

      {open && (
        <div className="md:hidden border-t-4 border-black bg-stone-dark px-4 py-3 flex flex-col gap-3">
          <Link
            href="/stats"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 px-2 py-1 hover:opacity-80"
          >
            <PixelSprite
              src={heroOrDefault(player?.hero_id).image}
              grid={heroOrDefault(player?.hero_id).grid}
              palette={heroOrDefault(player?.hero_id).palette}
              size={28}
              title={heroOrDefault(player?.hero_id).name}
              className="border-2 border-black shrink-0"
            />
            <span className="font-body text-parchment-dim text-sm">{player?.username}</span>
          </Link>
          {LINKS.map((l) => (
            <NavLink key={l.href} {...l} active={pathname.startsWith(l.href)} onClick={() => setOpen(false)} />
          ))}
          <button
            onClick={toggleMusic}
            className="font-display text-[9px] flex items-center gap-2 px-2 py-2 text-parchment-dim"
          >
            {musicEnabled ? <Volume2 size={14} /> : <VolumeX size={14} />} {musicEnabled ? 'MUTE MUSIC' : 'PLAY MUSIC'}
          </button>
          <button
            onClick={() => {
              openOnboarding();
              setOpen(false);
            }}
            className="font-display text-[9px] flex items-center gap-2 px-2 py-2 text-parchment-dim"
          >
            <HelpCircle size={14} /> HOW TO PLAY
          </button>
          <button
            onClick={handleLogout}
            className="font-display text-[9px] bg-blood text-parchment px-3 py-2 border-2 border-black self-start mt-1"
          >
            LOGOUT
          </button>
        </div>
      )}
    </nav>
  );
}

function NavLink({ href, label, icon: Icon, active, onClick }) {
  return (
    <Link
      href={href}
      onClick={onClick}
      className={clsx(
        'font-display text-[9px] flex items-center gap-2 px-2 py-2 border-2',
        active ? 'border-arcane text-arcane' : 'border-transparent text-parchment-dim hover:text-parchment'
      )}
    >
      <Icon size={14} />
      {label}
    </Link>
  );
}
