import type { PredictionGame } from "@/lib/queries";
import { venueLabel } from "@/lib/picks-proto";

/**
 * The "when and where" line of a card: the time (or date), then the game's
 * city and state when known, plus a neutral-site note. Renders nothing extra
 * when the location is unknown.
 */
export function GameWhen({ when, game }: { when: string; game: PredictionGame }) {
  const where = venueLabel(game.venueCity, game.venueState);
  return (
    <>
      <span className="shrink-0 font-medium tabular-nums text-ink-muted">{when}</span>
      {where && (
        <span className="min-w-0 truncate" title={where}>
          · {where}
        </span>
      )}
      {game.neutralSite && (
        <span className="shrink-0 rounded-full bg-surface-inset px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
          Neutral site
        </span>
      )}
    </>
  );
}

/** Compact second line for dense list rows (location and neutral-site note). */
export function WhereLine({ game }: { game: PredictionGame }) {
  const where = venueLabel(game.venueCity, game.venueState);
  if (!where && !game.neutralSite) return null;
  return (
    <div className="mt-0.5 max-w-[6.5rem] truncate text-[11px] text-ink-faint" title={where}>
      {where}
      {game.neutralSite && <span className="ml-1 uppercase">· Neutral</span>}
    </div>
  );
}
