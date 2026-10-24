import Link from "next/link";
import type { PublicationMode } from "@/lib/publication";
import { displaySystemName } from "@/lib/publication";
import { AppBar, type AppBarBack } from "./AppBar";
import { ThemeToggle } from "./ThemeToggle";
import { SeasonSelector } from "./SeasonSelector";
import { PAGE_WIDTHS, type PageWidth } from "@/lib/page-width";

export function Header({
  season,
  systemName,
  updatedAt,
  publicationMode,
  allowedSeasons,
  width = "narrow",
  status,
  back,
}: {
  season: number | null;
  systemName: string | null;
  updatedAt: Date | null;
  publicationMode: PublicationMode;
  allowedSeasons?: readonly number[];
  width?: PageWidth;
  status?: React.ReactNode;
  /** Phones: the app bar shows this back link and title in place of the section name. */
  back?: AppBarBack;
}) {
  const maxW = PAGE_WIDTHS[width];
  const hasSubrow = Boolean(
    (publicationMode === "predictions" && systemName) || status || updatedAt,
  );
  const systemLabel = publicationMode === "predictions" && systemName ? displaySystemName(systemName) : null;
  return (
    <>
      {/* Phones: the sticky app bar replaces the brand row and menu controls; only `status` stays on the page. */}
      <AppBar season={season} allowedSeasons={allowedSeasons} systemLabel={systemLabel} updatedAt={updatedAt?.toISOString() ?? null} back={back} />
    <header className={`border-b border-line bg-surface-card/80 backdrop-blur${status ? "" : " max-sm:hidden"}`}>
      <div className={`mx-auto flex ${maxW} flex-col gap-1.5 px-4 py-1.5 sm:py-3.5`}>
        <div className="flex items-center justify-between gap-3 max-sm:hidden">
          <Link href="/" className="inline-flex min-h-11 items-center rounded text-lg font-bold tracking-tight text-ink focus-visible:outline-2 focus-visible:outline-accent sm:text-xl">
            CK&rsquo;s Picks
            <span className="ml-1.5 text-xs font-normal text-ink-muted sm:text-sm">
              CFB
            </span>
          </Link>
          <div className="flex shrink-0 items-center gap-2 sm:gap-3">
            {season !== null && allowedSeasons && allowedSeasons.length > 1 && (
              <SeasonSelector season={season} allowedSeasons={allowedSeasons} />
            )}
            {season !== null &&
              !(allowedSeasons && allowedSeasons.length > 1) && (
                <span className="inline-flex items-center rounded-md border border-line bg-surface-inset px-2 py-0.5 text-xs font-semibold tabular-nums text-ink-muted">
                  {season}
                </span>
              )}
            <ThemeToggle />
          </div>
        </div>

        {hasSubrow && (
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-muted">
            {systemLabel && (
              <span className="max-sm:hidden inline-flex items-center rounded-md border border-line bg-surface-inset px-1.5 py-0.5 text-xs font-semibold uppercase tracking-wider text-ink-muted">
                {systemLabel}
              </span>
            )}
            {status}
            {updatedAt && (
              <span className="max-sm:hidden">
                Updated{" "}
                {updatedAt.toLocaleString("en-US", {
                  month: "short",
                  day: "numeric",
                  hour: "numeric",
                  minute: "2-digit",
                })}
              </span>
            )}
          </div>
        )}
      </div>
    </header>
    </>
  );
}

export function Footer({
  publicationMode,
  width = "narrow",
}: {
  publicationMode: PublicationMode;
  width?: PageWidth;
}) {
  const maxW = PAGE_WIDTHS[width];
  return (
    <footer
      className={`mx-auto mt-12 ${maxW} px-4 pb-8 text-center text-xs leading-relaxed text-ink-muted`}
    >
      <p className="mb-1">
        Display only &mdash; not betting advice. CK&rsquo;s Picks is a research
        project that shows{" "}
        {publicationMode === "predictions"
          ? "model leans against market lines"
          : "college football schedules and market lines"}
        ; nothing here is a recommendation or guarantee.
      </p>
      <p>
        Team names and logos are trademarks of their respective schools and
        owners, shown for identification only.
      </p>
    </footer>
  );
}
