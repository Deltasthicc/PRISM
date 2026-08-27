import clsx from 'clsx';

const TONES = {
  gold: 'bg-gold text-void',
  arcane: 'bg-arcane text-void',
  ember: 'bg-ember text-void',
  blood: 'bg-blood text-parchment',
  stone: 'bg-stone-light text-parchment',
};

export default function PixelBadge({ children, tone = 'stone', className }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1 font-display text-[9px] px-2 py-1 border-2 border-black',
        TONES[tone],
        className
      )}
    >
      {children}
    </span>
  );
}
