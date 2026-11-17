/** Disclosure affordance for a `<details>` summary: points down when closed, flips when the parent is open. */
export function Chevron() {
  return (
    <svg aria-hidden="true" viewBox="0 0 20 20" className="h-4 w-4 shrink-0 text-ink-muted transition-transform in-[details[open]]:rotate-180" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="m5 8 5 5 5-5" />
    </svg>
  );
}
