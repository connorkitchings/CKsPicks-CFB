import clsx from "clsx";
import type { Performance } from "@/lib/v5";
import { winRatePct } from "@/lib/slate";

type Rec = { win: number; loss: number; push: number };
const ZERO: Rec = { win: 0, loss: 0, push: 0 };

/**
 * Record, win rate and sample size, all centered: the label shares the top
 * row with the decided count, the W-L record sits in the middle, and the win
 * rate (pushes excluded) sits under it.
 */
export function RecordCell({ label, rec }: { label: string; rec: Rec }) {
  const rate = winRatePct(rec.win, rec.loss);
  const decided = rec.win + rec.loss;
  return (
    <div className="rounded-lg bg-surface-inset px-3 py-2.5 text-center">
      <div className="flex items-baseline gap-2">
        <span className="flex-1 text-center text-[10px] font-medium uppercase tracking-wide text-ink-faint">
          {label}
        </span>
        <span className="shrink-0 text-[11px] tabular-nums text-ink-faint">
          {decided} decided
        </span>
      </div>
      <div className="mt-0.5 font-mono text-xl font-semibold tabular-nums text-ink">
        {rec.win}–{rec.loss}–{rec.push}
      </div>
      <div className="text-xs tabular-nums text-ink-muted">
        {rate === null ? "No graded games yet" : `${rate.toFixed(1)}%`}
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
}: {
  title: string;
  note: string;
  spread: Rec | null;
  total: Rec | null;
}) {
  return (
    <div>
      <div className="mb-1.5 flex flex-wrap items-baseline gap-x-2">
        <h3 className="text-xs font-semibold text-ink">{title}</h3>
        <span className="text-[11px] text-ink-faint">{note}</span>
      </div>
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
    <section aria-label="Record" className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
      <h2 className="mb-2 text-sm font-semibold text-ink">How the model is doing</h2>
      <div className={clsx("grid gap-4", week && "md:grid-cols-2")}>
        {week && (
          <RecordBlock
            title={`Week ${week.number}`}
            note="this slate · small sample"
            spread={week.spread}
            total={week.total}
          />
        )}
        <RecordBlock
          title="Season"
          note={season ? `${season.games} games` : "no games yet"}
          spread={season?.spread ?? null}
          total={season?.total ?? null}
        />
      </div>
    </section>
  );
}
