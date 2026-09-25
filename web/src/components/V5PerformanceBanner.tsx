import type { Performance } from "@/lib/v5";

type Record = Performance["spread"];

function winRate(record: Record): string {
  const decisions = record.win + record.loss;
  return decisions ? `${((record.win / decisions) * 100).toFixed(1)}%` : "—";
}

function Scoreboard({ label, record }: { label: string; record: Record }) {
  return (
    <div className="rounded-lg bg-surface-inset p-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{label}</p>
      <p className="mt-2 font-mono text-xl text-ink">
        {record.win}–{record.loss}–{record.push}
      </p>
      <p className="mt-1 text-xs text-ink-faint">{winRate(record)} win rate</p>
    </div>
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
