import clsx from "clsx";
import type { PredictionGame } from "@/lib/queries";
import { marketSpreadView, modelSpreadView, spreadLabel } from "@/lib/betting-format";
import { isFinal, leanFor } from "@/lib/picks-proto";
import { kickoffTime } from "./format";
import { LeanPill } from "./LeanPill";
import { TeamLine } from "./TeamLine";

const th = "text-right text-[10px] font-medium uppercase tracking-wide text-ink-faint";

/**
 * Prototype game card: a score/teams block, a small market-vs-model grid, and
 * a pick strip that makes the lean the focal point. Games with no lean recede.
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
  const market = marketSpreadView(game.homeTeam, game.awayTeam, game.homeTeamSpreadLine);
  const model = modelSpreadView(game.homeTeam, game.awayTeam, game.predictedSpread);

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
          <span className="font-medium tabular-nums text-ink-muted">{kickoffTime(game.startDate)} ET</span>
          {game.highConfidence && (
            <span className="text-sm leading-none text-accent" title="High confidence lean" aria-label="High confidence lean">
              ★
            </span>
          )}
          {final && (
            <span className="rounded-full bg-surface-inset px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
              Final
            </span>
          )}
        </div>

        <div className="space-y-1.5">
          <TeamLine
            name={game.awayTeam}
            record={game.awayRecord}
            rank={ranks[game.awayTeam]}
            score={game.awayPoints}
            leaning={game.spreadLean === "away"}
          />
          <TeamLine
            name={game.homeTeam}
            record={game.homeRecord}
            rank={ranks[game.homeTeam]}
            home
            score={game.homePoints}
            leaning={game.spreadLean === "home"}
          />
        </div>

        <div className="mt-3 grid grid-cols-[3.5rem_1fr_1fr] items-baseline gap-y-1 text-xs tabular-nums">
          <span />
          <span className={th}>Market</span>
          <span className={th}>Model</span>
          <span className="text-ink-muted">Spread</span>
          <span className="text-right font-mono text-ink">{spreadLabel(market)}</span>
          <span className="text-right font-mono text-ink">{spreadLabel(model)}</span>
          <span className="text-ink-muted">Total</span>
          <span className="text-right font-mono text-ink">
            {game.totalLine === null ? "—" : game.totalLine.toFixed(1)}
          </span>
          <span className="text-right font-mono text-ink">
            {game.predictedTotal === null ? "—" : game.predictedTotal.toFixed(1)}
          </span>
        </div>
      </div>

      <div className="space-y-1.5 border-t border-line bg-surface-inset/60 px-4 py-2.5">
        {anyLean ? (
          <>
            {spread && <LeanPill lean={spread} />}
            {total && <LeanPill lean={total} />}
          </>
        ) : (
          <p className="text-xs text-ink-faint">No lean — model is within the threshold of the market.</p>
        )}
      </div>
    </li>
  );
}
