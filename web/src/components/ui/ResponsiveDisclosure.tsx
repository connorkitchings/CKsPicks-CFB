import type { ReactNode } from "react";
import clsx from "clsx";

/**
 * Collapsed behind a native `<details>` on phones; open and inline from `sm:` up.
 *
 * The children render twice and CSS shows one copy per width, so there is no JS media hook and
 * no hydration flash. Hidden copies stay in the DOM: give children no `data-testid`s or ids, and
 * filter locators with `visible: true` in tests.
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
    <>
      <details className={clsx("sm:hidden", className)}>
        <summary className="min-h-11 cursor-pointer rounded-xl px-3 py-3 text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
          {title}
        </summary>
        <div className="px-3 pb-3 text-sm text-ink-muted">{children}</div>
      </details>
      <div className={clsx("hidden sm:block", className)}>
        {heading !== undefined && <h3 className="px-3 pt-3 text-sm font-semibold text-ink">{heading}</h3>}
        <div className="px-3 pb-3 text-sm text-ink-muted">{children}</div>
      </div>
    </>
  );
}
