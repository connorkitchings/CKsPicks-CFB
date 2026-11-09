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
  action,
  children,
  className,
}: {
  /** Phone summary that opens the content. */
  title: ReactNode;
  /** Inline heading above the content from `sm:` up. Omit for no heading. */
  heading?: ReactNode;
  /** Control in the header's right side: beside the heading from `sm:` up, first in the opened card on phones. */
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <details data-card="" className={clsx("responsive-disclosure rounded-xl border border-line bg-surface-card shadow-2xs", className)}>
      <summary className="min-h-11 cursor-pointer rounded-xl px-3 py-3 text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
        {title}
      </summary>
      {action !== undefined ? (
        <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2 px-3 pb-3 sm:pt-3 sm:pb-2">
          {heading !== undefined && <h3 className="hidden min-w-0 text-sm font-semibold text-ink sm:block">{heading}</h3>}
          <div className="w-full min-w-0 sm:ml-auto sm:w-auto">{action}</div>
        </div>
      ) : (
        heading !== undefined && <h3 className="hidden px-3 pt-3 text-sm font-semibold text-ink sm:block">{heading}</h3>
      )}
      <div className="px-3 pb-3 text-sm text-ink-muted">{children}</div>
    </details>
  );
}
