import type { HistoricalModelContext as Context } from "@/lib/queries";

function pct(wins: number, losses: number): string {
  const denominator = wins + losses;
  return denominator === 0 ? "—" : `${((100 * wins) / denominator).toFixed(1)}%`;
}

function target(label: string, wins: number, losses: number, pushes: number) {
  return (
    <div className="rounded-lg bg-surface-inset p-3">
      <div className="text-[11px] font-medium uppercase tracking-wide text-ink-faint">{label}</div>
      <div className="font-mono text-xl font-semibold tabular-nums text-ink">{pct(wins, losses)}</div>
      <div className="text-xs tabular-nums text-ink-muted">{wins}–{losses}–{pushes}</div>
    </div>
  );
}

export function HistoricalModelContext({ context, selectedWeek }: { context: Context; selectedWeek: number }) {
  const period = context.matchingWeek;
  return (
    <section aria-label="Retrospective model context" className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h2 className="text-sm font-semibold text-ink">{context.fullSeason.comparisonSeason} Retrospective Model Context</h2>
        <p className="text-xs text-ink-faint">Diagnostic-only historical comparison</p>
      </div>
      <div className="mt-3 grid gap-4 md:grid-cols-2">
        <div>
          <h3 className="mb-2 text-xs font-medium text-ink-muted">Full season</h3>
          <div className="grid grid-cols-2 gap-3">
            {target("Spreads", context.fullSeason.spreadWins, context.fullSeason.spreadLosses, context.fullSeason.spreadPushes)}
            {target("Totals", context.fullSeason.totalWins, context.fullSeason.totalLosses, context.fullSeason.totalPushes)}
          </div>
        </div>
        <div>
          <h3 className="mb-2 text-xs font-medium text-ink-muted">Matching Week {selectedWeek}</h3>
          {period ? <div className="grid grid-cols-2 gap-3">
            {target("Spreads", period.spreadWins, period.spreadLosses, period.spreadPushes)}
            {target("Totals", period.totalWins, period.totalLosses, period.totalPushes)}
          </div> : <div className="rounded-lg bg-surface-inset p-3 text-sm text-ink-muted">No {context.fullSeason.comparisonSeason} Week {selectedWeek} comparison.</div>}
        </div>
      </div>
      <p className="mt-3 text-xs text-ink-faint">Uses reconstructed historical reference lines captured after the season; diagnostic context, not an official pregame betting record.</p>
    </section>
  );
}
