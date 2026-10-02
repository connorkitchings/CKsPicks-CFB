import clsx from "clsx";
import type { PredictionGame } from "@/lib/queries";
import TeamLogo from "@/components/TeamLogo";

function TeamLine({
  name,
  record,
  rank,
  score,
  highlight,
  size,
  side,
}: {
  name: string;
  record: string | null;
  rank?: number;
  score: number | null;
  /** Emphasize the name (e.g. the winner on Results). */
  highlight: boolean;
  size: number;
  side: "away" | "home";
}) {
  return (
    <div className="flex items-center gap-2.5" data-side={side}>
      <TeamLogo name={name} px={size} />
      <span className={clsx("min-w-0 truncate text-sm", highlight ? "font-semibold text-accent-ink" : "text-ink")}>
        {name}
      </span>
      {record && <span className="text-xs tabular-nums text-ink-faint">({record})</span>}
      {rank !== undefined && (
        <span
          title="V5 overall rating rank"
          className="rounded bg-surface-inset px-1 text-[10px] font-medium tabular-nums text-ink-muted"
        >
          #{rank}
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

/**
 * The two teams of a game: away on top, home on the bottom. Every card and row
 * layout uses this one component so the order cannot drift. There is no "home"
 * tag; the bottom team is the home team.
 */
export function TeamPair({
  game,
  ranks,
  size = 28,
  winner = null,
}: {
  game: PredictionGame;
  ranks: Record<string, number>;
  size?: number;
  /** Highlight the winning side's name (Results). */
  winner?: "away" | "home" | null;
}) {
  return (
    <div className="space-y-1.5">
      <TeamLine
        name={game.awayTeam}
        record={game.awayRecord}
        rank={ranks[game.awayTeam]}
        score={game.awayPoints}
        highlight={winner === "away"}
        size={size}
        side="away"
      />
      <TeamLine
        name={game.homeTeam}
        record={game.homeRecord}
        rank={ranks[game.homeTeam]}
        score={game.homePoints}
        highlight={winner === "home"}
        size={size}
        side="home"
      />
    </div>
  );
}
