import clsx from "clsx";
import type { Game } from "@/lib/queries";
import TeamLogo from "@/components/TeamLogo";

function TeamLine({
  name,
  record,
  score,
  highlight,
  size,
  side,
}: {
  name: string;
  record: string | null;
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
 * tag; the bottom team is the home team. No model rank badges: ranks live on
 * /ratings and /matchup, not on the high-density slate cards.
 */
export function TeamPair({
  game,
  size = 28,
  winner = null,
}: {
  game: Game;
  size?: number;
  /** Highlight the winning side's name (Results). */
  winner?: "away" | "home" | null;
}) {
  return (
    <div className="space-y-1.5">
      <TeamLine
        name={game.awayTeam}
        record={game.awayRecord}
        score={game.awayPoints}
        highlight={winner === "away"}
        size={size}
        side="away"
      />
      <TeamLine
        name={game.homeTeam}
        record={game.homeRecord}
        score={game.homePoints}
        highlight={winner === "home"}
        size={size}
        side="home"
      />
    </div>
  );
}
