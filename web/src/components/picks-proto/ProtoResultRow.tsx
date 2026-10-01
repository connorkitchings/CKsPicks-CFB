import type { PredictionGame } from "@/lib/queries";
import { coverMargin, leanFor, resultFor } from "@/lib/picks-proto";
import { LeanMarker } from "./LeanMarker";
import { coverText, ResultBadge } from "./ResultBadge";
import { dayShort } from "./format";
import { WhereLine } from "./GameWhen";
import { TeamPair } from "./TeamLine";

function Cell({ game, kind }: { game: PredictionGame; kind: "spread" | "total" }) {
  const lean = leanFor(game, kind);
  if (!lean) return <p className="text-xs text-ink-faint">No {kind} lean</p>;
  const grade = resultFor(game, kind);
  const text = coverText(coverMargin(game, kind));
  return (
    <div className="space-y-0.5 text-xs">
      <div className="flex items-center gap-2">
        <LeanMarker lean={lean} />
        <span className="min-w-0 truncate font-semibold text-ink">{lean.pick}</span>
        <span className="shrink-0 tabular-nums text-ink-muted">({lean.edge.toFixed(1)})</span>
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
      <div>
        <div className="whitespace-nowrap text-xs tabular-nums text-ink-muted">{dayShort(game.startDate)}</div>
        <WhereLine game={game} />
      </div>
      <TeamPair game={game} ranks={ranks} size={20} winner={awayWon ? "away" : homeWon ? "home" : null} />
      <Cell game={game} kind="spread" />
      <Cell game={game} kind="total" />
    </li>
  );
}
