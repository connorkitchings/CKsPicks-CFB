import Image from "next/image";
import Link from "next/link";
import { clsx } from "clsx";
import { logoUrl } from "@/lib/teams";
import { BetTable } from "./BetTable";
import { BetComparisonTable } from "./BetComparisonTable";
import type { Game } from "@/lib/queries";

function formatKickoff(startDate: Date): string {
  return startDate.toLocaleString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

import {
  modelSpreadView,
  marketSpreadView,
  spreadBetLabel,
  spreadEdge,
  spreadLabel,
  totalBetLabel,
  totalEdge,
} from "@/lib/betting-format";

function ResultCell({ result }: { result: "win" | "loss" | "push" | null }) {
  if (result === null) {
    return <span className="text-ink-faint">—</span>;
  }
  return (
    <span
      className={clsx(
        "inline-block rounded px-1.5 py-0.5 text-[11px] font-medium",
        result === "win" && "bg-win-soft text-win",
        result === "loss" && "bg-loss-soft text-loss",
        result === "push" && "bg-surface-inset text-ink-muted",
      )}
    >
      {result === "win" ? "Win" : result === "loss" ? "Loss" : "Push"}
    </span>
  );
}

/**
 * Matchup-centric game card. One shell serves both publication modes: the
 * box-score block (logos, names, final scores) is always present, followed by
 * a compact market-vs-model table. Predictions mode shows Market / Model /
 * Model Bet / Bet Result; market mode (fail-closed, no model output) shows
 * Market / Bet Result only.
 */
export function GameRow({
  game,
  ranks,
}: {
  game: Game;
  ranks?: Map<string, number>;
}) {
  if (game.publicationMode === "market") {
    return <MarketGameRow game={game} ranks={ranks} />;
  }
  const hasAnyLine =
    game.homeTeamSpreadLine !== null || game.totalLine !== null;
  const marketSpread = marketSpreadView(
    game.homeTeam,
    game.awayTeam,
    game.homeTeamSpreadLine,
  );
  const modelSpread = modelSpreadView(
    game.homeTeam,
    game.awayTeam,
    game.predictedSpread,
  );
  const spreadBet = spreadBetLabel(
    game.homeTeam,
    game.awayTeam,
    game.spreadLean,
    game.homeTeamSpreadLine,
  );
  const totalBet = totalBetLabel(game.totalLean, game.totalLine);

  const awayRank = ranks?.get(game.awayTeam) ?? null;
  const homeRank = ranks?.get(game.homeTeam) ?? null;

  return (
    <li className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
      {/* Meta row: kickoff + high-confidence marker */}
      <div className="mb-3 flex items-center justify-between gap-2 text-xs text-ink-faint">
        <span>{formatKickoff(game.startDate)}</span>
        {game.highConfidence && (
          <span
            className="text-sm leading-none text-accent"
            title="High confidence lean"
            aria-label="High confidence lean"
          >
            ★
          </span>
        )}
      </div>

      {/* Box score: logos, teams, finals, and power ranks */}
      <div className="space-y-1.5">
        <TeamLine
          name={game.awayTeam}
          record={game.awayRecord}
          score={game.awayPoints}
          highlighted={game.spreadLean === "away"}
          rank={awayRank}
        />
        <TeamLine
          name={game.homeTeam}
          record={game.homeRecord}
          home
          score={game.homePoints}
          highlighted={game.spreadLean === "home"}
          rank={homeRank}
        />
      </div>

      {/* Responsive Bet Comparison Table */}
      <BetComparisonTable
        marketSpread={spreadLabel(marketSpread)}
        modelSpread={spreadLabel(modelSpread)}
        spreadEdge={spreadEdge(modelSpread, marketSpread)}
        spreadBet={spreadBet}
        spreadResult={game.spreadResult}
        totalLine={game.totalLine}
        predictedTotal={game.predictedTotal}
        totalEdge={totalEdge(game.predictedTotal, game.totalLine)}
        totalBet={totalBet}
        totalResult={game.totalResult}
      />

      {!hasAnyLine && (
        <p className="mt-2 text-xs text-ink-faint">
          No market line — model prediction shown, no lean.
        </p>
      )}

      {/* Matchup Deep Dive Slot (Phase 2 extension point) */}
      <div className="mt-3 pt-2.5 border-t border-line/60 flex items-center justify-between text-xs">
        <span className="text-[11px] text-ink-faint font-mono">
          {game.systemName ? game.systemName : "Blitzkrieg V5"}
        </span>
        <Link
          href={`/matchup/${game.gameId}`}
          className="text-[11px] font-medium text-ink-muted hover:text-accent-ink hover:underline transition-colors flex items-center gap-1"
          title={`View ${game.awayTeam} vs ${game.homeTeam} matchup breakdown`}
        >
          Matchup Breakdown →
        </Link>
      </div>
    </li>
  );
}

/** Market-mode card: same shell; the table omits model columns (fail-closed). */
function MarketGameRow({
  game,
  ranks,
}: {
  game: Extract<Game, { publicationMode: "market" }>;
  ranks?: Map<string, number>;
}) {
  const hasResults = game.homePoints !== null && game.awayPoints !== null;
  const marketSpread = marketSpreadView(
    game.homeTeam,
    game.awayTeam,
    game.homeTeamSpreadLine,
  );
  const awayRank = ranks?.get(game.awayTeam) ?? null;
  const homeRank = ranks?.get(game.homeTeam) ?? null;

  return (
    <li className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-2 text-xs text-ink-faint">
        <span>{formatKickoff(game.startDate)}</span>
        {hasResults && (
          <span className="rounded-full bg-surface-inset px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
            Final
          </span>
        )}
      </div>
      <div className="space-y-1.5">
        <TeamLine
          name={game.awayTeam}
          record={game.awayRecord}
          score={game.awayPoints}
          highlighted={false}
          rank={awayRank}
        />
        <TeamLine
          name={game.homeTeam}
          record={game.homeRecord}
          home
          score={game.homePoints}
          highlighted={false}
          rank={homeRank}
        />
      </div>
      <BetTable
        ariaLabel="Market and results"
        tableClassName="mt-3 w-full tabular-nums text-[11px] sm:text-xs"
        headerCellClassName="pl-2 text-right"
        bodyCellClassName={[
          "py-1.5 pl-2 text-right font-mono tabular-nums text-ink",
          "py-1.5 pl-2 text-right text-ink",
        ]}
        columns={[{ header: "Market" }, { header: "Bet Result" }]}
        rows={[
          {
            label: "Spread",
            cells: [
              spreadLabel(marketSpread),
              <ResultCell key="result" result={game.spreadResult} />,
            ],
          },
          {
            label: "Total",
            cells: [
              game.totalLine === null
                ? "O/U —"
                : `O/U ${game.totalLine.toFixed(1)}`,
              <ResultCell key="result" result={game.totalResult} />,
            ],
          },
        ]}
      />
    </li>
  );
}

function TeamLine({
  name,
  record = null,
  home = false,
  score,
  highlighted,
  rank = null,
}: {
  name: string;
  /** Season W-L as of kickoff (e.g. "1-0"); null hides the marker. */
  record?: string | null;
  home?: boolean;
  score: number | null;
  highlighted: boolean;
  rank?: number | null;
}) {
  const isTop25 = rank !== null && rank >= 1 && rank <= 25;

  return (
    <div className="flex items-center gap-2.5">
      <Image
        src={logoUrl(name)}
        alt={name}
        width={28}
        height={28}
        className="h-7 w-7 shrink-0 object-contain"
        unoptimized
      />
      {isTop25 && (
        <span
          className="text-xs font-bold text-accent-ink shrink-0"
          aria-label={`Rank ${rank}`}
        >
          #{rank}
        </span>
      )}
      <Link
        href={`/teams/${encodeURIComponent(name)}`}
        className={clsx(
          "min-w-0 truncate text-sm text-ink hover:text-accent-ink hover:underline focus-visible:rounded focus-visible:outline-2 focus-visible:outline-accent",
          highlighted && "font-semibold",
        )}
      >
        {name}
      </Link>
      {record && (
        <span className="text-xs tabular-nums text-ink-faint">({record})</span>
      )}
      {home && (
        <span className="text-[10px] uppercase tracking-wide text-ink-faint">
          home
        </span>
      )}
      {score !== null && (
        <span className="ml-auto font-mono text-base font-semibold tabular-nums text-ink">
          {score}
        </span>
      )}
    </div>
  );
}
