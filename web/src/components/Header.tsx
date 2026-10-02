import type { PublicationMode } from "@/lib/publication";
import { displaySystemName } from "@/lib/publication";
import { ThemeToggle } from "./ThemeToggle";
import { SeasonSelector } from "./SeasonSelector";

export function Header({
  season,
  systemName,
  updatedAt,
  publicationMode,
  allowedSeasons,
  wide = false,
  containerWidth,
  status,
}: {
  season: number | null;
  systemName: string | null;
  updatedAt: Date | null;
  publicationMode: PublicationMode;
  allowedSeasons?: readonly number[];
  /** Wider page container (matchup pages); the nav widens itself by route. */
  wide?: boolean;
  containerWidth?: string;
  status?: React.ReactNode;
}) {
  const maxW = containerWidth ?? (wide ? "max-w-5xl" : "max-w-4xl");
  return (
    <header className="border-b border-line bg-surface-card/80 backdrop-blur">
      <div className={`mx-auto flex ${maxW} items-start justify-between gap-3 px-4 py-4`}>
        <div className="flex min-w-0 flex-col gap-1.5">
          <h1 className="text-xl font-bold tracking-tight text-ink">
            CK&rsquo;s Picks
            <span className="ml-2 text-sm font-normal text-ink-faint">
              CFB
            </span>
          </h1>
          <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5 text-[11px] text-ink-faint">
            {publicationMode === "predictions" && systemName && (
              <span className="inline-flex items-center rounded-md border border-line bg-surface-inset px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink-muted">
                {displaySystemName(systemName)}
              </span>
            )}
            {status}
            {updatedAt && (
              <span>
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
        </div>
        <div className="flex shrink-0 items-center gap-3">
          {season !== null && allowedSeasons && allowedSeasons.length > 1 && (
            <SeasonSelector season={season} allowedSeasons={allowedSeasons} />
          )}
          {season !== null &&
            !(allowedSeasons && allowedSeasons.length > 1) && (
              <div className="text-sm font-medium tabular-nums text-ink-muted">
                {season}
              </div>
            )}
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

export function Footer({
  publicationMode,
  wide = false,
  containerWidth,
}: {
  publicationMode: PublicationMode;
  wide?: boolean;
  containerWidth?: string;
}) {
  const maxW = containerWidth ?? (wide ? "max-w-5xl" : "max-w-4xl");
  return (
    <footer
      className={`mx-auto mt-12 ${maxW} px-4 pb-8 text-center text-[11px] leading-relaxed text-ink-faint`}
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
