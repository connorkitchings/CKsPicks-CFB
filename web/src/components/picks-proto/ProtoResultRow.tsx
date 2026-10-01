import type { PredictionGame } from "@/lib/queries";
import { coverMargin, leanFor, resultFor } from "@/lib/picks-proto";
import { coverText, ResultBadge } from "./ResultBadge";
import { dayShort } from "./format";
import { TeamLine } from "./TeamLine";

function Cell({ game, kind }: { game: PredictionGame; kind: "spread" | "total" }) {
  const lean = leanFor(game, kind);
  if (!lean) return <p className="text-xs text-ink-faint">No {kind} lean</p>;
  const grade = resultFor(game, kind);
  const text = coverText(coverMargin(game, kind));
  return (
    <div className="space-y-0.5 text-xs">
      <div className="flex items-center gap-2">
        <span className="min-w-0 truncate font-semibold text-ink">{lean.pick}</span>
        {grade && <ResultBadge grade={grade} />}
      </div>
      {text && <p className="tabular-nums text-ink-muted">{text}</p>}
    </div>
  );
}

/** Dense one-line-per-game results layout. */
export function ProtoResultRow({
  game,
  ranks,
}: {
  game: PredictionGame;
  ranks: Record<string, number>;
}) {
  const homeWon = (game.homePoints ?? 0) > (game.awayPoints ?? 0);
  const awayWon = (game.awayPoints ?? 0) > (game.homePoints ?? 0);
  return (
    <li
      id={`game-${game.gameId}`}
      className="grid scroll-mt-24 gap-x-4 gap-y-2 border-b border-line px-3 py-2.5 last:border-b-0 md:grid-cols-[6.5rem_minmax(0,1.4fr)_minmax(0,1fr)_minmax(0,1fr)] md:items-center"
    >
      <div className="whitespace-nowrap text-xs tabular-nums text-ink-muted">{dayShort(game.startDate)}</div>
      <div className="space-y-1">
        <TeamLine name={game.awayTeam} record={game.awayRecord} rank={ranks[game.awayTeam]} score={game.awayPoints} leaning={awayWon} size={20} />
        <TeamLine name={game.homeTeam} record={game.homeRecord} rank={ranks[game.homeTeam]} home score={game.homePoints} leaning={homeWon} size={20} />
      </div>
      <Cell game={game} kind="spread" />
      <Cell game={game} kind="total" />
    </li>
  );
}
