import type { ReactNode } from "react";
import clsx from "clsx";

/**
 * Collapsed behind a native `<details>` on phones; open and inline from `sm:` up.
 *
 * The children render once. From `sm:` up the `responsive-disclosure` rules in globals.css force
 * the content open (`::details-content`) and hide the summary, so there is no JS media hook, no
 * hydration flash and no duplicated ids or work.
 */
export function ResponsiveDisclosure({
  title,
  heading,
  children,
  className,
}: {
  /** Phone summary that opens the content. */
  title: ReactNode;
  /** Inline heading above the content from `sm:` up. Omit for no heading. */
  heading?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <details className={clsx("responsive-disclosure", className)}>
      <summary className="min-h-11 cursor-pointer rounded-xl px-3 py-3 text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
        {title}
      </summary>
      {heading !== undefined && <h3 className="hidden px-3 pt-3 text-sm font-semibold text-ink sm:block">{heading}</h3>}
      <div className="px-3 pb-3 text-sm text-ink-muted">{children}</div>
    </details>
  );
}
