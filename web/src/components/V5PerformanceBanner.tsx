import type { Performance } from "@/lib/v5";
import { StatCard, winRatePercent } from "./StatCard";

type Record = Performance["spread"];

function Scoreboard({ label, record }: { label: string; record: Record }) {
  return (
    <StatCard
      label={label}
      stat={`${record.win}–${record.loss}–${record.push}`}
      subline={`${winRatePercent(record.win, record.loss)} win rate`}
    />
  );
}

export function V5PerformanceBanner({ performance }: { performance: Performance[] }) {
  const season = performance.find((row) => row.classification === "all");
  if (!season) return null;
  return (
    <section aria-label="2026 so far" className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
      <div className="flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold text-ink">2026 so far</h2>
        <p className="text-xs text-ink-faint">{season.games} games</p>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <Scoreboard label="Spread" record={season.spread} />
        <Scoreboard label="Total" record={season.total} />
      </div>
    </section>
  );
}
