import clsx from "clsx";
import type { Performance } from "@/lib/v5";
import { BAR_RANGE_PTS, BREAK_EVEN_PCT, breakEvenDelta } from "@/lib/picks-proto";

type Rec = { win: number; loss: number; push: number };
const ZERO: Rec = { win: 0, loss: 0, push: 0 };

/**
 * Record, win rate and sample size. With `benchmark`, a bar centered on the
 * break-even rate shows the gap on one fixed scale (+/- BAR_RANGE_PTS), so bars
 * are comparable across records. Without it, no comparison is drawn.
 */
export function RecordCell({
  label,
  rec,
  benchmark,
}: {
  label: string;
  rec: Rec;
  benchmark: boolean;
}) {
  const { rate, delta, fill, decided } = breakEvenDelta(rec.win, rec.loss);
  const caption =
    rate === null || delta === null
      ? "No graded games yet"
      : `${delta >= 0 ? "+" : "−"}${Math.abs(delta).toFixed(1)} pts vs ${BREAK_EVEN_PCT}% break-even`;
  return (
    <div className="rounded-lg bg-surface-inset px-3 py-2.5">
      <div className="flex items-baseline justify-between">
        <span className="text-[10px] font-medium uppercase tracking-wide text-ink-faint">{label}</span>
        <span className="text-xs tabular-nums text-ink-muted">{rate === null ? "—" : `${rate.toFixed(1)}%`}</span>
      </div>
      <div className="mt-0.5 font-mono text-xl font-semibold tabular-nums text-ink">
        {rec.win}–{rec.loss}–{rec.push}
      </div>
      <div className="text-[11px] text-ink-faint">{decided} decided</div>
      {benchmark && (
        <>
          <div role="img" aria-label={`${label}: ${caption}`} className="relative mt-2 h-2 rounded-full bg-line">
            {fill !== 0 && (
              <div
                className={clsx(
                  "absolute inset-y-0",
                  fill > 0 ? "left-1/2 rounded-r-full bg-win" : "right-1/2 rounded-l-full bg-loss",
                )}
                style={{ width: `${Math.abs(fill) * 50}%` }}
              />
            )}
            <div className="absolute -inset-y-1 left-1/2 w-px bg-ink" />
          </div>
          <p className="mt-1 text-center text-[10px] tabular-nums text-ink-faint">{caption}</p>
        </>
      )}
    </div>
  );
}

/** A titled pair of spread/total records. Always renders both cells, even when empty. */
export function RecordBlock({
  title,
  note,
  spread,
  total,
  benchmark,
}: {
  title: string;
  note: string;
  spread: Rec | null;
  total: Rec | null;
  benchmark: boolean;
}) {
  return (
    <div>
      <div className="mb-1.5 flex flex-wrap items-baseline gap-x-2">
        <h3 className="text-xs font-semibold text-ink">{title}</h3>
        <span className="text-[11px] text-ink-faint">{note}</span>
      </div>
      <div className="grid grid-cols-2 gap-2">
        <RecordCell label="Spread" rec={spread ?? ZERO} benchmark={benchmark} />
        <RecordCell label="Total" rec={total ?? ZERO} benchmark={benchmark} />
      </div>
    </div>
  );
}

export const BAR_SCALE_NOTE = `Bars span ±${BAR_RANGE_PTS} points of win rate around the ${BREAK_EVEN_PCT}% break-even line.`;

/** Typical size of the model's misses, from the season summary. */
function missLine(season: Performance | undefined): string | null {
  if (!season || season.marginMae === null || season.totalMae === null) return null;
  return `Average miss: ${season.marginMae.toFixed(1)} pts on the margin, ${season.totalMae.toFixed(1)} on totals.`;
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
  const replayed = (performance.find((p) => p.classification === "replay")?.games ?? 0) > 0;
  const miss = missLine(season);
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
            benchmark={false}
          />
        )}
        <RecordBlock
          title="Season"
          note={season ? `${season.games} games` : "no games yet"}
          spread={season?.spread ?? null}
          total={season?.total ?? null}
          benchmark
        />
      </div>
      <div className="mt-3 space-y-0.5 text-[11px] text-ink-faint">
        {miss && <p>{miss}</p>}
        <p>
          {BAR_SCALE_NOTE}
          {week ? " A single week is not compared to it." : ""}
        </p>
        {replayed && (
          <p>Includes games recalculated after the fact (replays), so read it as a back-test, not the original picks.</p>
        )}
      </div>
    </section>
  );
}
