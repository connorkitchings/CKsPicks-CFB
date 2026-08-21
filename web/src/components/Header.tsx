import type { PublicationMode } from "@/lib/publication";
import { ThemeToggle } from "./ThemeToggle";

export function Header({
  season,
  week,
  systemName,
  updatedAt,
  runState,
  publicationMode,
}: {
  season: number | null;
  week: number | null;
  systemName: string | null;
  updatedAt: Date | null;
  runState: string | null;
  publicationMode: PublicationMode;
}) {
  return (
    <header className="border-b border-line bg-surface-card/80 backdrop-blur">
      <div className="mx-auto flex max-w-4xl items-start justify-between gap-3 px-4 py-4">
        <div className="flex min-w-0 flex-col gap-1">
          <h1 className="text-xl font-bold tracking-tight text-ink">
            CK&rsquo;s Picks
            <span className="ml-2 text-sm font-normal text-ink-faint">
              CFB
            </span>
          </h1>
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-ink-faint">
            {publicationMode === "predictions" && systemName && (
              <span className="font-medium text-ink-muted">{systemName}</span>
            )}
            {publicationMode === "predictions" && runState && (
              <span className="rounded bg-surface-inset px-1.5 py-0.5 font-semibold uppercase tracking-wide text-ink-muted">
                {runState}
              </span>
            )}
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
          {season !== null && week !== null && (
            <div className="text-sm font-medium tabular-nums text-ink-muted">
              {season} · Week {week}
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
}: {
  publicationMode: PublicationMode;
}) {
  return (
    <footer className="mx-auto mt-12 max-w-4xl px-4 pb-8 text-center text-[11px] leading-relaxed text-ink-faint">
      <p className="mb-1">
        Display only &mdash; not betting advice. CK&rsquo;s Picks is a research
        project that shows{" "}
        {publicationMode === "predictions"
          ? "model leans against market lines"
          : "college football schedules and market lines"}
        ; nothing here is a recommendation or guarantee.
      </p>
      <p>
        Source:{" "}
        <a
          href="https://github.com/connorkitchings/CKsPicks-CFB"
          className="underline hover:text-ink-muted"
          target="_blank"
          rel="noopener noreferrer"
        >
          github.com/connorkitchings/CKsPicks-CFB
        </a>
      </p>
    </footer>
  );
}
