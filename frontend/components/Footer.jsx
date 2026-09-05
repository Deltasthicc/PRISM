import React from 'react';
import { BadgeCheck } from 'lucide-react';

export default function Footer() {
  return (
    <footer className="w-full bg-[#f2f3ff] py-4 px-4 sm:px-8 text-[#444651] text-xs border-t border-[#c5c5d3]/30 mt-auto">
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3 text-center md:text-left">
        <div className="flex items-center gap-2 justify-center md:justify-start">
          <BadgeCheck size={30} />
          <p className="text-xs">
            © 2024 Ministry of Statistics and Programme Implementation (MoSPI) • Smart India Hackathon Prototype 26101
          </p>
        </div>
        <div className="flex items-center gap-3 font-mono text-[11px] text-[#757682] flex-wrap justify-center">
          <span className="flex items-center gap-1">
            <span className="material-symbols-outlined text-[14px]">history</span>Audit: ISO-27001 Staging
          </span>
          <span>•</span>
          <span className="flex items-center gap-1">
            <span className="material-symbols-outlined text-[14px]">policy</span>NDSAP-Aligned
          </span>
          <span>•</span>
          <span>Sync: Catalog Mode</span>
        </div>
      </div>
    </footer>
  );
}
