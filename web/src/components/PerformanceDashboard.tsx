"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import clsx from "clsx";
import type { PerformanceDetail, GradedGamePick } from "@/lib/v5";
import { accuracyRecord, type AccuracyResult } from "@/lib/performance-accuracy";
import { Disclosure } from "@/components/ui/Disclosure";
import { ResponsiveDisclosure } from "@/components/ui/ResponsiveDisclosure";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { MatchupButton } from "@/components/MatchupLinks";

type TargetFilter = "all" | "spread" | "total";
type Record3 = ReturnType<typeof accuracyRecord>;
const recordText = (record: Record3) => `${record.win}–${record.loss}–${record.push}`;
const rateText = (record: Record3) => record.winRate === null ? "—" : `${record.winRate.toFixed(1)}%`;
const decimal = (value: number | null, suffix = "") => value === null ? "—" : `${value.toFixed(1)}${suffix}`;
const graded = (record: Record3) => record.win + record.loss + record.push;

function merge(a: Record3, b: Record3): Record3 {
  const win = a.win + b.win;
  const loss = a.loss + b.loss;
  return { win, loss, push: a.push + b.push, winRate: win + loss ? (100 * win) / (win + loss) : null };
}

function recordFor(games: GradedGamePick[], pick: (game: GradedGamePick) => AccuracyResult) {
  return accuracyRecord(games.map(pick));
}

function AuditGame({ game, target }: { game: GradedGamePick; target: TargetFilter }) {
  return (
    <article data-testid="audit-game" data-game-id={game.gameId}>
      <Disclosure title={<span className="break-words">{game.awayTeam} @ {game.homeTeam}</span>}>
        <p className="mb-2 text-xs">Week {game.week} · V5 · Final {game.awayPoints ?? "—"}–{game.homePoints ?? "—"}</p>
        <MatchupButton gameId={game.gameId} />
        <p className="mt-2 break-words text-xs">Original run: <code className="break-all">{game.runId}</code></p>
        {game.freezeReceiptSha256 && (
          <p className="mt-1 text-xs">Freeze evidence SHA-256: <code className="break-all">{game.freezeReceiptSha256}</code></p>
        )}
        <dl className="mt-3 space-y-3 text-sm">
          {target !== "total" && game.spreadResult !== null && (
            <div>
              <dt className="font-semibold text-ink">Spread · captured line {decimal(game.marketSpread)}</dt>
              <dd>Forecast {decimal(game.predictedSpread)} · {game.spreadLean ?? "No stored lean"} · {game.spreadResult}</dd>
              <dd className="mt-1 text-xs">Price: {game.spreadPriceProvenance ?? "unavailable"}</dd>
            </div>
          )}
          {target !== "spread" && game.totalResult !== null && (
            <div>
              <dt className="font-semibold text-ink">Total · captured line {decimal(game.marketTotal)}</dt>
              <dd>Forecast {decimal(game.predictedTotal)} · {game.totalLean ?? "No stored lean"} · {game.totalResult}</dd>
              <dd className="mt-1 text-xs">Price: {game.totalPriceProvenance ?? "unavailable"}</dd>
            </div>
          )}
        </dl>
      </Disclosure>
    </article>
  );
}

export function PerformanceDashboard({ data, title }: { data: PerformanceDetail; title: string }) {
  const [targetFilter, setTargetFilter] = useState<TargetFilter>("all");
  const games = data.gradedGames;
  const auditWeeks = useMemo(
    () => [...new Set(games.filter((game) => game.spreadResult !== null || game.totalResult !== null).map((game) => game.week))].sort((a, b) => b - a),
    [games],
  );
  // Target changes do not alter the chosen week, including a week empty for that target.
  const [auditWeek, setAuditWeek] = useState(() => auditWeeks[0] ?? null);

  const overall = useMemo(() => {
    const spread = recordFor(games, (game) => game.spreadResult);
    const total = recordFor(games, (game) => game.totalResult);
    const focused = targetFilter === "spread" ? spread : targetFilter === "total" ? total : merge(spread, total);
    const label = targetFilter === "spread" ? "Spread Accuracy" : targetFilter === "total" ? "Totals Accuracy" : "Overall Accuracy";
    return { spread, total, focused, label };
  }, [games, targetFilter]);

  const weeklyData = useMemo(
    () => data.weeks.map((week) => {
      const weekGames = games.filter((game) => game.week === week);
      const spread = recordFor(weekGames, (game) => game.spreadResult);
      const total = recordFor(weekGames, (game) => game.totalResult);
      return { week, spread, total, combined: merge(spread, total) };
    }).filter((row) => graded(row.combined) > 0),
    [data.weeks, games],
  );

  const auditGames = useMemo(
    () => games.filter((game) => game.week === auditWeek && (
      targetFilter === "spread" ? game.spreadResult !== null : targetFilter === "total" ? game.totalResult !== null : game.spreadResult !== null || game.totalResult !== null
    )),
    [games, auditWeek, targetFilter],
  );

  return (
    <div className="space-y-4 sm:space-y-6">
      <h2 className="text-lg font-semibold text-ink">{title}</h2>
      <section aria-labelledby="kpi-heading" className="grid grid-cols-2 gap-2.5 sm:gap-4">
        <h2 id="kpi-heading" className="sr-only">Forecast accuracy summary</h2>
        {(["spread", "total"] as const).map((target) => {
          const record = overall[target];
          return (
            <button
              key={target}
              type="button"
              aria-pressed={targetFilter === target}
              onClick={() => setTargetFilter(targetFilter === target ? "all" : target)}
              className={clsx(
                "min-h-11 min-w-0 rounded-xl border bg-surface-card p-3 text-left shadow-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent sm:p-5",
                targetFilter === target ? "border-accent ring-1 ring-accent" : "border-line hover:border-line-strong",
              )}
            >
              <span className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{target === "spread" ? "Spread" : "Totals"}</span>
              <span className="mt-2 block font-mono text-xl font-bold tracking-tight text-ink sm:text-4xl">{recordText(record)}</span>
              <span className="mt-2 flex flex-wrap justify-between gap-1 text-sm text-ink-muted">
                <span>Win rate</span><strong className="font-mono text-ink">{rateText(record)}</strong>
              </span>
              <span className="mt-1 block text-xs text-ink-muted">{graded(record)} graded picks</span>
            </button>
          );
        })}
      </section>

      <ResponsiveDisclosure className="rounded-xl border border-line bg-surface-card" title="Season-wide forecast diagnostics" heading="Season-wide forecast diagnostics">
        <section aria-labelledby="calibration-heading" className="space-y-3">
          <h2 id="calibration-heading" className="sr-only">Forecast accuracy</h2>
          <p className="text-sm">Season-wide forecasts compared with certified final scores; these diagnostics do not change with the target filter.</p>
          <dl className="grid gap-3 sm:grid-cols-2">
            {([
              ["Spread MAE", decimal(data.summary.marginMae, " pts")],
              ["Total MAE", decimal(data.summary.totalMae, " pts")],
              ["Spread 95% interval", decimal(data.summary.marginCoverage95, "%")],
              ["Total 95% interval", decimal(data.summary.totalCoverage95, "%")],
            ] as const).map(([label, value]) => (
              <div key={label}><dt>{label}</dt><dd className="font-mono font-semibold text-ink">{value}</dd></div>
            ))}
          </dl>
        </section>
      </ResponsiveDisclosure>

      <section aria-labelledby="filter-heading" className="space-y-2">
        <h2 id="filter-heading" className="text-sm font-semibold text-ink">Weekly records</h2>
        <SegmentedControl<TargetFilter>
          label="Pick target"
          value={targetFilter}
          onChange={setTargetFilter}
          options={[{ value: "all", label: "All Picks" }, { value: "spread", label: "Spreads" }, { value: "total", label: "Totals" }]}
          fill
          className="sm:w-fit"
        />
        <p className="text-xs text-ink-muted">{overall.label}: {recordText(overall.focused)} · {rateText(overall.focused)} · {graded(overall.focused)} graded. Pushes excluded from rate.</p>
      </section>

      <section aria-labelledby="weekly-heading" className="overflow-hidden rounded-xl border border-line bg-surface-card shadow-sm">
        <h2 id="weekly-heading" className="sr-only">Weekly accuracy breakdown</h2>
        <div className="divide-y divide-line sm:hidden">
          {weeklyData.map((row) => (
            <div key={row.week} className="space-y-2 p-3">
              <Link href={`/results?week=${row.week}`} className="inline-flex min-h-11 items-center gap-2 rounded text-sm font-bold text-ink hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-accent">
                Week {row.week} <span aria-hidden>→</span>
              </Link>
              <div className={clsx("grid gap-2", targetFilter === "all" && "grid-cols-2")}>
                {(["spread", "total"] as const).filter((target) => targetFilter === "all" || targetFilter === target).map((target) => (
                  <div key={target} className="rounded-lg bg-surface-inset p-2">
                    <p className="text-xs font-semibold text-ink-muted">{target === "spread" ? "Spread" : "Total"}</p>
                    <p className="mt-1 flex flex-wrap justify-between gap-1 font-mono text-sm text-ink">
                      <span>{recordText(row[target])}</span><span>{rateText(row[target])}</span>
                    </p>
                  </div>
                ))}
              </div>
            </div>
          ))}
          <div className="space-y-1 border-t-2 border-line bg-surface-inset p-3 text-sm text-ink-muted">
            <p className="font-semibold text-ink">Season Total</p>
            <p>{targetFilter === "all" ? `Spread: ${recordText(overall.spread)} · Total: ${recordText(overall.total)}` : `Record: ${recordText(overall.focused)}`}</p>
            <p>Win rate: {rateText(overall.focused)}</p>
          </div>
        </div>
        <div className="hidden sm:block">
          <table className="w-full text-left text-sm tabular-nums">
            <thead className="border-b border-line bg-surface-inset text-xs text-ink-muted">
              <tr>
                <th scope="col" className="px-3 py-3">Week</th>
                {targetFilter !== "total" && <><th scope="col" className="px-2 py-3 text-right">Spread (W-L-P)</th><th scope="col" className="px-2 py-3 text-right">Spread Win Rate</th></>}
                {targetFilter !== "spread" && <><th scope="col" className="px-2 py-3 text-right">Total (W-L-P)</th><th scope="col" className="px-3 py-3 text-right">Total Win Rate</th></>}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {weeklyData.map((row) => (
                <tr key={row.week}>
                  <th scope="row" className="px-3 text-ink">
                    <Link href={`/results?week=${row.week}`} className="inline-flex min-h-11 items-center rounded font-semibold sm:min-h-9 hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-accent">Week {row.week}</Link>
                  </th>
                  {targetFilter !== "total" && <><td className="px-2 py-3 text-right">{recordText(row.spread)}</td><td className="px-2 py-3 text-right">{rateText(row.spread)}</td></>}
                  {targetFilter !== "spread" && <><td className="px-2 py-3 text-right">{recordText(row.total)}</td><td className="px-3 py-3 text-right">{rateText(row.total)}</td></>}
                </tr>
              ))}
            </tbody>
            <tfoot className="border-t-2 border-line bg-surface-inset font-semibold text-ink">
              <tr>
                <th scope="row" className="px-3 py-3">Season Total</th>
                {targetFilter !== "total" && <><td className="px-2 py-3 text-right">{recordText(overall.spread)}</td><td className="px-2 py-3 text-right">{rateText(overall.spread)}</td></>}
                {targetFilter !== "spread" && <><td className="px-2 py-3 text-right">{recordText(overall.total)}</td><td className="px-3 py-3 text-right">{rateText(overall.total)}</td></>}
              </tr>
            </tfoot>
          </table>
        </div>
      </section>

      <section aria-label="Graded picks audit">
        <Disclosure title="Graded picks audit">
          <p className="mb-3 text-xs">Grades use the captured selected line. Price source is an audit fact; accuracy does not assume a payout.</p>
          <label htmlFor="audit-week" className="mb-1 block text-sm font-medium text-ink">Audit week</label>
          <select
            id="audit-week"
            name="audit-week"
            value={auditWeek ?? ""}
            onChange={(event) => setAuditWeek(Number(event.target.value))}
            className="mb-3 min-h-11 w-full rounded-lg border border-line bg-surface-card px-3 text-base text-ink focus-visible:outline-2 focus-visible:outline-accent sm:w-auto sm:text-sm"
          >
            {auditWeeks.map((week) => <option key={week} value={week}>Week {week}</option>)}
          </select>
          {auditGames.length === 0 ? (
            <p role="status" className="text-sm">No graded {targetFilter === "all" ? "picks" : targetFilter === "spread" ? "spreads" : "totals"} in Week {auditWeek}.</p>
          ) : (
            <div className="grid gap-3 sm:grid-cols-2">
              {auditGames.map((game) => <AuditGame key={game.gameId} game={game} target={targetFilter} />)}
            </div>
          )}
        </Disclosure>
      </section>
      <p className="text-xs text-ink-muted">Select any week above to view its full game-by-game results and graded picks on the Results tab.</p>
    </div>
  );
}
