'use client';

import { useLanguage } from '@/lib/i18n/LanguageContext';
import { LANGUAGES } from '@/lib/i18n/translations';

export default function LanguageSwitcher({ className = '' }) {
  const { language, setLanguage } = useLanguage();

  return (
    <select
      aria-label="Language"
      value={language}
      onChange={(e) => setLanguage(e.target.value)}
      className={`bg-[#f2f3ff] text-[#00236f] font-sans text-xs font-semibold px-2.5 py-1.5 rounded-lg border border-[#c5c5d3]/40 outline-none cursor-pointer ${className}`}
    >
      {LANGUAGES.map((lang) => (
        <option key={lang.code} value={lang.code}>
          {lang.label}
        </option>
      ))}
    </select>
  );
}
