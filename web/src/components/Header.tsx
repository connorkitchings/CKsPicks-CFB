import type { PublicationMode } from "@/lib/publication";

export function Header({
  season,
  week,
  systemName,
  modelId,
  updatedAt,
  runState,
  publicationMode,
}: {
  season: number | null;
  week: number | null;
  systemName: string | null;
  modelId: string | null;
  updatedAt: Date | null;
  runState: string | null;
  publicationMode: PublicationMode;
}) {
  return (
    <header className="border-b border-zinc-200 bg-white/80 backdrop-blur dark:border-zinc-800 dark:bg-zinc-950/80">
      <div className="mx-auto flex max-w-4xl flex-col gap-1 px-4 py-4">
        <div className="flex items-baseline justify-between gap-3">
          <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-50">
            CK&rsquo;s Picks
            <span className="ml-2 text-sm font-normal text-zinc-500 dark:text-zinc-400">
              CFB
            </span>
          </h1>
          {season !== null && week !== null && (
            <div className="text-sm text-zinc-600 dark:text-zinc-300">
              {season} · Week {week}
            </div>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-zinc-400 dark:text-zinc-500">
          {publicationMode === "predictions" && systemName && (
            <span>Model: {systemName}</span>
          )}
          {publicationMode === "predictions" && runState && (
            <span className="rounded bg-zinc-100 px-1.5 py-0.5 font-semibold uppercase tracking-wide text-zinc-600 dark:bg-zinc-900 dark:text-zinc-300">
              {runState}
            </span>
          )}
          {publicationMode === "predictions" && modelId && (
            <span className="font-mono">
              id: <span className="text-zinc-500 dark:text-zinc-400">{modelId}</span>
            </span>
          )}
          {updatedAt && (
            <span>
              {publicationMode === "predictions" ? "Predictions" : "Markets"} updated{" "}
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
    </header>
  );
}

export function Footer({ publicationMode }: { publicationMode: PublicationMode }) {
  return (
    <footer className="mx-auto mt-12 max-w-4xl px-4 pb-8 text-center text-[11px] leading-relaxed text-zinc-400 dark:text-zinc-600">
      <p className="mb-1">
        Display only &mdash; not betting advice. CK&rsquo;s Picks is a research
        project that shows {publicationMode === "predictions"
          ? "model leans against market lines"
          : "college football schedules and market lines"}; nothing here is a
        recommendation or guarantee.
      </p>
      <p>
        Source:{" "}
        <a
          href="https://github.com/connorkitchings/CKsPicks-CFB"
          className="underline hover:text-zinc-600 dark:hover:text-zinc-400"
          target="_blank"
          rel="noopener noreferrer"
        >
          github.com/connorkitchings/CKsPicks-CFB
        </a>
      </p>
    </footer>
  );
}
