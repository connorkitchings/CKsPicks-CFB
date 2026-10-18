import clsx from "clsx";

/**
 * Shared look of the chart settings row's grouped controls (toggles, side links, week stepper),
 * kept 36px tall (`min-h-9`) like the row's selects and buttons. A plain module so the server
 * page and client components can both import the strings.
 */
export const SEGMENTED_GROUP = "inline-flex min-h-9 items-center gap-0.5 rounded-lg border border-line bg-surface-card p-0.5 shadow-2xs";

export function segmentedItem(active: boolean): string {
  return clsx(
    "inline-flex min-h-7.5 items-center rounded-md px-3 text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
    active ? "bg-ink text-surface-card shadow-2xs" : "text-ink-muted hover:bg-surface-inset hover:text-ink",
  );
}
