"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { BottomSheet, useSheet } from "@/components/ui/BottomSheet";
import { useIsPhone } from "@/lib/use-is-phone";
import { SeasonSelector } from "./SeasonSelector";
import { ThemeToggle } from "./ThemeToggle";
import { etDateTime } from "@/lib/time-et";
import { BRAND_NAME, BRAND_SUFFIX } from "@/lib/brand";

/** Pages whose app bar centers the brand: the four tabs. Matchup and team pages keep a back link and their own title. */
const TAB_TITLES = new Set(["Games", "Ratings", "Graphs", "Model"]);

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

/** A page that sits under another (a matchup under its week) supplies this to show a back link and its own title. */
export type AppBarBack = { href: string; label: string; title: string };

/**
 * The phone app bar: one slim sticky row with a menu button and either the centered brand (the four
 * tabs, with the page name kept for assistive tech and tests) or a back link and visible page title. The menu sheet holds the season selector, theme toggle and publication time, and exists
 * only while the viewport is a phone. Its height is the `--app-bar-h` CSS variable (globals.css),
 * which the pinned bars and `scroll-padding-top` build on. Hidden from 640px up.
 */
export function AppBar({
  season,
  allowedSeasons,
  systemLabel,
  updatedAt,
  back,
}: {
  season: number | null;
  allowedSeasons?: readonly number[];
  systemLabel: string | null;
  updatedAt: string | null;
  back?: AppBarBack;
}) {
  const pathname = usePathname();
  const phone = useIsPhone();
  const { dialogRef, triggerRef, titleId, open, close } = useSheet({ enabled: phone, closeOn: [pathname, season] });
  const title = back?.title ?? titleFor(pathname);
  const tab = !back && TAB_TITLES.has(title);
  const updated = updatedAt
    ? etDateTime(new Date(updatedAt))
    : null;

  return (
    <div data-testid="app-bar" className={`sticky top-0 z-40 box-border h-(--app-bar-h) items-center gap-3 border-b border-line bg-surface-card px-4 pt-[env(safe-area-inset-top)] sm:hidden ${tab ? "grid grid-cols-[2.75rem_1fr_2.75rem]" : "flex justify-between"}`}>
      {tab && <span aria-hidden />}
      <div className={tab ? "flex min-w-0 items-center justify-center" : "flex min-w-0 items-center gap-1"}>
        {back && (
          <Link
            href={back.href}
            aria-label={back.label}
            data-testid="app-bar-back"
            className="-ml-3 inline-flex size-11 shrink-0 items-center justify-center rounded-lg text-accent-ink focus-visible:outline-2 focus-visible:outline-accent"
          >
            <svg aria-hidden viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2.25" strokeLinecap="round" strokeLinejoin="round">
              <path d="M15 5l-7 7 7 7" />
            </svg>
          </Link>
        )}
        {tab && (
          <Link href="/" className="inline-flex min-h-11 shrink-0 items-center rounded text-base font-bold tracking-tight text-ink focus-visible:outline-2 focus-visible:outline-accent">
            {BRAND_NAME} <span className="text-xs font-normal text-ink-muted">{BRAND_SUFFIX}</span>
          </Link>
        )}
        {/* On the tabs the brand is the title; the name stays for assistive tech and tests. */}
        <span data-testid="app-bar-title" title={back ? title : undefined} className={tab ? "sr-only" : "truncate text-base font-bold tracking-tight text-ink"}>{title}</span>
      </div>
      <button
        ref={triggerRef}
        type="button"
        aria-label="Menu"
        aria-haspopup="dialog"
        disabled={!phone}
        onClick={open}
        data-testid="app-menu-button"
        className={`${tab ? "" : "-mr-2 "}inline-flex size-11 shrink-0 items-center justify-center rounded-lg text-ink focus-visible:outline-2 focus-visible:outline-accent disabled:opacity-70`}
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
