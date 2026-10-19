import clsx from "clsx";
import type { Performance } from "@/lib/v5";
import { winRatePct } from "@/lib/slate";

type Rec = { win: number; loss: number; push: number };
const ZERO: Rec = { win: 0, loss: 0, push: 0 };

/**
 * Compact record cell:
 * Top row: category label on left, decided count on right.
 * Main row: monospace W-L-P record on left, win rate % with benchmark context on right.
 */
export function RecordCell({ label, rec }: { label: string; rec: Rec }) {
  const rate = winRatePct(rec.win, rec.loss);
  const isAboveBreakEven = rate !== null && rate >= 52.4;

  return (
    <div className="flex flex-col items-stretch justify-center gap-1 rounded-lg border border-line bg-surface-inset p-2 text-center">
      <span className="text-left text-xs font-semibold uppercase tracking-wide text-ink-muted">
        {label}
      </span>
      <div className="flex items-center justify-between gap-1 max-[360px]:flex-col max-[360px]:items-start">
        <div className="font-mono text-base font-bold tracking-tight tabular-nums text-ink sm:text-lg">
          {rec.win}–{rec.loss}–{rec.push}
        </div>
        {rate !== null && (
          <div>
            <span
              className={clsx(
                "inline-flex items-center rounded-full px-1.5 py-0.5 text-xs font-semibold tabular-nums leading-none",
                isAboveBreakEven
                  ? "border border-win-line/60 bg-win-soft text-win"
                  : "text-ink-muted",
              )}
            >
              {rate.toFixed(1)}%
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

/** A titled pair of spread/total records. Always renders both cells, even when empty. */
export function RecordBlock({
  title,
  note,
  spread,
  total,
  showHeader = true,
}: {
  title: string;
  note: string;
  spread: Rec | null;
  total: Rec | null;
  showHeader?: boolean;
}) {
  return (
    <div className="min-w-0">
      {showHeader && (
        <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-2">
          <h3 className="text-xs font-semibold text-ink">{title}</h3>
          <span className="text-xs text-ink-muted">{note}</span>
        </div>
      )}
      <div className="grid grid-cols-2 gap-2">
        <RecordCell label="Spread" rec={spread ?? ZERO} />
        <RecordCell label="Total" rec={total ?? ZERO} />
      </div>
    </div>
  );
}

/** Context for reading the picks: how the model has done so far this season. */
export function ModelRecord({
  performance,
  week,
}: {
  performance: Performance[];
  /** When set (Results), this slate's record is shown beside the season's. */
  week?: { number: number; spread: Rec; total: Rec };
}) {
  const season = performance.find((p) => p.classification === "all");
  const seasonNote = season ? `${season.games} games` : "no games yet";

  if (!week) {
    return (
      <section aria-label="Record" className="rounded-xl border border-line bg-surface-card p-2.5 shadow-2xs">
        <h2 className="mb-2 text-sm font-semibold text-ink">Season record</h2>
        <RecordBlock title="Season" note={seasonNote} spread={season?.spread ?? null} total={season?.total ?? null} showHeader={false} />
      </section>
    );
  }

  const seasonBlock = <RecordBlock title="Season" note={seasonNote} spread={season?.spread ?? null} total={season?.total ?? null} />;

  // One grid for both widths. The heading and the phone "Season context" summary share a row
  // (the summary sits in the heading's cell and opens beneath it); from md the season block
  // takes the second column beside the week.
  return (
    <section aria-label="Record" className="rounded-xl border border-line bg-surface-card p-2.5 shadow-2xs">
      <div className="group/record grid md:grid-cols-2 md:gap-x-3 md:gap-y-2">
        <h2 className="col-start-1 row-start-1 flex flex-wrap items-baseline gap-x-2 self-start py-2 pr-32 text-sm font-semibold text-ink md:col-span-2 md:py-0 md:pr-0">
          Week {week.number} record
          <span className="text-xs font-normal text-ink-muted">this slate · small sample</span>
        </h2>
        <details className="col-start-1 row-start-1 md:hidden">
          <summary className="ml-auto flex min-h-11 w-fit cursor-pointer items-center rounded-lg px-2 text-sm font-semibold text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent">
            Season context
          </summary>
          <div className="pb-3 pt-2 text-ink-muted">{seasonBlock}</div>
        </details>
        <div className="col-start-1 row-start-2 md:col-start-1">
          {/* Phone only, and only while the season block is open above: labels the tiles that would otherwise read as part of it. */}
          <h3 className="mb-1.5 hidden text-xs font-semibold text-ink max-md:group-has-[details[open]]/record:block">
            Week {week.number}
          </h3>
          <RecordBlock title={`Week ${week.number}`} note="" spread={week.spread} total={week.total} showHeader={false} />
        </div>
        <div className="hidden md:col-start-2 md:row-start-2 md:block">{seasonBlock}</div>
      </div>
    </section>
  );
}
