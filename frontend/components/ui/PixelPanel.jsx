import clsx from 'clsx';

/**
 * Base "carved stone" surface used by every card/modal/panel in the app.
 * variant="arcane" gives the teal AI/knowledge-related glow border instead
 * of the default black bevel.
 */
export default function PixelPanel({ children, className, variant = 'default', as: Tag = 'div', ...rest }) {
  return (
    <Tag
      className={clsx(
        'bg-stone p-4',
        variant === 'arcane' ? 'pixel-bevel-arcane' : 'pixel-bevel',
        className
      )}
      {...rest}
    >
      {children}
    </Tag>
  );
}
