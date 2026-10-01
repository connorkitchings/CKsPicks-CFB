import type { PredictionGame } from "@/lib/queries";
import { coverMargin, finalMarginText, resultFor, type Lean } from "@/lib/picks-proto";
import { LeanMarker } from "./LeanMarker";
import { coverText, ResultBadge } from "./ResultBadge";

const LABEL = { spread: "Spread", total: "Total" } as const;

/**
 * One lean with its recorded result. The one-line sentence under it pairs what
 * the model had with how the game actually finished.
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
  const sentence = [
    cover,
    lean.model ? `model: ${lean.model}` : null,
    final ? `final: ${final}` : null,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <div className="space-y-0.5">
      <div className="flex items-baseline gap-2">
        <span className="w-12 shrink-0 text-[10px] font-semibold uppercase tracking-wide text-ink-faint">
          {LABEL[lean.kind]}
        </span>
        {/* The pick is never truncated: the edge and result wrap to the next line if needed. */}
        <span className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5">
          <LeanMarker lean={lean} />
          <span data-pick className="min-w-0 break-words text-sm font-semibold text-ink">{lean.pick}</span>
          <span className="whitespace-nowrap text-xs tabular-nums text-ink-muted">({lean.edge.toFixed(1)})</span>
          {grade ? <ResultBadge grade={grade} /> : <span className="text-xs text-ink-faint">Ungraded</span>}
        </span>
      </div>
      {sentence && (
        <p className="pl-[3.75rem] text-[11px] text-ink-muted">
          {sentence}
        </p>
      )}
    </div>
  );
}
