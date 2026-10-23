"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BottomSheet, useSheet } from "@/components/ui/BottomSheet";
import { useIsPhone } from "@/lib/use-is-phone";
import { SeasonSelector } from "./SeasonSelector";
import { ThemeToggle } from "./ThemeToggle";

const TITLES: [prefix: string, title: string][] = [
  ["/ratings", "Ratings"],
  ["/stats", "Graphs"],
  ["/model", "Model"],
  ["/matchup", "Matchup"],
  ["/teams", "Team"],
];

function titleFor(pathname: string): string {
  return TITLES.find(([prefix]) => pathname === prefix || pathname.startsWith(`${prefix}/`))?.[1] ?? "Games";
}

/**
 * The phone app bar: one slim sticky row with the page name (plus the brand on Games) and a menu
 * button. The menu sheet holds the season selector, theme toggle and publication time, and exists
 * only while the viewport is a phone. Its height is the `--app-bar-h` CSS variable (globals.css),
 * which the pinned bars and `scroll-padding-top` build on. Hidden from 640px up.
 */
export function AppBar({
  season,
  allowedSeasons,
  systemLabel,
  updatedAt,
}: {
  season: number | null;
  allowedSeasons?: readonly number[];
  systemLabel: string | null;
  updatedAt: string | null;
}) {
  const pathname = usePathname();
  const phone = useIsPhone();
  const { dialogRef, triggerRef, titleId, open, close } = useSheet({ enabled: phone, closeOn: [pathname, season] });
  const title = titleFor(pathname);
  const updated = updatedAt
    ? new Date(updatedAt).toLocaleString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" })
    : null;

  return (
    <div data-testid="app-bar" className="sticky top-0 z-40 box-border flex h-(--app-bar-h) items-center justify-between gap-3 border-b border-line bg-surface-card px-4 pt-[env(safe-area-inset-top)] sm:hidden">
      <div className="flex min-w-0 items-baseline gap-2">
        {title === "Games" && (
          <Link href="/" className="shrink-0 rounded text-base font-bold tracking-tight text-ink focus-visible:outline-2 focus-visible:outline-accent">
            CK&rsquo;s Picks <span className="text-xs font-normal text-ink-muted">CFB</span>
          </Link>
        )}
        {/* On Games the brand is the title; the name stays for assistive tech and tests. */}
        <span data-testid="app-bar-title" className={title === "Games" ? "sr-only" : "truncate text-base font-bold tracking-tight text-ink"}>{title}</span>
      </div>
      <button
        ref={triggerRef}
        type="button"
        aria-label="Menu"
        aria-haspopup="dialog"
        disabled={!phone}
        onClick={open}
        data-testid="app-menu-button"
        className="-mr-2 inline-flex size-11 shrink-0 items-center justify-center rounded-lg text-ink focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-70"
      >
        <svg aria-hidden viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
          <path d="M4 7h16M4 12h16M4 17h16" />
        </svg>
      </button>
      {phone && (
        <BottomSheet dialogRef={dialogRef} titleId={titleId} onClose={close} title="Menu" data-testid="app-menu-dialog">
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-medium text-ink">Season</span>
            {allowedSeasons && allowedSeasons.length > 1 && season !== null ? (
              <SeasonSelector season={season} allowedSeasons={allowedSeasons} />
            ) : (
              <span className="text-sm font-semibold tabular-nums text-ink-muted">{season ?? "None"}</span>
            )}
          </div>
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-medium text-ink">Theme</span>
            <ThemeToggle />
          </div>
          {systemLabel && <p className="text-sm text-ink-muted">Model: {systemLabel}</p>}
          {updated && <p className="text-sm text-ink-muted">Updated {updated}</p>}
        </BottomSheet>
      )}
    </div>
  );
}
