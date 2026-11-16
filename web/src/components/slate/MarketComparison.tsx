"use client";

import Link from "next/link";
import { marketComparisonPoints, type MarketBoardMetric } from "@/lib/charts";
import type { Game } from "@/lib/queries";
import { homeSpreadText } from "@/lib/betting-format";
import { bookName } from "@/lib/slate";

type ComparisonPoint = ReturnType<typeof marketComparisonPoints>["points"][number];

/** Each metric gets its own padded domain; only the spread (a signed margin) must include 0. */
function domainFor(points: readonly ComparisonPoint[], metric: MarketBoardMetric) {
  const values = points.flatMap((point) => [point.market, point.model]);
  if (metric === "spread") values.push(0);
  const low = Math.min(...values);
  const high = Math.max(...values);
  const min = (Number.isFinite(low) ? low : 0) - 2;
  const max = Number.isFinite(high) && high > low ? high + 2 : min + 4;
  return (value: number) => 8 + ((value - min) / (max - min)) * 84;
}

/** Home margin (positive favors home) as the home team's spread: "Ohio State -6.0" / "Ohio State PK". */
function spreadText(homeTeam: string, margin: number) {
  const homeSpread = Math.abs(margin) < 0.05 ? 0 : -margin;
  return homeSpreadText(homeTeam, homeSpread);
}

function TargetCell({
  metric,
  point,
  position,
}: {
  metric: MarketBoardMetric;
  point: ComparisonPoint | undefined;
  position: (value: number) => number;
}) {
  const label = metric === "spread" ? "Spread" : "Total";
  if (!point) {
    return (
      <div className="space-y-1">
        <div className="text-[11px] font-medium uppercase tracking-wider text-ink-muted">{label}</div>
        <p className="text-xs text-ink-muted">Missing {metric} line or model projection</p>
      </div>
    );
  }
  const book = bookName(point.source);
  const marketText = metric === "spread" ? spreadText(point.homeTeam, point.market) : point.market.toFixed(1);
  const modelText = metric === "spread" ? spreadText(point.homeTeam, point.model) : point.model.toFixed(1);
  const diffText = Math.abs(point.edge).toFixed(1);
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-2 text-[11px] text-ink-muted">
        <span className="font-medium uppercase tracking-wider">{label}</span>
        {book && <span>{book}</span>}
      </div>
      <svg
        viewBox="0 0 100 16"
        className="h-6 w-full"
        role="img"
        aria-label={`Market ${marketText}, model ${modelText} ${metric === "spread" ? "spread" : "total points"}`}
      >
        <line x1="8" x2="92" y1="8" y2="8" className="stroke-line" strokeWidth="0.5" />
        <line x1={position(point.market)} x2={position(point.model)} y1="8" y2="8" className="stroke-ink-muted" strokeWidth="1" />
        <circle cx={position(point.market)} cy="8" r="2.2" className="fill-surface-card stroke-ink" strokeWidth="0.8" />
        <circle cx={position(point.model)} cy="8" r="2.2" className="fill-accent" />
      </svg>
      <p className="flex flex-wrap items-baseline justify-between gap-x-2 text-xs tabular-nums text-ink">
        <span>Market {marketText} · Model {modelText}</span>
        <span className="text-ink-muted">Difference: {diffText} pts</span>
      </p>
    </div>
  );
}

/** The same market-board data foundation, showing spread and total side by side. */
export function MarketComparison({ games, matchupEnabled }: {
  games: Game[];
  matchupEnabled: boolean;
}) {
  const predictionGames = games.filter((game) => game.publicationMode === "predictions");
  const spreadData = marketComparisonPoints(predictionGames, "spread");
  const totalData = marketComparisonPoints(predictionGames, "total");
  const spreadByGame = new Map(spreadData.points.map((point) => [point.gameId, point]));
  const totalByGame = new Map(totalData.points.map((point) => [point.gameId, point]));
  const spreadPos = domainFor(spreadData.points, "spread");
  const totalPos = domainFor(totalData.points, "total");
  const rows = predictionGames.filter((game) => spreadByGame.has(game.gameId) || totalByGame.has(game.gameId));
  const unavailable = [...spreadData.unavailable, ...totalData.unavailable];

  return (
    <section className="space-y-4" aria-label="Model vs market">
      <h2 className="text-xl font-semibold text-ink">Model vs market</h2>
      <p className="max-w-3xl text-sm text-ink-muted">
        Spread is home margin in points (positive favors the home team; negative favors the away team); Total is combined points scored by both teams. ○ Selected market line · ● Model forecast. Differences describe disagreement, not confidence.
      </p>
      <p className="text-xs text-ink-muted">
        {spreadData.points.length} of {games.length} filtered games have a comparable spread; {totalData.points.length} of {games.length} have a comparable total.
      </p>
      {rows.length === 0 ? (
        <p role="status" className="py-8 text-sm text-ink-muted">No comparable forecasts and lines for these filters.</p>
      ) : (
        <div className="divide-y divide-line">
          {rows.map((game) => (
            <article
              key={game.gameId}
              className="grid items-center gap-4 py-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)_minmax(0,1.2fr)]"
            >
              {matchupEnabled ? (
                <Link href={`/matchup/${game.gameId}`} className="flex min-h-11 items-center font-medium text-accent-ink underline-offset-4 hover:underline">
                  {game.awayTeam} at {game.homeTeam}
                </Link>
              ) : (
                <span>{game.awayTeam} at {game.homeTeam}</span>
              )}
              <TargetCell metric="spread" point={spreadByGame.get(game.gameId)} position={spreadPos} />
              <TargetCell metric="total" point={totalByGame.get(game.gameId)} position={totalPos} />
            </article>
          ))}
        </div>
      )}
      {unavailable.length > 0 && (
        <details className="text-sm text-ink-muted">
          <summary className="min-h-11 cursor-pointer py-3">Why {unavailable.length} {unavailable.length === 1 ? "line is" : "lines are"} unavailable</summary>
          <ul>
            {unavailable.map((game, i) => (
              <li key={i}>{game.awayTeam} at {game.homeTeam}: {game.reason}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
