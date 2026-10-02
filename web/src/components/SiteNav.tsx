"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";

const items = [
  ["Picks", "/"],
  ["Results", "/results"],
  ["Ratings", "/ratings"],
  ["Performance", "/performance"],
] as const;

export function SiteNav() {
  const pathname = usePathname();

  // Align navigation container with page content widths.
  const isSlate = pathname === "/" || pathname.startsWith("/results");
  const wide = pathname.startsWith("/matchup");
  const containerClass = isSlate ? "max-w-6xl" : wide ? "max-w-5xl" : "max-w-4xl";

  return (
    <nav aria-label="Main navigation" className="border-b border-line bg-surface-card">
      <div
        className={clsx(
          "mx-auto flex gap-6 overflow-x-auto px-4 py-3 text-sm font-medium",
          containerClass,
        )}
      >
        {items.map(([label, href]) => {
          const isActive = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <Link
              key={href}
              href={href}
              aria-current={isActive ? "page" : undefined}
              className={clsx(
                "whitespace-nowrap transition-colors focus-visible:rounded focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                isActive
                  ? "text-accent-ink font-semibold"
                  : "text-ink-muted hover:text-ink"
              )}
            >
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
