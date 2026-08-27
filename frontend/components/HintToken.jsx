'use client';

import { Sparkles } from 'lucide-react';
import clsx from 'clsx';

export default function HintToken({ tokensRemaining, maxTokens, onUse, disabled, used }) {
  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={onUse}
        disabled={disabled || tokensRemaining <= 0 || used}
        className={clsx(
          'font-display text-[10px] px-3 py-2 border-4 border-black flex items-center gap-2',
          'transition-transform active:translate-y-1',
          tokensRemaining > 0 && !used
            ? 'bg-gold text-void hover:bg-gold/90'
            : 'bg-stone-light text-parchment-dim cursor-not-allowed'
        )}
        title={tokensRemaining <= 0 ? 'No hint tokens left' : 'Reveal a hint'}
      >
        <Sparkles size={14} />
        HINT
      </button>
      <div className="flex gap-1" aria-hidden="true">
        {Array.from({ length: maxTokens }).map((_, i) => (
          <span
            key={i}
            className={clsx(
              'w-3 h-3 border-2 border-black',
              i < tokensRemaining ? 'bg-gold' : 'bg-stone-light opacity-40'
            )}
          />
        ))}
      </div>
      <span className="font-body text-sm text-parchment-dim">
        {tokensRemaining}/{maxTokens}
      </span>
    </div>
  );
}
