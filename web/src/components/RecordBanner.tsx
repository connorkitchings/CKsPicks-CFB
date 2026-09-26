import type { Stats } from "@/lib/queries";
import { StatCard, winRatePercent } from "./StatCard";

/** Not yet wired into a route — reserved for the season-record display. Do not delete as dead code. */

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
      <StatCard
        label={label}
        stat={`${w}–${l}–${p}`}
        subline={`${winRatePercent(w, l)} hit rate`}
      />
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
