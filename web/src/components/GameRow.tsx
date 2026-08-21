import Image from "next/image";
import { clsx } from "clsx";
import { LeanBadge, TotalLeanChip } from "./LeanBadge";
import { logoUrl } from "@/lib/teams";
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

function signedSpread(n: number | null): string {
  if (n === null) return "—";
  return n > 0 ? `+${n.toFixed(1)}` : n.toFixed(1);
}

function marketSpreadLabel(homeTeam: string, line: number | null): string {
  if (line === null) return "PK / no line";
  // Line is the home team's spread; +home dog, -home favorite.
  return `${homeTeam} ${signedSpread(line)}`;
}

function modelProjectionLabel(
  homeTeam: string,
  awayTeam: string,
  predictedSpread: number | null,
  predictedTotal: number | null,
): string {
  const spread =
    predictedSpread === null
      ? "spread unavailable"
      : predictedSpread === 0
        ? "pick ’em"
        : `${predictedSpread > 0 ? homeTeam : awayTeam} by ${Math.abs(predictedSpread).toFixed(1)}`;
  const total =
    predictedTotal === null ? null : `${predictedTotal.toFixed(1)} total`;
  return total ? `${spread} · ${total}` : spread;
}

const REGIME_LABEL = {
  preseason: "Preseason",
  one_game: "1 game",
  two_games: "2 games",
  three_games: "3 games",
  game_1: "Game 1",
  game_2: "Game 2",
  game_3: "Game 3",
  game_4: "Game 4",
  established: "Established",
} as const;

/**
 * Matchup-centric game card. One shell serves both publication modes:
 * the matchup block (logos, names, big final scores) is always present;
 * predictions mode adds a lean rail and a compact model projection, while
 * market mode shows the current lines in the same rail position.
 */
export function GameRow({ game }: { game: Game }) {
  if (game.publicationMode === "market") {
    return <MarketGameRow game={game} />;
  }
  const hasResults = game.homePoints !== null && game.awayPoints !== null;
  const hasAnyLine =
    game.homeTeamSpreadLine !== null || game.totalLine !== null;
  const regimeLabel = game.regime ? REGIME_LABEL[game.regime] : null;

  return (
    <li className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
      {/* Meta row: kickoff + context markers */}
      <div className="mb-3 flex items-center justify-between gap-2 text-xs text-ink-faint">
        <span>{formatKickoff(game.startDate)}</span>
        <div className="flex items-center gap-2">
          {regimeLabel && (
            <span className="rounded-full bg-surface-inset px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
              {regimeLabel}
            </span>
          )}
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
      </div>

      {/* Matchup + lean rail */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
        <div className="min-w-0 flex-1 space-y-1.5">
          <TeamLine
            name={game.awayTeam}
            score={game.awayPoints}
            highlighted={game.spreadLean === "away"}
          />
          <TeamLine
            name={game.homeTeam}
            home
            score={game.homePoints}
            highlighted={game.spreadLean === "home"}
          />
        </div>
        {hasAnyLine ? (
          <div className="shrink-0 sm:text-right">
            <div className="mb-1 text-[10px] font-medium uppercase tracking-wide text-ink-faint">
              Market Consensus
            </div>
            <div className="flex gap-6 sm:flex-col sm:gap-1.5">
              <LeanBadge
                lean={game.spreadLean}
                edge={game.edgeSpread}
                homeTeam={game.homeTeam}
                awayTeam={game.awayTeam}
                homeLine={game.homeTeamSpreadLine}
              />
              <TotalLeanChip
                lean={game.totalLean}
                edge={game.edgeTotal}
                totalLine={game.totalLine}
              />
            </div>
          </div>
        ) : (
          <p className="shrink-0 text-xs text-ink-faint sm:max-w-40 sm:text-right">
            No market line — model prediction shown, no lean.
          </p>
        )}
      </div>

      {/* Lines already appear in the lean rail. Keep the projection once, in plain language. */}
      <div className="mt-2 text-xs text-ink-muted">
        <span className="text-ink-faint">Model projection: </span>
        <span className="font-mono tabular-nums">
          {modelProjectionLabel(
            game.homeTeam,
            game.awayTeam,
            game.predictedSpread,
            game.predictedTotal,
          )}
        </span>
      </div>

      {/* Grades (once the game is scored) */}
      {hasResults && (game.spreadResult || game.totalResult) && (
        <div className="mt-2 flex items-center gap-2">
          {game.spreadResult && (
            <ResultChip label="Spread" result={game.spreadResult} />
          )}
          {game.totalResult && (
            <ResultChip label="Total" result={game.totalResult} />
          )}
        </div>
      )}

    </li>
  );
}

/** Market-mode card: same shell, with current lines in the rail position. */
function MarketGameRow({
  game,
}: {
  game: Extract<Game, { publicationMode: "market" }>;
}) {
  return (
    <li className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
      <div className="mb-3 text-xs text-ink-faint">
        {formatKickoff(game.startDate)}
      </div>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
        <div className="min-w-0 flex-1 space-y-1.5">
          <TeamLine name={game.awayTeam} score={game.awayPoints} highlighted={false} />
          <TeamLine name={game.homeTeam} home score={game.homePoints} highlighted={false} />
        </div>
        <div className="shrink-0 sm:text-right">
          <div className="text-xs text-ink-faint">Market Consensus</div>
          <div className="font-mono text-sm tabular-nums text-ink">
            {marketSpreadLabel(game.homeTeam, game.homeTeamSpreadLine)}
          </div>
          <div className="font-mono text-sm tabular-nums text-ink">
            {game.totalLine === null
              ? "O/U —"
              : `O/U ${game.totalLine.toFixed(1)}`}
          </div>
        </div>
      </div>
    </li>
  );
}

function TeamLine({
  name,
  home = false,
  score,
  highlighted,
}: {
  name: string;
  home?: boolean;
  score: number | null;
  highlighted: boolean;
}) {
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
      <span
        className={clsx(
          "truncate text-sm text-ink",
          highlighted && "font-semibold",
        )}
      >
        {name}
      </span>
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

function ResultChip({
  label,
  result,
}: {
  label: string;
  result: "win" | "loss" | "push";
}) {
  return (
    <span
      className={clsx(
        "rounded px-1.5 py-0.5 text-[11px] font-medium",
        result === "win" && "bg-win-soft text-win",
        result === "loss" && "bg-loss-soft text-loss",
        result === "push" && "bg-surface-inset text-ink-muted",
      )}
    >
      {label} {result}
    </span>
  );
}
