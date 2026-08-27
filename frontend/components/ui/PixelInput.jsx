'use client';

export default function PixelInput({ label, id, className = '', textarea = false, ...rest }) {
  const Comp = textarea ? 'textarea' : 'input';
  return (
    <div className="flex flex-col gap-2">
      {label && (
        <label htmlFor={id} className="font-display text-[10px] text-arcane tracking-wide">
          {label}
        </label>
      )}
      <Comp
        id={id}
        className={`bg-void text-parchment font-body text-lg px-3 py-2 border-4 border-black
          focus:outline-none focus:border-arcane placeholder:text-parchment-dim/50 ${className}`}
        {...rest}
      />
    </div>
  );
}
