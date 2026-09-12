'use client';

import { useEffect, useRef, useState } from 'react';
import { Accessibility } from 'lucide-react';
import { useAccessibility } from '@/lib/a11y/AccessibilityContext';

// Plain hardcoded English strings -- not yet run through the i18n pipeline
// (see app/sampling-lab/page.jsx's own header comment for this project's
// established convention: new features ship in English first rather than
// faking a t() call that doesn't have real translations behind it yet).
//
// Mirrors LanguageSwitcher.jsx's spot in the NavBar and its interaction
// pattern (a compact control that opens on click), but as a popover with
// three real toggles instead of a single <select>, closing on outside click.
export default function AccessibilityMenu({ className = '' }) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef(null);
  const {
    highContrast,
    setHighContrast,
    largeText,
    setLargeText,
    reducedMotion,
    setReducedMotion,
  } = useAccessibility();

  useEffect(() => {
    if (!open) return undefined;

    function handleClickOutside(event) {
      if (containerRef.current && !containerRef.current.contains(event.target)) {
        setOpen(false);
      }
    }

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [open]);

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        aria-haspopup="true"
        aria-expanded={open}
        title="Accessibility settings"
        className="p-2 rounded-lg border border-[#c5c5d3]/40 text-[#757682] hover:text-[#00236f] hover:border-[#00236f]/30 transition-colors"
      >
        <Accessibility size={16} />
      </button>

      {open && (
        <div
          role="menu"
          aria-label="Accessibility settings"
          className="absolute right-0 mt-2 w-64 bg-white border border-[#c5c5d3]/40 rounded-xl shadow-lg p-3 z-50"
        >
          <p className="font-mono text-[10px] font-bold uppercase tracking-wide text-[#00236f] mb-2 px-1">
            Accessibility
          </p>

          <AccessibilityToggleRow
            label="High contrast"
            checked={highContrast}
            onChange={setHighContrast}
          />
          <AccessibilityToggleRow
            label="Large text"
            checked={largeText}
            onChange={setLargeText}
          />
          <AccessibilityToggleRow
            label="Reduced motion"
            checked={reducedMotion}
            onChange={setReducedMotion}
          />
        </div>
      )}
    </div>
  );
}

function AccessibilityToggleRow({ label, checked, onChange }) {
  return (
    <button
      type="button"
      onClick={() => onChange(!checked)}
      role="menuitemcheckbox"
      aria-checked={checked}
      className="w-full flex items-center justify-between gap-2 px-2 py-2 rounded-lg hover:bg-[#f5f6fa] text-left cursor-pointer"
    >
      <span className="text-xs text-[#151c2d] font-medium">{label}</span>
      <span
        className={`relative w-9 h-5 rounded-full transition-colors shrink-0 ${
          checked ? 'bg-[#00236f]' : 'bg-[#dfe2eb]'
        }`}
      >
        <span
          className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow-sm transition-transform ${
            checked ? 'translate-x-4' : 'translate-x-0.5'
          }`}
        />
      </span>
    </button>
  );
}
