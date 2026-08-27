'use client';

import { useEffect, useRef } from 'react';
import { usePathname } from 'next/navigation';
import { useMusicStore } from '@/store/useMusicStore';

const TRACKS = {
  exploration: '/audio/exploration.mp3',
  combat: '/audio/combat.mp3',
  boss: '/audio/boss.mp3',
};

const TARGET_VOLUME = 0.5;
const FADE_MS = 500;
const FADE_STEPS = 12;

function trackForPath(pathname) {
  if (pathname.startsWith('/combat/')) return 'combat';
  if (pathname.startsWith('/boss/')) return 'boss';
  return 'exploration';
}

/**
 * Background music, one looping <audio> element swapped/cross-faded between
 * three tracks based on route: dungeon map and every other menu-ish page use
 * `exploration`, a topic fight uses `combat`, the final encounter uses `boss`.
 *
 * Starts muted -- browsers block audio-with-sound until a real user gesture,
 * so playback only ever begins from useMusicStore's toggle(), itself only
 * ever called from the NavBar button's onClick.
 */
export default function MusicPlayer() {
  const pathname = usePathname();
  const enabled = useMusicStore((s) => s.enabled);
  const hydrate = useMusicStore((s) => s.hydrate);
  const audioRef = useRef(null);
  const currentTrackRef = useRef(null);
  const fadeTimerRef = useRef(null);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  const track = trackForPath(pathname || '');

  useEffect(() => {
    const audio = audioRef.current;
    if (!audio) return undefined;

    function clearFade() {
      if (fadeTimerRef.current) {
        clearInterval(fadeTimerRef.current);
        fadeTimerRef.current = null;
      }
    }

    function fade(from, to, onDone) {
      clearFade();
      let step = 0;
      audio.volume = from;
      fadeTimerRef.current = setInterval(() => {
        step += 1;
        audio.volume = from + (to - from) * (step / FADE_STEPS);
        if (step >= FADE_STEPS) {
          clearFade();
          audio.volume = to;
          onDone?.();
        }
      }, FADE_MS / FADE_STEPS);
    }

    if (!enabled) {
      if (!audio.paused) fade(audio.volume, 0, () => audio.pause());
      return clearFade;
    }

    const switchTrack = () => {
      audio.src = TRACKS[track];
      currentTrackRef.current = track;
      audio.volume = 0;
      audio.play().catch(() => {});
      fade(0, TARGET_VOLUME);
    };

    if (currentTrackRef.current !== track) {
      if (audio.paused || audio.volume === 0) switchTrack();
      else fade(audio.volume, 0, switchTrack);
    } else if (audio.paused) {
      audio.volume = 0;
      audio.play().catch(() => {});
      fade(0, TARGET_VOLUME);
    }

    return clearFade;
  }, [enabled, track]);

  return <audio ref={audioRef} loop preload="none" aria-hidden="true" />;
}
