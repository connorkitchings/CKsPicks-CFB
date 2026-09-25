import type { Performance } from "@/lib/v5";

export function V5PerformanceBanner({ performance }: { performance: Performance[] }) {
  // Classifications with no picks yet (e.g. live before the first live
  // slate) carry no signal; the detailed performance page still lists them.
  const rows = performance.filter((row) => row.games > 0);
  const replay = rows.find((row) => row.classification === "replay");
  const live = rows.find((row) => row.classification === "live");
  if (!replay && !live) return null;
  return <section aria-label="V5 season performance" className="grid gap-3 sm:grid-cols-2">
    {[replay, live].filter((row): row is Performance => Boolean(row)).map((row) =>
      <div key={row.classification} className="rounded-xl border border-line bg-surface-card p-4 shadow-sm"><h2 className="text-sm font-semibold capitalize text-ink">{row.classification} forecasts</h2><p className="mt-1 text-xs text-ink-faint">{row.games} selected games</p><p className="mt-3 font-mono text-xl text-ink">{row.marginMae === null ? "—" : row.marginMae.toFixed(1)} <span className="text-xs font-sans text-ink-faint">margin MAE</span></p><p className="text-xs text-ink-muted">Spread grades: {row.spread.win}–{row.spread.loss}–{row.spread.push}</p></div>
    )}
  </section>;
}
