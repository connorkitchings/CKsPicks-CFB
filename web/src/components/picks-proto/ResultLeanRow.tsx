import type { PredictionGame } from "@/lib/queries";
import { coverMargin, finalMarginText, resultFor, type Lean } from "@/lib/picks-proto";
import { LeanMarker } from "./LeanMarker";
import { coverText, ResultBadge } from "./ResultBadge";

const LABEL = { spread: "Spread", total: "Total" } as const;

/**
 * One lean with its recorded result. The sentence under it pairs what the pick
 * meant and what the model had with how the game actually finished.
 */
export function ResultLeanRow({ game, lean }: { game: PredictionGame; lean: Lean }) {
  const grade = resultFor(game, lean.kind);
  const cover = coverText(coverMargin(game, lean.kind));
  const final =
    lean.kind === "spread" && lean.team
      ? finalMarginText(game, lean.team)
      : game.homePoints !== null && game.awayPoints !== null
        ? `total ${game.homePoints + game.awayPoints}`
        : null;
  return (
    <div className="space-y-0.5">
      <div className="flex items-center gap-2">
        <span className="w-12 shrink-0 text-[10px] font-semibold uppercase tracking-wide text-ink-faint">
          {LABEL[lean.kind]}
        </span>
        <LeanMarker lean={lean} />
        <span className="min-w-0 truncate text-sm font-semibold text-ink">{lean.pick}</span>
        {grade ? <ResultBadge grade={grade} /> : <span className="text-xs text-ink-faint">Ungraded</span>}
        {cover && <span className="ml-auto shrink-0 text-xs tabular-nums text-ink-muted">{cover}</span>}
      </div>
      <p className="pl-[3.75rem] text-xs text-ink-muted">
        {lean.explain}
        {lean.model && <> · model: {lean.model}</>}
        {final && <> · final: {final}</>}
      </p>
    </div>
  );
}
