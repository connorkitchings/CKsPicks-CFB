import type { Game } from "@/lib/queries";
import { isFinal } from "@/lib/team-games";
import { coverMargin, edgeTone, leanFor, phoneLean, resultFor } from "@/lib/slate";
import { PhoneSwap } from "@/components/ui/PhoneSwap";
import { dayShort, kickoffTime } from "./format";
import { MatchupButton } from "@/components/MatchupLinks";
import { MarketGameCard } from "./MarketGameCard";
import { WhereLine } from "./GameWhen";
import { LeanMarker } from "./LeanMarker";
import { LeanPill } from "./LeanPill";
import { coverText, ResultBadge } from "./ResultBadge";
import { TeamPair } from "./TeamPair";

function GradedCell({ game, kind }: { game: Game; kind: "spread" | "total" }) {
  const lean = leanFor(game, kind);
  if (!lean) return <p className="text-xs text-ink-muted">No {kind} lean</p>;
  const grade = resultFor(game, kind);
  const text = coverText(coverMargin(game, kind));
  return (
    <div className="space-y-0.5 text-xs">
      <div className="flex items-center gap-2">
        <LeanMarker lean={lean} />
        <span className="min-w-0 break-words text-sm font-semibold text-ink"><PhoneSwap full={lean.pick} phone={phoneLean(lean).pick} /></span>
        <span className={`shrink-0 tabular-nums ${edgeTone(lean.edge, lean.kind)}`}>({lean.edge.toFixed(1)})</span>
        {grade && <ResultBadge grade={grade} />}
      </div>
      {text && <p className="tabular-nums text-ink-muted">{text}</p>}
    </div>
  );
}

function LeanCell({ game, kind }: { game: Game; kind: "spread" | "total" }) {
  const lean = leanFor(game, kind);
  return <div>{lean ? <LeanPill lean={lean} compact /> : <p className="text-xs text-ink-muted">No {kind} lean</p>}</div>;
}

/** Dense one-line-per-game layout; finished games show the graded pick, others the lean. */
export function SlateGameRow({ game }: { game: Game }) {
  const final = isFinal(game);
  if (game.publicationMode === "market") {
    return <MarketGameCard game={game} showBetResult={final} />;
  }
  const homeWon = (game.homePoints ?? 0) > (game.awayPoints ?? 0);
  const awayWon = (game.awayPoints ?? 0) > (game.homePoints ?? 0);
  const Cell = final ? GradedCell : LeanCell;

  return (
    <li
      id={`game-${game.gameId}`}
      className="grid scroll-mt-24 gap-x-4 gap-y-2 border-b border-line px-3 py-2.5 last:border-b-0 md:grid-cols-[6.5rem_minmax(0,1.2fr)_minmax(0,1.1fr)_minmax(0,1.1fr)] md:items-center"
    >
      <div>
        <div className="whitespace-nowrap text-xs tabular-nums text-ink-muted">
          {final ? dayShort(game.startDate) : kickoffTime(game.startDate)}
          {game.highConfidence && <span className="ml-1.5 text-accent" title="High confidence lean">★</span>}
        </div>
        <WhereLine game={game} />
        <div className="mt-1">
          <MatchupButton gameId={game.gameId} />
        </div>
      </div>
      <TeamPair game={game} size={20} winner={final ? (awayWon ? "away" : homeWon ? "home" : null) : undefined} />
      <Cell game={game} kind="spread" />
      <Cell game={game} kind="total" />
    </li>
  );
}
