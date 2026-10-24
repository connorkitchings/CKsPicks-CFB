"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import clsx from "clsx";
import type { PerformanceSummary } from "@/lib/v5";
import { accuracyRecord, type AccuracyResult } from "@/lib/performance-accuracy";
import { BREAK_EVEN_PCT } from "@/lib/betting-format";
import { Card } from "@/components/ui/Card";
import { ResponsiveDisclosure } from "@/components/ui/ResponsiveDisclosure";
import { SummaryLine } from "@/components/ui/SummaryLine";
import { SegmentedControl } from "@/components/ui/SegmentedControl";

/** Only what the dashboard renders; the per-game audit facts stay server-side. */
export interface GradedResult {
  week: number;
  spreadResult: AccuracyResult;
  totalResult: AccuracyResult;
}
export interface PerformanceView {
  summary: PerformanceSummary;
  weeks: number[];
  gradedGames: GradedResult[];
}

type TargetFilter = "all" | "spread" | "total";
type Record3 = ReturnType<typeof accuracyRecord>;
const recordText = (record: Record3) => `${record.win}–${record.loss}–${record.push}`;
const rateText = (record: Record3) => record.winRate === null ? "—" : `${record.winRate.toFixed(1)}%`;
const decimal = (value: number | null, suffix = "") => value === null ? "—" : `${value.toFixed(1)}${suffix}`;
const graded = (record: Record3) => record.win + record.loss + record.push;
const breakEvenText = (record: Record3) => {
  if (record.winRate === null) return `${BREAK_EVEN_PCT}% break-even`;
  const delta = record.winRate - BREAK_EVEN_PCT;
  return `${delta >= 0 ? "+" : ""}${delta.toFixed(1)} pp vs ${BREAK_EVEN_PCT}% break-even`;
};

function merge(a: Record3, b: Record3): Record3 {
  const win = a.win + b.win;
  const loss = a.loss + b.loss;
  return { win, loss, push: a.push + b.push, winRate: win + loss ? (100 * win) / (win + loss) : null };
}

function recordFor(games: GradedResult[], pick: (game: GradedResult) => AccuracyResult) {
  return accuracyRecord(games.map(pick));
}

export function PerformanceDashboard({ data, title }: { data: PerformanceView; title: string }) {
  const [targetFilter, setTargetFilter] = useState<TargetFilter>("all");
  const games = data.gradedGames;
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

  return (
    <div className="space-y-2 sm:space-y-6">
      <SummaryLine
        parts={["2026 · V5", `${weeklyData.length} graded ${weeklyData.length === 1 ? "week" : "weeks"}`]}
        className="text-xs text-ink-muted sm:hidden"
        data-testid="model-summary"
      />
      <h2 className="text-lg font-semibold text-ink max-sm:sr-only">{title}</h2>
      <section aria-labelledby="kpi-heading" className="grid grid-cols-2 gap-2.5 sm:gap-4">
        <h2 id="kpi-heading" className="sr-only">Forecast accuracy summary</h2>
        {(["spread", "total"] as const).map((target) => {
          const record = overall[target];
          return (
            <button
              key={target}
              type="button"
              aria-pressed={targetFilter === target}
              data-card=""
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
              <span className="mt-1 flex flex-wrap justify-between gap-1 text-xs text-ink-muted">
                <span>{graded(record)} graded picks</span>
                <span className="font-mono">{breakEvenText(record)}</span>
              </span>
            </button>
          );
        })}
      </section>

      <ResponsiveDisclosure title="Season-wide forecast diagnostics" heading="Season-wide forecast diagnostics">
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
          className="max-sm:hidden sm:w-fit"
        />
        <p className="text-xs text-ink-muted">{overall.label}: {recordText(overall.focused)} · {rateText(overall.focused)} ({BREAK_EVEN_PCT}% break-even) · {graded(overall.focused)} graded. Pushes excluded from rate.</p>
      </section>

      <Card as="section" padding="none" aria-labelledby="weekly-heading" className="overflow-hidden">
        <h2 id="weekly-heading" className="sr-only">Weekly accuracy breakdown</h2>
        <div className="divide-y divide-line sm:hidden">
          {weeklyData.map((row) => (
            <div key={row.week} className="space-y-2 p-3">
              <Link href={`/?week=${row.week}`} className="inline-flex min-h-11 items-center gap-2 rounded text-sm font-bold text-ink hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-accent">
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
                    <Link href={`/?week=${row.week}`} className="inline-flex min-h-11 items-center rounded font-semibold sm:min-h-9 hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-accent">Week {row.week}</Link>
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
      </Card>

      <p className="text-xs text-ink-muted max-sm:hidden">Select any week above to view its full game-by-game results and graded picks on the Games tab.</p>
    </div>
  );
}
