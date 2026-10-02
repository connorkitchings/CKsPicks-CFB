import clsx from "clsx";
import type { PredictionGame } from "@/lib/queries";
import { marketSpreadView, modelSpreadView, spreadLabel } from "@/lib/betting-format";
import { isFinal, leanFor } from "@/lib/picks-proto";
import { MatchupButton } from "@/components/MatchupLinks";
import { kickoffTime } from "./format";
import { GameWhen } from "./GameWhen";
import { LeanPill } from "./LeanPill";
import { TeamPair } from "./TeamLine";

/**
 * Prototype game card: who is playing, then each lean with its direction and
 * edge. The market and model numbers live in the lean sentence, not a second
 * table, so each number appears once. Games with no lean recede.
 */
export function ProtoGameCard({
  game,
  ranks,
}: {
  game: PredictionGame;
  ranks: Record<string, number>;
}) {
  const spread = leanFor(game, "spread");
  const total = leanFor(game, "total");
  const anyLean = spread !== null || total !== null;
  const final = isFinal(game);
  const strongest = Math.max(spread?.tier ?? 0, total?.tier ?? 0);

  return (
    <li
      id={`game-${game.gameId}`}
      className={clsx(
        "scroll-mt-24 overflow-hidden rounded-xl border bg-surface-card shadow-sm",
        anyLean
          ? clsx("border-line border-l-4", strongest === 3 ? "border-l-accent" : "border-l-accent-line")
          : "border-dashed border-line",
      )}
    >
      <div className={clsx("p-4", !anyLean && "opacity-75")}>
        <div className="mb-3 flex items-center gap-2 text-xs text-ink-faint">
          <GameWhen when={`${kickoffTime(game.startDate)} ET`} game={game} />
          {game.highConfidence && (
            <span className="text-sm leading-none text-accent" title="High confidence lean" aria-label="High confidence lean">
              ★
            </span>
          )}
          <span className="ml-auto">
            <MatchupButton gameId={game.gameId} />
          </span>
          {final && (
            <span className="rounded-full bg-surface-inset px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
              Final
            </span>
          )}
        </div>
        <TeamPair game={game} ranks={ranks} />
      </div>

      <div className="space-y-2.5 border-t border-line bg-surface-inset/60 px-4 py-3">
        {anyLean ? (
          <>
            {spread && <LeanPill lean={spread} />}
            {total && <LeanPill lean={total} />}
          </>
        ) : (
          <div className="space-y-0.5 text-xs text-ink-faint">
            <p className="font-medium">No lean</p>
            <p>
              Spread: market {spreadLabel(marketSpreadView(game.homeTeam, game.awayTeam, game.homeTeamSpreadLine))}, model{" "}
              {spreadLabel(modelSpreadView(game.homeTeam, game.awayTeam, game.predictedSpread))}
            </p>
            <p>
              Total: market {game.totalLine === null ? "—" : game.totalLine.toFixed(1)}, model{" "}
              {game.predictedTotal === null ? "—" : game.predictedTotal.toFixed(1)}
            </p>
          </div>
        )}
      </div>
    </li>
  );
}
