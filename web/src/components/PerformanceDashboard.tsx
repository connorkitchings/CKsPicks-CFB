"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import clsx from "clsx";
import type { PerformanceDetail, GradedGamePick } from "@/lib/v5";
import { accuracyRecord, type AccuracyResult } from "@/lib/performance-accuracy";

type TargetFilter = "all" | "spread" | "total";
type Record3 = ReturnType<typeof accuracyRecord>;

const recordText = (r: Record3) => `${r.win}–${r.loss}–${r.push}`;
const rateText = (r: Record3) => (r.winRate === null ? "—" : `${r.winRate.toFixed(1)}%`);
const decimal = (value: number | null, suffix = "") =>
  value === null ? "—" : `${value.toFixed(1)}${suffix}`;
const graded = (r: Record3) => r.win + r.loss + r.push;

function merge(a: Record3, b: Record3): Record3 {
  const win = a.win + b.win;
  const loss = a.loss + b.loss;
  return { win, loss, push: a.push + b.push, winRate: win + loss ? (100 * win) / (win + loss) : null };
}

function recordFor(games: GradedGamePick[], pick: (g: GradedGamePick) => AccuracyResult) {
  return accuracyRecord(games.map(pick));
}

export function PerformanceDashboard({ data }: { data: PerformanceDetail }) {
  const [targetFilter, setTargetFilter] = useState<TargetFilter>("all");
  const [confidenceOnly, setConfidenceOnly] = useState<boolean>(false);

  const games = useMemo(
    () => data.gradedGames.filter((g) => !confidenceOnly || g.highConfidence),
    [data.gradedGames, confidenceOnly],
  );

  const overall = useMemo(() => {
    const spread = recordFor(games, (g) => g.spreadResult);
    const total = recordFor(games, (g) => g.totalResult);
    const focused =
      targetFilter === "spread" ? spread : targetFilter === "total" ? total : merge(spread, total);
    const label =
      targetFilter === "spread" ? "Spread Accuracy" : targetFilter === "total" ? "Totals Accuracy" : "Overall Accuracy";
    return { spread, total, focused, label };
  }, [games, targetFilter]);

  const weeklyData = useMemo(
    () =>
      data.weeks
        .map((week) => {
          const weekGames = games.filter((g) => g.week === week);
          const spread = recordFor(weekGames, (g) => g.spreadResult);
          const total = recordFor(weekGames, (g) => g.totalResult);
          return { week, spread, total, combined: merge(spread, total) };
        })
        .filter((row) => graded(row.combined) > 0),
    [data.weeks, games],
  );

  const auditGames = useMemo(
    () =>
      games.filter((g) =>
        targetFilter === "spread"
          ? g.spreadResult !== null
          : targetFilter === "total"
            ? g.totalResult !== null
            : g.spreadResult !== null || g.totalResult !== null,
      ),
    [games, targetFilter],
  );

  const cardClass = (active: boolean) =>
    clsx(
      "col-span-1 rounded-xl border p-3 sm:p-5 shadow-sm transition-all text-left cursor-pointer",
      active ? "border-accent ring-1 ring-accent bg-surface-card" : "border-line bg-surface-card hover:border-ink-faint",
    );

  return (
    <div className="space-y-4 sm:space-y-6">
      {/* Accuracy KPI cards: mobile 2+1 grid, desktop 3-col */}
      <section aria-labelledby="kpi-heading" className="grid grid-cols-2 gap-2.5 sm:gap-4 md:grid-cols-3">
        <h2 id="kpi-heading" className="sr-only">Forecast accuracy summary</h2>

        {(["spread", "total"] as const).map((target) => {
          const record = overall[target];
          return (
            <button
              key={target}
              type="button"
              onClick={() => setTargetFilter(targetFilter === target ? "all" : target)}
              className={cardClass(targetFilter === target)}
            >
              <div className="flex items-center justify-between mb-1.5 sm:mb-2">
                <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
                  <span className="sm:hidden">{target === "spread" ? "Spread" : "Totals"}</span>
                  <span className="hidden sm:inline">{target === "spread" ? "Spread Performance" : "Totals Performance"}</span>
                </span>
                {targetFilter === target && (
                  <span className="rounded bg-accent-soft px-1.5 py-0.5 text-[10px] font-semibold text-accent-ink">
                    active
                  </span>
                )}
              </div>
              <div className="font-mono text-2xl sm:text-4xl font-bold tracking-tight text-ink">
                {recordText(record)}
              </div>
              <div className="mt-2 sm:mt-3 space-y-1 text-xs">
                <div className="flex items-center justify-between text-ink-muted">
                  <span>Win Rate</span>
                  <span className="font-mono font-medium text-ink">{rateText(record)}</span>
                </div>
                <div className="flex items-center justify-between text-ink-muted">
                  <span>Graded</span>
                  <span className="font-mono font-medium text-ink">{graded(record)} picks</span>
                </div>
              </div>
            </button>
          );
        })}

        <div className="col-span-2 md:col-span-1 rounded-xl border border-line bg-surface-card p-3 sm:p-5 shadow-sm">
          <div className="flex items-center justify-between mb-1.5 sm:mb-2">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
              {overall.label}
            </span>
            <span className="text-[10px] text-ink-faint font-medium">{graded(overall.focused)} graded</span>
          </div>
          <div className="font-mono text-2xl sm:text-4xl font-bold tracking-tight text-ink">
            {rateText(overall.focused)}
          </div>
          <div className="mt-2 sm:mt-3 space-y-1 text-xs">
            <div className="flex items-center justify-between text-ink-muted">
              <span>Record (W–L–P)</span>
              <span className="font-mono font-medium text-ink">{recordText(overall.focused)}</span>
            </div>
            <div className="flex items-center justify-between text-ink-muted">
              <span>Pushes</span>
              <span className="font-mono font-medium text-ink">excluded from rate</span>
            </div>
          </div>
        </div>
      </section>

      {/* Forecast accuracy strip: season diagnostics, independent of the filters below */}
      <section
        aria-labelledby="calibration-heading"
        className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 sm:gap-2.5 rounded-xl border border-line bg-surface-card px-3 sm:px-4 py-2 sm:py-2.5 shadow-sm text-xs text-ink-muted"
      >
        <h2 id="calibration-heading" className="sr-only">Forecast accuracy</h2>
        <div className="flex items-center gap-1.5 sm:gap-2 flex-wrap">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">
            Forecast Accuracy
          </span>
          <span className="text-ink-faint">·</span>
          <span>
            Spread MAE <strong className="font-mono text-ink">{decimal(data.summary.marginMae, " pts")}</strong>
          </span>
          <span className="text-ink-faint">·</span>
          <span>
            Total MAE <strong className="font-mono text-ink">{decimal(data.summary.totalMae, " pts")}</strong>
          </span>
          <span className="text-ink-faint">·</span>
          <span>
            Spread 95% interval <strong className="font-mono text-ink">{decimal(data.summary.marginCoverage95, "%")}</strong>
          </span>
          <span className="text-ink-faint">·</span>
          <span>
            Total 95% interval <strong className="font-mono text-ink">{decimal(data.summary.totalCoverage95, "%")}</strong>
          </span>
        </div>
        <div className="text-[11px] text-ink-faint">
          Forecasts compared with certified final scores
        </div>
      </section>

      {/* Filter toolbar */}
      <section aria-labelledby="filter-heading" className="flex flex-wrap items-center justify-between gap-2.5 sm:gap-3 rounded-xl border border-line bg-surface-card p-3 sm:p-4 shadow-sm">
        <h2 id="filter-heading" className="sr-only">Dashboard filters</h2>

        <div className="inline-flex rounded-lg bg-surface-inset p-1" role="tablist" aria-label="Pick target">
          {(["all", "spread", "total"] as const).map((t) => {
            const label = t === "all" ? "All Picks" : t === "spread" ? "Spreads" : "Totals";
            return (
              <button
                key={t}
                type="button"
                role="tab"
                aria-selected={targetFilter === t}
                onClick={() => setTargetFilter(t)}
                className={clsx(
                  "rounded-md px-3 sm:px-3.5 py-1 text-xs font-medium transition-colors",
                  targetFilter === t ? "bg-surface-card text-ink shadow-sm" : "text-ink-muted hover:text-ink",
                )}
              >
                {label}
              </button>
            );
          })}
        </div>

        <button
          type="button"
          onClick={() => setConfidenceOnly(!confidenceOnly)}
          aria-pressed={confidenceOnly}
          className={clsx(
            "flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors",
            confidenceOnly
              ? "border-accent bg-accent-soft text-accent-ink"
              : "border-line bg-surface-inset text-ink-muted hover:text-ink",
          )}
        >
          <span className={confidenceOnly ? "text-accent" : "text-ink-faint"}>★</span>
          High Confidence Only
        </button>
      </section>

      {/* Weekly breakdown: mobile cards and desktop table */}
      <section aria-labelledby="weekly-heading" className="rounded-xl border border-line bg-surface-card overflow-hidden shadow-sm">
        <h2 id="weekly-heading" className="sr-only">Weekly accuracy breakdown</h2>

        <div className="sm:hidden divide-y divide-line">
          {weeklyData.map((row) => (
            <div key={row.week} className="p-3.5 space-y-2">
              <div className="flex items-center justify-between">
                <Link
                  href={`/results?week=${row.week}`}
                  className="inline-flex items-center gap-1 text-sm font-bold text-ink hover:text-accent-ink"
                  title={`View Week ${row.week} results slate`}
                >
                  <span>Week {row.week}</span>
                  <span className="text-ink-faint text-xs">→</span>
                </Link>
                <span className="font-mono text-xs text-ink-muted">
                  {rateText(targetFilter === "spread" ? row.spread : targetFilter === "total" ? row.total : row.combined)}
                </span>
              </div>
              {targetFilter === "all" ? (
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {([["Spread", row.spread], ["Totals", row.total]] as const).map(([label, rec]) => (
                    <div key={label} className="bg-surface-inset rounded-lg p-2 space-y-0.5">
                      <div className="text-[10px] uppercase font-semibold text-ink-faint">{label}</div>
                      <div className="flex items-center justify-between font-mono">
                        <span className="text-ink font-medium">{recordText(rec)}</span>
                        <span className="text-ink-muted">{rateText(rec)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex items-center justify-between text-xs text-ink-muted bg-surface-inset rounded-lg px-2.5 py-1.5">
                  <span>Record: <strong className="text-ink font-mono">{recordText(targetFilter === "spread" ? row.spread : row.total)}</strong></span>
                  <span>Win Rate: <strong className="text-ink font-mono">{rateText(targetFilter === "spread" ? row.spread : row.total)}</strong></span>
                </div>
              )}
            </div>
          ))}
          <div className="p-3.5 bg-surface-inset/80 space-y-2 border-t-2 border-line">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold uppercase tracking-wider text-ink">Season Total</span>
              <span className="font-mono text-sm font-bold text-ink">{rateText(overall.focused)}</span>
            </div>
            <div className="flex items-center justify-between text-xs text-ink-muted">
              {targetFilter === "all" ? (
                <>
                  <span>Spread: <strong className="text-ink font-mono">{recordText(overall.spread)}</strong></span>
                  <span>Total: <strong className="text-ink font-mono">{recordText(overall.total)}</strong></span>
                </>
              ) : (
                <>
                  <span>Record: <strong className="text-ink font-mono">{recordText(overall.focused)}</strong></span>
                  <span>Win Rate: <strong className="text-ink font-mono">{rateText(overall.focused)}</strong></span>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="hidden sm:block overflow-x-auto">
          <table className="w-full min-w-[560px] text-xs tabular-nums text-left">
            <thead className="border-b border-line bg-surface-inset text-[11px] uppercase tracking-wider text-ink-faint font-semibold">
              <tr>
                <th scope="col" className="px-4 py-3">Week</th>
                {targetFilter !== "total" && (
                  <>
                    <th scope="col" className="px-3 py-3 text-right">Spread (W-L-P)</th>
                    <th scope="col" className="px-3 py-3 text-right">Spread Win Rate</th>
                  </>
                )}
                {targetFilter !== "spread" && (
                  <>
                    <th scope="col" className="px-3 py-3 text-right">Total (W-L-P)</th>
                    <th scope="col" className="px-4 py-3 text-right">Total Win Rate</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {weeklyData.map((row) => (
                <tr key={row.week} className="hover:bg-surface-inset/50 transition-colors">
                  <td className="px-4 py-3 font-semibold text-ink">
                    <Link
                      href={`/results?week=${row.week}`}
                      className="hover:text-accent-ink hover:underline"
                      title={`View Week ${row.week} results slate`}
                    >
                      Week {row.week}
                    </Link>
                  </td>
                  {targetFilter !== "total" && (
                    <>
                      <td className="px-3 py-3 text-right text-ink">{recordText(row.spread)}</td>
                      <td className="px-3 py-3 text-right text-ink">{rateText(row.spread)}</td>
                    </>
                  )}
                  {targetFilter !== "spread" && (
                    <>
                      <td className="px-3 py-3 text-right text-ink">{recordText(row.total)}</td>
                      <td className="px-4 py-3 text-right text-ink">{rateText(row.total)}</td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
            <tfoot className="border-t-2 border-line bg-surface-inset font-semibold text-ink">
              <tr>
                <td className="px-4 py-3">Season Total</td>
                {targetFilter !== "total" && (
                  <>
                    <td className="px-3 py-3 text-right">{recordText(overall.spread)}</td>
                    <td className="px-3 py-3 text-right font-mono">{rateText(overall.spread)}</td>
                  </>
                )}
                {targetFilter !== "spread" && (
                  <>
                    <td className="px-3 py-3 text-right">{recordText(overall.total)}</td>
                    <td className="px-4 py-3 text-right font-mono">{rateText(overall.total)}</td>
                  </>
                )}
              </tr>
            </tfoot>
          </table>
        </div>
      </section>

      {/* Graded picks audit: captured line, stored lean, grade and price provenance */}
      <section aria-labelledby="audit-heading" className="space-y-3">
        <h2 id="audit-heading" className="text-sm font-semibold text-ink">Graded picks audit</h2>
        <p className="text-xs text-ink-muted">
          Grades use the captured selected line. Replays are retrospective evidence. Price source is an audit fact;
          accuracy does not assume a payout.
        </p>
        {auditGames.length === 0 && <p role="status" className="text-xs text-ink-muted">No graded picks match these filters.</p>}
        <div className="grid gap-2.5 sm:grid-cols-2">
          {auditGames.map((game) => (
            <article key={game.gameId} className="rounded-xl border border-line bg-surface-card p-3 sm:p-4 shadow-sm">
              <Link className="text-sm font-semibold text-ink hover:text-accent-ink" href={`/matchup/${game.gameId}`}>
                {game.awayTeam} @ {game.homeTeam}
              </Link>
              <p className="mt-1 text-[11px] text-ink-faint">
                Week {game.week} · {game.evidenceClass === "replay" ? "Retrospective replay" : "Prospective"} · Final {game.awayPoints ?? "—"}–{game.homePoints ?? "—"}
              </p>
              <dl className="mt-2 space-y-2 text-xs">
                {targetFilter !== "total" && game.spreadResult !== null && (
                  <div>
                    <dt className="text-ink-muted">Spread · captured line {decimal(game.marketSpread)}</dt>
                    <dd className="text-ink">Forecast {decimal(game.predictedSpread)} · {game.spreadLean ?? "No stored lean"} · {game.spreadResult}</dd>
                    <dd className="text-ink-faint">Price: {game.spreadPriceProvenance ?? "unavailable"}</dd>
                  </div>
                )}
                {targetFilter !== "spread" && game.totalResult !== null && (
                  <div>
                    <dt className="text-ink-muted">Total · captured line {decimal(game.marketTotal)}</dt>
                    <dd className="text-ink">Forecast {decimal(game.predictedTotal)} · {game.totalLean ?? "No stored lean"} · {game.totalResult}</dd>
                    <dd className="text-ink-faint">Price: {game.totalPriceProvenance ?? "unavailable"}</dd>
                  </div>
                )}
              </dl>
            </article>
          ))}
        </div>
      </section>

      <p className="text-xs text-ink-muted">
        Click any week above to view the full game-by-game results and graded picks on the Results tab.
      </p>
    </div>
  );
}
