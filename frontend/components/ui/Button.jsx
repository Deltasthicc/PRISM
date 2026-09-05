import clsx from 'clsx';

const VARIANTS = {
  primary: 'bg-[#00236f] text-white hover:bg-[#001a54]',
  accent: 'bg-[#fe932c] text-white hover:bg-[#e57e1a]',
  ghost: 'bg-white text-[#00236f] border border-[#c5c5d3]/60 hover:bg-[#f2f3ff]',
  danger: 'bg-[#b3261e] text-white hover:bg-[#8f1e18]',
};

/** Professional-shell equivalent of Quest's PixelButton. */
export default function Button({
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
        'font-sans text-sm font-semibold px-4 py-2.5 rounded-lg transition-colors',
        'disabled:opacity-50 disabled:cursor-not-allowed',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#00236f]',
        VARIANTS[variant] || VARIANTS.primary,
        className
      )}
      {...rest}
    >
      {children}
    </button>
  );
}
