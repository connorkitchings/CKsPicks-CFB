"use client";

import Link from "next/link";
import { groupUnavailableByGame, marketComparisonPoints, type MarketBoardMetric } from "@/lib/charts";
import type { Game } from "@/lib/queries";
import { homeSpreadText } from "@/lib/betting-format";
import { bookName, gameState } from "@/lib/slate";
import { Disclosure } from "@/components/ui/Disclosure";
import { Notice } from "@/components/ui/Notice";
import { AwaitingTag } from "./AwaitingTag";
import { dayShort, kickoffTime } from "./format";

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
  missing,
}: {
  metric: MarketBoardMetric;
  point: ComparisonPoint | undefined;
  position: (value: number) => number;
  /** Why there is no point, e.g. "No total line". */
  missing?: string;
}) {
  const label = metric === "spread" ? "Spread" : "Total";
  if (!point) {
    return (
      <div className="space-y-1">
        <div className="text-[11px] font-medium uppercase tracking-wider text-ink-muted">{label}</div>
        <p className="text-xs text-ink-muted">{missing ?? "Comparison unavailable"}</p>
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

const capitalized = (text: string) => text.charAt(0).toUpperCase() + text.slice(1);

/** The same market-board data foundation, showing spread and total side by side. */
export function MarketComparison({ games, matchupEnabled, now, onReset }: {
  games: Game[];
  matchupEnabled: boolean;
  /** The clock for awaiting-result tags. */
  now: Date;
  /** Clears the filters that emptied the view. */
  onReset: () => void;
}) {
  const predictionGames = games.filter((game) => game.publicationMode === "predictions");
  const spreadData = marketComparisonPoints(predictionGames, "spread");
  const totalData = marketComparisonPoints(predictionGames, "total");
  const spreadByGame = new Map(spreadData.points.map((point) => [point.gameId, point]));
  const totalByGame = new Map(totalData.points.map((point) => [point.gameId, point]));
  const spreadMissing = new Map(spreadData.unavailable.map((item) => [item.gameId, capitalized(item.reason)]));
  const totalMissing = new Map(totalData.unavailable.map((item) => [item.gameId, capitalized(item.reason)]));
  const spreadPos = domainFor(spreadData.points, "spread");
  const totalPos = domainFor(totalData.points, "total");
  const rows = predictionGames.filter((game) => spreadByGame.has(game.gameId) || totalByGame.has(game.gameId));
  const unavailable = groupUnavailableByGame(spreadData.unavailable, totalData.unavailable);
  const total = predictionGames.length;

  return (
    <section className="space-y-4" aria-label="Model vs market">
      <h2 className="text-xl font-semibold text-ink">Model vs market</h2>
      <p className="max-w-3xl text-sm text-ink-muted max-sm:hidden">
        Spread is home margin in points (positive favors the home team; negative favors the away team); Total is combined points scored by both teams. ○ Selected market line · ● Model forecast. Differences describe disagreement, not confidence.
      </p>
      <Disclosure title="How to read this" className="sm:hidden">
        <p>Spread is home margin in points (positive favors the home team; negative favors the away team); Total is combined points scored by both teams. ○ Selected market line · ● Model forecast. Differences describe disagreement, not confidence.</p>
      </Disclosure>
      <p className="text-xs text-ink-muted">
        {spreadData.points.length} of {total} filtered games have a comparable spread; {totalData.points.length} of {total} have a comparable total.
      </p>
      {rows.length === 0 ? (
        <Notice
          tone="empty"
          action={<button type="button" onClick={onReset} className="min-h-11 rounded-lg px-3 font-medium text-accent-ink underline focus-visible:outline-2 focus-visible:outline-accent">Show all games</button>}
        >
          No comparable forecasts and lines for these filters.
        </Notice>
      ) : (
        <div className="divide-y divide-line">
          {rows.map((game) => (
            <article
              key={game.gameId}
              className="grid items-center gap-4 py-4 md:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)_minmax(0,1.2fr)]"
            >
              <div className="min-w-0">
                {matchupEnabled ? (
                  <Link href={`/matchup/${game.gameId}`} className="flex min-h-11 items-center font-medium text-accent-ink underline-offset-4 hover:underline">
                    {game.awayTeam} at {game.homeTeam}
                  </Link>
                ) : (
                  <span>{game.awayTeam} at {game.homeTeam}</span>
                )}
                <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-ink-muted">
                  <span>{dayShort(game.startDate)} · {kickoffTime(game.startDate)}</span>
                  {gameState(game, now) === "final" && <span className="font-semibold">Final</span>}
                  <AwaitingTag game={game} now={now} />
                </p>
              </div>
              <TargetCell metric="spread" point={spreadByGame.get(game.gameId)} position={spreadPos} missing={spreadMissing.get(game.gameId)} />
              <TargetCell metric="total" point={totalByGame.get(game.gameId)} position={totalPos} missing={totalMissing.get(game.gameId)} />
            </article>
          ))}
        </div>
      )}
      {unavailable.length > 0 && (
        <details data-testid="market-unavailable" className="text-sm text-ink-muted">
          <summary className="min-h-11 cursor-pointer py-3">Why {unavailable.length} {unavailable.length === 1 ? "game is" : "games are"} missing a comparison</summary>
          <ul>
            {unavailable.map((game) => (
              <li key={game.gameId}>{game.awayTeam} at {game.homeTeam}: {game.reasons.join("; ")}</li>
            ))}
          </ul>
        </details>
      )}
    </section>
  );
}
