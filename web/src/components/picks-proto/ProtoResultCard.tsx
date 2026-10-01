import clsx from "clsx";
import type { PredictionGame } from "@/lib/queries";
import { leanFor, resultFor } from "@/lib/picks-proto";
import { dayShort } from "./format";
import { GameWhen } from "./GameWhen";
import { ResultLeanRow } from "./ResultLeanRow";
import { TeamPair } from "./TeamLine";

/**
 * Results card: final score first, then each lean with its graded outcome.
 * The left edge shows the outcome (all won / all lost / mixed / no lean).
 */
export function ProtoResultCard({
  game,
  ranks,
}: {
  game: PredictionGame;
  ranks: Record<string, number>;
}) {
  const spread = leanFor(game, "spread");
  const total = leanFor(game, "total");
  const grades = [
    spread ? resultFor(game, "spread") : null,
    total ? resultFor(game, "total") : null,
  ].filter((g): g is NonNullable<typeof g> => g !== null);
  const anyLean = spread !== null || total !== null;
  const allWin = grades.length > 0 && grades.every((g) => g === "win");
  const allLoss = grades.length > 0 && grades.every((g) => g === "loss");
  const homeWon = (game.homePoints ?? 0) > (game.awayPoints ?? 0);
  const awayWon = (game.awayPoints ?? 0) > (game.homePoints ?? 0);

  return (
    <li
      id={`game-${game.gameId}`}
      className={clsx(
        "scroll-mt-24 overflow-hidden rounded-xl border bg-surface-card shadow-sm",
        !anyLean && "border-dashed border-line",
        anyLean && "border-line border-l-4",
        allWin && "border-l-win",
        allLoss && "border-l-loss",
        anyLean && !allWin && !allLoss && "border-l-line-strong",
      )}
    >
      <div className={clsx("p-4", !anyLean && "opacity-75")}>
        <div className="mb-3 flex items-center gap-2 text-xs text-ink-faint">
          <GameWhen when={dayShort(game.startDate)} game={game} />
          <span className="rounded-full bg-surface-inset px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
            Final
          </span>
        </div>
        <TeamPair game={game} ranks={ranks} winner={awayWon ? "away" : homeWon ? "home" : null} />
      </div>
      <div className="space-y-2.5 border-t border-line bg-surface-inset/60 px-4 py-3">
        {anyLean ? (
          <>
            {spread && <ResultLeanRow game={game} lean={spread} />}
            {total && <ResultLeanRow game={game} lean={total} />}
          </>
        ) : (
          <p className="text-xs text-ink-faint">No lean on this game.</p>
        )}
      </div>
    </li>
  );
}
