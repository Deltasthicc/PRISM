import clsx from 'clsx';

const VARIANTS = {
  default: 'border-[#c5c5d3]/40',
  accent: 'border-[#00236f]/30',
};

/** Base professional-shell surface -- white card, subtle border, soft shadow. */
export default function Panel({ children, className, variant = 'default', as: Tag = 'div', ...rest }) {
  return (
    <Tag
      className={clsx(
        'bg-white rounded-xl p-4 shadow-sm border',
        VARIANTS[variant] || VARIANTS.default,
        className
      )}
      {...rest}
    >
      {children}
    </Tag>
  );
}
