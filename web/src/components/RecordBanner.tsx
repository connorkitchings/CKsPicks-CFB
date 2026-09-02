import type { Stats } from "@/lib/queries";

function pct(w: number, l: number): string {
  const n = w + l;
  if (n === 0) return "—";
  return `${((100 * w) / n).toFixed(1)}%`;
}

export function RecordBanner({
  season,
  week,
  stats,
}: {
  season: number;
  week: number;
  stats: Stats;
}) {
  const card = (label: string, w: number, l: number, p: number) => {
    return (
      <div className="flex flex-col gap-1 rounded-lg bg-surface-inset p-3">
        <div className="text-[11px] font-medium uppercase tracking-wide text-ink-faint">
          {label}
        </div>
        <div className="font-mono text-2xl font-semibold tabular-nums text-ink">
          {w}–{l}–{p}
        </div>
        <div className="text-xs tabular-nums text-ink-muted">
          {pct(w, l)} hit rate
        </div>
      </div>
    );
  };

  return (
    <section
      aria-label="Season record"
      className="rounded-xl border border-line bg-surface-card p-4 shadow-sm"
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="text-sm font-semibold text-ink">{season} Season Record</h2>
        <p className="text-xs text-ink-faint">
          {stats.asOfWeek === null
            ? `No graded results through Week ${week}`
            : `Through Week ${stats.asOfWeek}`}
        </p>
      </div>
      <div className="mt-3 grid grid-cols-2 gap-3">
        {card("Spreads", stats.spreadWins, stats.spreadLosses, stats.spreadPushes)}
        {card("Totals", stats.totalWins, stats.totalLosses, stats.totalPushes)}
      </div>
    </section>
  );
}
