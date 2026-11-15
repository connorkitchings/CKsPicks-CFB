"use client";

import Link from "next/link";
import { marketComparisonPoints, type MarketBoardMetric } from "@/lib/charts";
import type { Game } from "@/lib/queries";
import { bookName } from "@/lib/slate";
import { etDateTime } from "@/lib/time-et";
import { SegmentedControl } from "@/components/ui/SegmentedControl";

/** The same market-board data foundation, shown as paired marks with exact values. */
export function MarketComparison({ games, matchupEnabled, metric, onMetricChange }: {
  games: Game[]; matchupEnabled: boolean; metric: MarketBoardMetric; onMetricChange: (metric: MarketBoardMetric) => void;
}) {
  const data = marketComparisonPoints(games.filter((game) => game.publicationMode === "predictions"), metric);
  const points = data.points;
  const values = points.flatMap((point) => [point.market, point.model]);
  const min = Math.min(0, ...values) - 2;
  const max = Math.max(1, ...values) + 2;
  const position = (value: number) => 8 + (value - min) / (max - min) * 84;
  const number = (value: number) => `${metric === "spread" && value > 0 ? "+" : ""}${value.toFixed(1)}`;
  return (
    <section className="space-y-4" aria-label="Model vs market">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold text-ink">Model vs market</h2>
        <SegmentedControl label="Market comparison target" value={metric} onChange={onMetricChange} options={[{ value: "spread", label: "Spread" }, { value: "total", label: "Total" }]} />
      </div>
      <p className="max-w-3xl text-sm text-ink-muted">{metric === "spread" ? "Home margin in points: positive favors the home team; negative favors the away team." : "Combined points scored by both teams."} ○ Selected market line · ● Model forecast. Differences describe disagreement, not confidence.</p>
      <p className="text-xs text-ink-muted">{points.length} of {games.length} filtered games have both a forecast and selected line.</p>
      {points.length === 0 ? <p role="status" className="py-8 text-sm text-ink-muted">No comparable forecasts and lines for these filters.</p> : (
        <div className="divide-y divide-line">
          {points.map((point) => (
            <article key={point.gameId} className="grid items-center gap-2 py-4 sm:grid-cols-[minmax(0,1fr)_minmax(180px,1fr)_auto]">
              {matchupEnabled ? <Link href={`/matchup/${point.gameId}`} className="min-h-11 font-medium text-accent-ink underline-offset-4 hover:underline">{point.awayTeam} at {point.homeTeam}</Link> : <span>{point.awayTeam} at {point.homeTeam}</span>}
              <svg viewBox="0 0 100 20" className="h-10 w-full" role="img" aria-label={`Market ${number(point.market)}, model ${number(point.model)} ${metric === "spread" ? "home margin" : "total"} points`}>
                <line x1="8" x2="92" y1="10" y2="10" className="stroke-line" strokeWidth="0.5" />
                <line x1={position(point.market)} x2={position(point.model)} y1="10" y2="10" className="stroke-ink-muted" strokeWidth="1" />
                <circle cx={position(point.market)} cy="10" r="2" className="fill-surface-card stroke-ink" strokeWidth="0.8" />
                <circle cx={position(point.model)} cy="10" r="2" className="fill-accent" />
              </svg>
              <p className="text-sm tabular-nums text-ink">
                Market {number(point.market)} · Model {number(point.model)}
                <span className="block text-xs text-ink-muted">Difference: {Math.abs(point.model - point.market).toFixed(1)} pts</span>
                <span className="block text-[11px] text-ink-muted">
                  {bookName(point.source) ? `${bookName(point.source)} · ` : ""}
                  Line captured: {point.capturedAt ? etDateTime(point.capturedAt) : "unavailable"}
                </span>
              </p>
            </article>
          ))}
        </div>
      )}
      {data.unavailable.length > 0 && <details className="text-sm text-ink-muted"><summary className="cursor-pointer py-2">Why {data.unavailable.length} games are unavailable</summary><ul>{data.unavailable.map((game, i) => <li key={i}>{game.awayTeam} at {game.homeTeam}: {game.reason}</li>)}</ul></details>}
    </section>
  );
}
