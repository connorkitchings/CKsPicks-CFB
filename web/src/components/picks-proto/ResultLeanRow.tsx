import type { PredictionGame } from "@/lib/queries";
import { coverMargin, resultFor, type Lean } from "@/lib/picks-proto";
import { coverText, ResultBadge } from "./ResultBadge";

const LABEL = { spread: "Spread", total: "Total" } as const;

/** One lean with its recorded result and how it landed relative to the number. */
export function ResultLeanRow({ game, lean }: { game: PredictionGame; lean: Lean }) {
  const grade = resultFor(game, lean.kind);
  const cover = coverMargin(game, lean.kind);
  const detail = [
    coverText(cover),
    lean.kind === "total" && game.homePoints !== null && game.awayPoints !== null
      ? `final total ${game.homePoints + game.awayPoints}`
      : null,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <div className="flex items-center gap-2">
      <span className="w-12 shrink-0 text-[10px] font-semibold uppercase tracking-wide text-ink-faint">
        {LABEL[lean.kind]}
      </span>
      <span className="min-w-0 truncate text-sm font-semibold text-ink">{lean.pick}</span>
      {grade ? <ResultBadge grade={grade} /> : <span className="text-xs text-ink-faint">Ungraded</span>}
      {detail && <span className="ml-auto shrink-0 text-xs tabular-nums text-ink-muted">{detail}</span>}
    </div>
  );
}
