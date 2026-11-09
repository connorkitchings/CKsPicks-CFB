"use client";

import Link from "next/link";
import { useMemo } from "react";
import clsx from "clsx";
import type { PerformanceSummary, WeekPerformanceRow } from "@/lib/v5";
import { accuracyRecord, type AccuracyResult } from "@/lib/performance-accuracy";
import { BIG_MISS_POINTS, type LineSourceCounts, type MarketComparison, type MarketTarget } from "@/lib/performance-market";
import { breakEvenCaveat, type TrendWeek } from "@/lib/performance-trend";
import { BREAK_EVEN_PCT } from "@/lib/betting-format";
import { Card } from "@/components/ui/Card";
import { ResponsiveDisclosure } from "@/components/ui/ResponsiveDisclosure";
import { SummaryLine } from "@/components/ui/SummaryLine";
import { RecordTrendChart } from "@/components/model/RecordTrendChart";

/** Only what the dashboard renders; the per-game audit facts stay server-side. */
export interface GradedResult {
  week: number;
  spreadResult: AccuracyResult;
  totalResult: AccuracyResult;
}

/** One target's model-versus-line facts, computed on the server. */
export interface MarketView {
  comparison: MarketComparison | null;
  counts: LineSourceCounts;
}

export interface PerformanceView {
  summary: PerformanceSummary;
  weeks: number[];
  gradedGames: GradedResult[];
  weekRows: WeekPerformanceRow[];
  trend: TrendWeek[];
  market: Record<MarketTarget, MarketView>;
}

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
const plural = (n: number, noun: string) => `${n} ${noun}${n === 1 ? "" : "s"}`;

const TARGET_LABEL: Record<MarketTarget, string> = { spread: "Spread", total: "Totals" };

/** Mean signed error in words: spread leans toward a team, totals lean high or low. */
function leanText(target: MarketTarget, lean: number): string {
  const size = Math.abs(lean);
  if (size < 0.05) return "no lean";
  if (target === "spread") return `${size.toFixed(1)} pts toward the ${lean < 0 ? "away" : "home"} team`;
  return `${size.toFixed(1)} pts ${lean > 0 ? "high" : "low"}`;
}

function merge(a: Record3, b: Record3): Record3 {
  const win = a.win + b.win;
  const loss = a.loss + b.loss;
  return { win, loss, push: a.push + b.push, winRate: win + loss ? (100 * win) / (win + loss) : null };
}

function recordFor(games: GradedResult[], pick: (game: GradedResult) => AccuracyResult) {
  return accuracyRecord(games.map(pick));
}

function ComparisonCard({ target, view }: { target: MarketTarget; view: MarketView }) {
  const { comparison: c, counts } = view;
  const left = counts.retrospective + counts.unknown;
  return (
    <Card as="article" padding="sm" className="min-w-0 space-y-2 sm:p-4" data-testid={`market-${target}`}>
      <h3 className="text-sm font-semibold text-ink">{TARGET_LABEL[target]}</h3>
      {c === null ? (
        <p className="text-sm text-ink-muted">No games with a retained pre-kickoff line and a final score yet.</p>
      ) : (
        <dl className="space-y-2 text-sm">
          <div>
            <dt className="text-xs text-ink-muted">Average miss</dt>
            <dd className="font-mono font-semibold text-ink">Model {c.modelMiss.toFixed(1)} pts · Betting line {c.lineMiss.toFixed(1)} pts</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-muted">Closer to the final score</dt>
            <dd className="text-ink">
              <span className="font-semibold">Model closer in {c.modelCloser} of {plural(c.decided, "game")}</span>
              <span className="block text-xs text-ink-muted">Betting line closer in {c.lineCloser} · Even: {c.even}</span>
            </dd>
          </div>
          <div>
            <dt className="text-xs text-ink-muted">Leaned (average over every game compared)</dt>
            <dd className="break-words text-ink">Model {leanText(target, c.modelLean)}; betting line {leanText(target, c.lineLean)}</dd>
          </div>
          <div>
            <dt className="text-xs text-ink-muted">Misses over {BIG_MISS_POINTS} pts</dt>
            <dd className="font-mono text-ink">Model {c.modelBigMisses} · Betting line {c.lineBigMisses}</dd>
          </div>
        </dl>
      )}
      <p className="text-xs leading-relaxed text-ink-muted">
        {c === null ? "" : `Compared on ${plural(c.n, "game")} with a retained pre-kickoff line. `}
        {left > 0
          ? `Left out: ${counts.retrospective} graded against a historical line and ${counts.unknown} with an unknown line source.`
          : "No graded games were left out."}
      </p>
    </Card>
  );
}

/** One cell per period: the muted record, then the win rate in bold. `edge` is the left divider's border colour. */
function RecordCell({ record, edge }: { record: Record3; edge: string }) {
  return (
    <td className={clsx("whitespace-nowrap border-l px-4 py-2.5 text-right", edge)}>
      <span className="font-mono text-ink-muted">{recordText(record)}</span>
      <span className="ml-3 inline-block min-w-[3.5rem] font-semibold text-ink">{rateText(record)}</span>
    </td>
  );
}

const TARGETS = ["spread", "total"] as const;

export function PerformanceDashboard({ data, title }: { data: PerformanceView; title: string }) {
  const games = data.gradedGames;
  const overall = useMemo(() => {
    const spread = recordFor(games, (game) => game.spreadResult);
    const total = recordFor(games, (game) => game.totalResult);
    return { spread, total, combined: merge(spread, total) };
  }, [games]);

  const weeklyData = useMemo(
    () => data.trend
      .filter((row) => graded(row.weekly.combined) > 0)
      .map((row) => ({
        ...row,
        inProgress: (data.weekRows.find((weekRow) => weekRow.week === row.week)?.unplayedGames ?? 0) > 0,
      })),
    [data.trend, data.weekRows],
  );

  const caveat = breakEvenCaveat(overall.combined.winRate, overall.combined.win + overall.combined.loss);

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
        {TARGETS.map((target) => {
          const record = overall[target];
          return (
            <div
              key={target}
              data-card=""
              className="min-w-0 rounded-xl border border-line bg-surface-card p-3 text-left shadow-sm sm:p-5"
            >
              <span className="block text-xs font-semibold uppercase tracking-wide text-ink-muted">{target === "spread" ? "Spread" : "Totals"}</span>
              <span className="mt-2 block font-mono text-xl font-bold tracking-tight text-ink sm:text-4xl">{recordText(record)}</span>
              <span className="mt-2 flex flex-wrap justify-between gap-1 text-sm text-ink-muted">
                <span>Win rate</span><strong className="font-mono text-ink">{rateText(record)}</strong>
              </span>
              <span className="mt-1 flex flex-wrap justify-between gap-1 text-xs text-ink-muted">
                <span>{graded(record)} graded picks</span>
                <span className="font-mono">{breakEvenText(record)}</span>
              </span>
            </div>
          );
        })}
      </section>
      <p className="text-xs leading-relaxed text-ink-muted" data-testid="record-caveat">
        Win rate shows how often picks were right; it is not a betting result.
        {caveat && <> {caveat}</>}
      </p>

      <section aria-labelledby="trend-heading" className="space-y-2">
        <h2 id="trend-heading" className="text-sm font-semibold text-ink">Season trend</h2>
        <Card padding="sm" className="sm:p-4">
          {data.trend.filter((row) => graded(row.weekly.combined) > 0).length >= 2
            ? <RecordTrendChart rows={data.trend.filter((row) => graded(row.weekly.combined) > 0)} />
            : <p className="text-sm text-ink-muted">The trend appears after two graded weeks.</p>}
        </Card>
      </section>

      <h2 id="filter-heading" className="text-sm font-semibold text-ink">Week by week</h2>

      <Card as="section" padding="none" aria-labelledby="weekly-heading" className="overflow-hidden">
        <h2 id="weekly-heading" className="sr-only">Weekly accuracy breakdown</h2>
        <div className="divide-y divide-line sm:hidden">
          {weeklyData.map((row) => (
            <div key={row.week} className="space-y-2 p-3">
              <div className="flex flex-wrap items-center gap-x-3">
                <Link href={`/?week=${row.week}`} className="inline-flex min-h-11 items-center gap-2 rounded text-sm font-bold text-ink hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-accent">
                  Week {row.week} <span aria-hidden>→</span>
                </Link>
                {row.inProgress && <span className="rounded-full border border-warn-line bg-warn-soft px-2 py-0.5 text-xs font-medium text-warn">In progress</span>}
              </div>
              <div className="grid grid-cols-2 gap-2">
                {TARGETS.map((target) => (
                  <div key={target} className="min-w-0 rounded-lg bg-surface-inset p-2">
                    <p className="text-xs font-semibold text-ink-muted">{target === "spread" ? "Spread" : "Total"}</p>
                    <p className="mt-1 flex flex-wrap justify-between gap-1 font-mono text-sm text-ink">
                      <span>{recordText(row.weekly[target])}</span><span>{rateText(row.weekly[target])}</span>
                    </p>
                    <p className="mt-1 text-xs text-ink-muted">To date {recordText(row.cumulative[target])} · {rateText(row.cumulative[target])}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}
          <div className="space-y-1 border-t-2 border-line bg-surface-inset p-3 text-sm text-ink-muted">
            <p className="font-semibold text-ink">Season Total</p>
            <p>Spread: {recordText(overall.spread)} · Total: {recordText(overall.total)}</p>
            <p>Win rate: {rateText(overall.combined)}</p>
          </div>
        </div>
        <div className="hidden overflow-x-auto sm:block">
          <table className="w-full table-fixed text-left text-sm tabular-nums">
            <caption className="sr-only">Weekly pick results</caption>
            <colgroup>
              <col className="w-[16%]" />
              {TARGETS.flatMap((target) => [0, 1].map((i) => <col key={`${target}-${i}`} />))}
            </colgroup>
            <thead className="border-b border-line bg-surface-inset text-xs text-ink-muted">
              <tr>
                <th scope="col" rowSpan={2} className="px-4 py-3 align-bottom">Week</th>
                {TARGETS.map((target) => (
                  <th key={target} scope="colgroup" colSpan={2} className="border-l border-line px-3 pb-1 pt-3 text-center text-sm font-semibold text-ink">
                    {target === "spread" ? "Spread" : "Totals"}
                  </th>
                ))}
              </tr>
              <tr>
                {TARGETS.flatMap((target) => [
                  <th key={`${target}-week`} scope="col" className="border-l border-line px-4 pb-2 text-right font-medium">This week</th>,
                  <th key={`${target}-date`} scope="col" className="border-l border-line/50 px-4 pb-2 text-right font-medium">Season to date</th>,
                ])}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {weeklyData.map((row) => (
                <tr key={row.week}>
                  <th scope="row" className="whitespace-nowrap px-4 py-2.5 text-left text-ink">
                    <Link href={`/?week=${row.week}`} className="inline-flex min-h-9 items-center rounded font-semibold hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-accent">Week {row.week}</Link>
                    {row.inProgress && <span className="ml-2 whitespace-nowrap rounded-full border border-warn-line bg-warn-soft px-2 py-0.5 text-xs font-medium text-warn">In progress</span>}
                  </th>
                  {TARGETS.flatMap((target) => [
                    <RecordCell key={`${target}-week`} record={row.weekly[target]} edge="border-line" />,
                    <RecordCell key={`${target}-date`} record={row.cumulative[target]} edge="border-line/50" />,
                  ])}
                </tr>
              ))}
            </tbody>
            <tfoot className="border-t-2 border-line bg-surface-inset font-semibold text-ink">
              <tr>
                <th scope="row" className="whitespace-nowrap px-4 py-3 text-left">Season Total</th>
                {TARGETS.flatMap((target) => [
                  <RecordCell key={`${target}-week`} record={overall[target]} edge="border-line" />,
                  <td key={`${target}-date`} className="border-l border-line/50" />,
                ])}
              </tr>
            </tfoot>
          </table>
        </div>
      </Card>


      <p className="text-xs text-ink-muted">Records are wins–losses–pushes; win rate excludes pushes. <span className="max-sm:hidden">Select a week in the table to view its game-by-game results and graded picks on the Games tab.</span></p>

      <section aria-labelledby="market-heading" className="space-y-2">
        <h2 id="market-heading" className="text-sm font-semibold text-ink">Model vs the betting line</h2>
        <p className="text-xs leading-relaxed text-ink-muted">
          The same games and the same final scores: how far off the model and the retained pre-kickoff betting line were. Lower is closer. The win-loss record above is settled separately, at the best quote found for each pick.
        </p>
        <div className="grid gap-2.5 sm:grid-cols-2 sm:gap-4">
          {(["spread", "total"] as const).map((target) => <ComparisonCard key={target} target={target} view={data.market[target]} />)}
        </div>
      </section>

      <ResponsiveDisclosure title="Season-wide forecast diagnostics" heading="Season-wide forecast diagnostics">
        <section aria-labelledby="calibration-heading" className="space-y-3">
          <h2 id="calibration-heading" className="sr-only">Forecast accuracy</h2>
          <p className="text-sm">Average miss, every game with a final score ({data.summary.games} games). Forecasts compared with certified final scores.</p>
          <dl className="grid gap-3 sm:grid-cols-2">
            {([
              ["Spread average miss", decimal(data.summary.marginMae, " pts")],
              ["Total average miss", decimal(data.summary.totalMae, " pts")],
              ["Spread 95% interval", decimal(data.summary.marginCoverage95, "%")],
              ["Total 95% interval", decimal(data.summary.totalCoverage95, "%")],
            ] as const).map(([label, value]) => (
              <div key={label}><dt>{label}</dt><dd className="font-mono font-semibold text-ink">{value}</dd></div>
            ))}
          </dl>
        </section>
      </ResponsiveDisclosure>
    </div>
  );
}
