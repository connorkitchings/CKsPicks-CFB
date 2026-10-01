import type { PredictionGame } from "@/lib/queries";
import { marketSpreadView, spreadLabel } from "@/lib/betting-format";
import { isFinal, leanFor } from "@/lib/picks-proto";
import { kickoffTime } from "./format";
import { LeanPill } from "./LeanPill";
import { TeamLine } from "./TeamLine";

/** Dense one-line-per-game layout for scanning a full slate on desktop. */
export function ProtoGameRow({
  game,
  ranks,
}: {
  game: PredictionGame;
  ranks: Record<string, number>;
}) {
  const spread = leanFor(game, "spread");
  const total = leanFor(game, "total");
  const market = marketSpreadView(game.homeTeam, game.awayTeam, game.homeTeamSpreadLine);

  return (
    <li
      id={`game-${game.gameId}`}
      className="grid scroll-mt-24 gap-x-4 gap-y-2 border-b border-line px-3 py-2.5 last:border-b-0 md:grid-cols-[6.5rem_minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,1fr)] md:items-center"
    >
      <div className="whitespace-nowrap text-xs tabular-nums text-ink-muted">
        {kickoffTime(game.startDate)}
        {isFinal(game) && <span className="ml-1.5 text-[10px] uppercase text-ink-faint">Final</span>}
        {game.highConfidence && <span className="ml-1.5 text-accent" title="High confidence lean">★</span>}
      </div>
      <div className="space-y-1">
        <TeamLine name={game.awayTeam} record={game.awayRecord} rank={ranks[game.awayTeam]} score={game.awayPoints} leaning={game.spreadLean === "away"} size={20} />
        <TeamLine name={game.homeTeam} record={game.homeRecord} rank={ranks[game.homeTeam]} home score={game.homePoints} leaning={game.spreadLean === "home"} size={20} />
      </div>
      <div className="space-y-0.5 text-xs">
        <p className="tabular-nums text-ink-faint">
          Market <span className="font-mono text-ink-muted">{spreadLabel(market)}</span>
        </p>
        {spread ? <LeanPill lean={spread} compact /> : <p className="text-ink-faint">No spread lean</p>}
      </div>
      <div className="space-y-0.5 text-xs">
        <p className="tabular-nums text-ink-faint">
          Market <span className="font-mono text-ink-muted">{game.totalLine === null ? "—" : game.totalLine.toFixed(1)}</span>
        </p>
        {total ? <LeanPill lean={total} compact /> : <p className="text-ink-faint">No total lean</p>}
      </div>
    </li>
  );
}
