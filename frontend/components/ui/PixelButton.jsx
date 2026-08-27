'use client';

import clsx from 'clsx';

const VARIANTS = {
  primary: 'bg-ember text-void hover:bg-ember/90',
  arcane: 'bg-arcane text-void hover:bg-arcane/90',
  gold: 'bg-gold text-void hover:bg-gold/90',
  ghost: 'bg-stone text-parchment hover:bg-stone-light',
  danger: 'bg-blood text-parchment hover:bg-blood/90',
};

export default function PixelButton({
  children,
  variant = 'primary',
  className,
  disabled,
  type = 'button',
  ...rest
}) {
  return (
    <button
      type={type}
      disabled={disabled}
      className={clsx(
        'font-display text-xs px-4 py-3 border-4 border-black transition-transform',
        'shadow-pixel-sm active:translate-y-1 active:shadow-none',
        'disabled:opacity-40 disabled:cursor-not-allowed disabled:active:translate-y-0',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-arcane',
        VARIANTS[variant],
        className
      )}
      {...rest}
    >
      {children}
    </button>
  );
}
