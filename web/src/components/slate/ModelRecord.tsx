import Link from "next/link";
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
  const decided = rec.win + rec.loss;
  const isAboveBreakEven = rate !== null && rate >= 52.4;

  return (
    <div className="rounded-lg border border-line/60 bg-surface-inset/80 p-2.5 transition-colors hover:border-line">
      <div className="flex items-center justify-between text-[11px]">
        <span className="font-semibold uppercase tracking-wider text-ink-muted">
          {label}
        </span>
        <span className="tabular-nums text-ink-faint">
          {decided} decided
        </span>
      </div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="font-mono text-lg font-bold tracking-tight tabular-nums text-ink sm:text-xl">
          {rec.win}–{rec.loss}–{rec.push}
        </span>
        <span
          className={clsx(
            "font-mono text-sm font-semibold tabular-nums",
            rate === null
              ? "text-ink-faint"
              : isAboveBreakEven
              ? "text-win"
              : "text-ink-muted",
          )}
        >
          {rate === null ? "—" : `(${rate.toFixed(1)}%)`}
        </span>
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
          <span className="text-[11px] text-ink-faint">{note}</span>
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
  return (
    <section aria-label="Record" className="rounded-xl border border-line bg-surface-card p-3.5 shadow-2xs">
      <div className="mb-2 flex items-baseline justify-between gap-2">
        <div className="flex flex-wrap items-baseline gap-x-2.5">
          <h2 className="text-xs font-semibold text-ink sm:text-sm">How the model is doing</h2>
          <span className="text-[11px] text-ink-faint">
            Season {season ? `(${season.games} games)` : ""} · 52.4% target
          </span>
        </div>
        <Link
          href="/performance"
          className="text-[11px] font-medium text-accent hover:text-accent-ink hover:underline"
        >
          Full performance →
        </Link>
      </div>
      <div className={clsx("grid gap-3", week && "md:grid-cols-2")}>
        {week && (
          <RecordBlock
            title={`Week ${week.number}`}
            note="this slate · small sample"
            spread={week.spread}
            total={week.total}
            showHeader={true}
          />
        )}
        <RecordBlock
          title="Season"
          note={season ? `${season.games} games` : "no games yet"}
          spread={season?.spread ?? null}
          total={season?.total ?? null}
          showHeader={Boolean(week)}
        />
      </div>
    </section>
  );
}
