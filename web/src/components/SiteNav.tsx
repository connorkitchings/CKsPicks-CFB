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

function NavIcon({ href, active }: { href: string; active: boolean }) {
  const strokeWidth = active ? 2.25 : 1.75;
  switch (href) {
    case "/":
      return (
        <svg
          aria-hidden="true"
          className="h-5 w-5 sm:hidden"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M16.5 6v.75m0 3v.75m0 3v.75m0 3V18m-9-5.25h5.25M7.5 15h3M3.375 5.25c-.621 0-1.125.504-1.125 1.125v3.026a2.999 2.999 0 010 5.198v3.026c0 .621.504 1.125 1.125 1.125h17.25c.621 0 1.125-.504 1.125-1.125v-3.026a2.999 2.999 0 010-5.198V6.375c0-.621-.504-1.125-1.125-1.125H3.375z"
          />
        </svg>
      );
    case "/results":
      return (
        <svg
          aria-hidden="true"
          className="h-5 w-5 sm:hidden"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
          />
        </svg>
      );
    case "/ratings":
      return (
        <svg
          aria-hidden="true"
          className="h-5 w-5 sm:hidden"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
          />
        </svg>
      );
    case "/performance":
      return (
        <svg
          aria-hidden="true"
          className="h-5 w-5 sm:hidden"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M2.25 18L9 11.25l4.306 4.307a11.95 11.95 0 015.814-5.519l2.74-1.22m0 0l-5.94-2.28m5.94 2.28l-2.28 5.941"
          />
        </svg>
      );
    default:
      return null;
  }
}

export function SiteNav() {
  const pathname = usePathname();

  // Align navigation container with page content widths on desktop.
  const isSlate = pathname === "/" || pathname.startsWith("/results");
  const wide = pathname.startsWith("/matchup");
  const containerClass = isSlate ? "sm:max-w-6xl" : wide ? "sm:max-w-5xl" : "sm:max-w-4xl";

  return (
    <nav
      aria-label="Main navigation"
      className="fixed bottom-0 inset-x-0 z-40 border-t border-line bg-surface-card/90 backdrop-blur-md pb-[env(safe-area-inset-bottom)] shadow-[0_-4px_16px_rgba(0,0,0,0.04)] dark:shadow-[0_-4px_16px_rgba(0,0,0,0.3)] sm:static sm:z-auto sm:border-t-0 sm:border-b sm:bg-surface-card sm:backdrop-blur-none sm:pb-0 sm:shadow-none"
    >
      <div
        className={clsx(
          "mx-auto grid grid-cols-4 h-14 items-stretch px-2 sm:flex sm:h-auto sm:gap-6 sm:overflow-x-auto sm:px-4 sm:py-3 sm:text-sm sm:font-medium",
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
                "flex flex-col items-center justify-center gap-0.5 text-[10px] font-medium transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                "sm:flex-row sm:gap-1.5 sm:rounded-md sm:px-3 sm:py-1 sm:text-sm sm:whitespace-nowrap",
                isActive
                  ? "text-accent font-semibold sm:bg-surface-inset sm:font-semibold sm:text-ink sm:shadow-2xs"
                  : "text-ink-muted hover:text-ink sm:text-ink-muted sm:hover:bg-surface-inset/60 sm:hover:text-ink",
              )}
            >
              <NavIcon href={href} active={isActive} />
              <span>{label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
