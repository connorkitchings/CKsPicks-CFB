import type { ReactNode } from "react";
import clsx from "clsx";

/** Native disclosure supports touch, keyboard and no-JavaScript reading.
 * React only reconciles open when the prop changes, preserving user toggles across renders.
 */
export function Disclosure({
  title,
  children,
  className,
  open = false,
}: {
  title: ReactNode;
  children: ReactNode;
  className?: string;
  open?: boolean;
}) {
  return (
    <details open={open} className={clsx("group rounded-xl border border-line bg-surface-card", className)}>
      <summary className="min-h-11 cursor-pointer rounded-xl px-3 py-3 text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
        {title}
      </summary>
      <div className="px-3 pb-3 text-sm text-ink-muted">{children}</div>
    </details>
  );
}
