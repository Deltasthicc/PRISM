import clsx from 'clsx';

const TONES = {
  default: 'bg-[#f2f3ff] text-[#444651] border-[#c5c5d3]/60',
  accent: 'bg-[#dce1ff] text-[#00164e] border-[#b6c4ff]',
  warning: 'bg-[#fff4e5] text-[#904d00] border-[#ffd9a8]',
  danger: 'bg-[#fce8e6] text-[#b3261e] border-[#f5c6c2]',
  success: 'bg-[#e6f4ea] text-[#1a7f4b] border-[#b7e1c4]',
};

/** Small tone-coded pill, professional-shell equivalent of Quest's PixelBadge. */
export default function Badge({ children, tone = 'default', className }) {
  return (
    <span
      className={clsx(
        'inline-flex items-center font-mono text-[10px] uppercase tracking-wide px-2 py-0.5 rounded border',
        TONES[tone] || TONES.default,
        className
      )}
    >
      {children}
    </span>
  );
}
