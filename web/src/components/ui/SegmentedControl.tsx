import clsx from "clsx";

// No "use client": the component holds no state, and server pages (the Charts side links)
// import the class helpers to style links as segments.

/** `md`: 44px touch targets on phones, 36px from `sm:`. `sm`: the compact Charts settings-row look. */
export type SegmentedSize = "md" | "sm";

/** `fill` stretches the group and its segments across the row on phones only. */
/** The `md` group insets its segments by 1px so a 36px segment plus border stays within 40px. */
export function segmentedGroupClass(size: SegmentedSize = "md", fill = false): string {
  return clsx(
    fill ? "flex sm:inline-flex" : "inline-flex",
    size === "sm"
      ? "max-w-full flex-wrap min-h-11 items-center gap-0.5 sm:min-h-9 rounded-lg border border-line bg-surface-card p-0.5 shadow-2xs"
      : "rounded-lg border border-line bg-surface-inset p-px",
  );
}

export function segmentedItemClass(active: boolean, size: SegmentedSize = "md", fill = false): string {
  return clsx(
    "inline-flex items-center justify-center rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
    // Phones may wrap a filled segment between words; nothing ever breaks mid-word.
    size === "sm" ? "whitespace-normal sm:whitespace-nowrap" : fill ? "flex-1 whitespace-normal sm:flex-none sm:whitespace-nowrap" : "whitespace-nowrap",
    size === "sm"
      ? clsx("min-h-11 px-3 py-1.5 text-xs font-semibold transition-colors sm:min-h-7.5 sm:py-0", active ? "bg-ink text-surface-card shadow-2xs" : "text-ink-muted hover:bg-surface-inset hover:text-ink")
      : clsx("min-h-11 px-3 py-2 text-sm font-medium sm:min-h-9 sm:py-1.5", active ? "bg-surface-card text-ink shadow-2xs" : "text-ink-muted hover:text-ink"),
  );
}

/** Button group with one pressed option (layout, category and metric switchers). */
export function SegmentedControl<T extends string>({
  label,
  value,
  onChange,
  options,
  size = "md",
  fill = false,
  className,
  testId,
}: {
  /** Group name for assistive tech. */
  label: string;
  value: T;
  onChange: (value: T) => void;
  options: readonly { value: T; label: string; testId?: string }[];
  size?: SegmentedSize;
  fill?: boolean;
  className?: string;
  testId?: string;
}) {
  return (
    <div role="group" aria-label={label} data-testid={testId} className={clsx(segmentedGroupClass(size, fill), className)}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={value === option.value}
          onClick={() => onChange(option.value)}
          data-testid={option.testId}
          className={segmentedItemClass(value === option.value, size, fill)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}
