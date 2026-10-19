"use client";

import { useSyncExternalStore } from "react";

const subscribe = () => () => {};
const hydratedSnapshot = () => true;
const serverSnapshot = () => false;

export function SearchField({
  id,
  label,
  value,
  onChange,
  placeholder = "Search…",
  className = "",
  clearLabel = "Clear filter",
}: {
  id: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
  clearLabel?: string;
}) {
  // Server-rendered fields become editable only after their React handlers are ready.
  // Otherwise early typing can be discarded by the first controlled-input render.
  const hydrated = useSyncExternalStore(subscribe, hydratedSnapshot, serverSnapshot);

  return (
    <div className={`relative min-w-0 ${className}`}>
      <label htmlFor={id} className="sr-only">{label}</label>
      <input
        id={id}
        name={id}
        autoComplete="off"
        type="search"
        readOnly={!hydrated}
        aria-busy={!hydrated}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="min-h-11 w-full rounded-lg border border-line bg-surface-card px-3 pr-12 text-base sm:min-h-9 sm:pr-10 text-ink placeholder:text-ink-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent sm:text-sm [&::-webkit-search-cancel-button]:hidden"
      />
      {value && (
        <button
          type="button"
          aria-label={clearLabel}
          onClick={() => onChange("")}
          className="absolute inset-y-0 right-0 flex min-h-11 w-11 items-center justify-center rounded-lg text-xl sm:min-h-9 sm:w-9 sm:text-base text-ink-muted hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
        >
          <span aria-hidden>×</span>
        </button>
      )}
    </div>
  );
}
