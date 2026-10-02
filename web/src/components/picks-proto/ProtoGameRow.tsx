import type { PredictionGame } from "@/lib/queries";
import { isFinal, leanFor } from "@/lib/picks-proto";
import { kickoffTime } from "./format";
import { MatchupButton } from "@/components/MatchupLinks";
import { WhereLine } from "./GameWhen";
import { LeanPill } from "./LeanPill";
import { TeamPair } from "./TeamLine";

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

  return (
    <li
      id={`game-${game.gameId}`}
      className="grid scroll-mt-24 gap-x-4 gap-y-2 border-b border-line px-3 py-2.5 last:border-b-0 md:grid-cols-[6.5rem_minmax(0,1.1fr)_minmax(0,1.2fr)_minmax(0,1.2fr)] md:items-center"
    >
      <div>
        <div className="whitespace-nowrap text-xs tabular-nums text-ink-muted">
          {kickoffTime(game.startDate)}
          {isFinal(game) && <span className="ml-1.5 text-[10px] uppercase text-ink-faint">Final</span>}
          {game.highConfidence && <span className="ml-1.5 text-accent" title="High confidence lean">★</span>}
        </div>
        <WhereLine game={game} />
        <div className="mt-1">
          <MatchupButton gameId={game.gameId} />
        </div>
      </div>
      <TeamPair game={game} ranks={ranks} size={20} />
      <div>{spread ? <LeanPill lean={spread} compact /> : <p className="text-xs text-ink-faint">No spread lean</p>}</div>
      <div>{total ? <LeanPill lean={total} compact /> : <p className="text-xs text-ink-faint">No total lean</p>}</div>
    </li>
  );
}
