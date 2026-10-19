"use client";

import clsx from "clsx";

export function SegmentedControl<T extends string>({
  label,
  value,
  onChange,
  options,
  className,
}: {
  label: string;
  value: T;
  onChange: (value: T) => void;
  options: readonly { value: T; label: string }[];
  className?: string;
}) {
  return (
    <div role="group" aria-label={label} className={clsx("flex min-w-0 rounded-lg border border-line bg-surface-inset p-0.5", className)}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          className={clsx(
            "min-h-11 min-w-0 flex-1 rounded-md px-3 py-2 text-sm font-medium break-words focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
            value === option.value ? "bg-surface-card text-ink shadow-2xs" : "text-ink-muted hover:text-ink",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
