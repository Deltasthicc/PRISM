'use client';

export default function Input({ label, id, className = '', textarea = false, ...rest }) {
  const Comp = textarea ? 'textarea' : 'input';
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={id} className="font-sans text-xs font-semibold text-[#444651]">
          {label}
        </label>
      )}
      <Comp
        id={id}
        className={`bg-white text-[#131b2e] font-sans text-sm px-3 py-2.5 rounded-lg border border-[#c5c5d3]/60
          outline-none focus:border-[#00236f] focus:ring-1 focus:ring-[#00236f] placeholder:text-[#757682] ${className}`}
        {...rest}
      />
    </div>
  );
}
