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
          <div
            role="img"
            aria-label={`${label}: ${caption}`}
            className="relative mt-2 h-2 rounded-full bg-line"
          >
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

/** Season records (live vs replay), compared to break-even. Same blocks on Picks and Results. */
export function ProtoRecord({ performance }: { performance: Performance[] }) {
  const live = performance.find((p) => p.classification === "live");
  const replay = performance.find((p) => p.classification === "replay");
  return (
    <section aria-label="Record" className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
      <div className="grid gap-4 md:grid-cols-2">
        <RecordBlock title="Season · Live" note="frozen before kickoff" spread={live?.spread ?? null} total={live?.total ?? null} benchmark />
        <RecordBlock title="Season · Replay" note="recalculated after the games" spread={replay?.spread ?? null} total={replay?.total ?? null} benchmark />
      </div>
      <p className="mt-3 text-[11px] text-ink-faint">{BAR_SCALE_NOTE}</p>
    </section>
  );
}
