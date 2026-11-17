"use client";

import { useContext } from "react";
import Link from "next/link";
import clsx from "clsx";
import type { Game } from "@/lib/queries";
import TeamLogo from "@/components/TeamLogo";
import { marketSpreadView, spreadLabel } from "@/lib/betting-format";
import { etClock, isTimeTbd } from "@/lib/time-et";
import { phoneTeamName } from "@/lib/team-logos";
import { isFinal } from "@/lib/team-games";
import { coverMargin, leanFor, phoneLean, resultFor } from "@/lib/slate";
import { PhoneSwap } from "@/components/ui/PhoneSwap";
import { dayShort, kickoffTime } from "./format";
import { MatchupButton, MatchupLinksContext } from "@/components/MatchupLinks";
import { MarketGameCard } from "./MarketGameCard";
import { WhereLine } from "./GameWhen";
import { LeanMarker } from "./LeanMarker";
import { LeanPill } from "./LeanPill";
import { coverText, ResultBadge } from "./ResultBadge";
import { TeamPair } from "./TeamPair";
import { AwaitingTag } from "./AwaitingTag";

function GradedCell({ game, kind }: { game: Game; kind: "spread" | "total" }) {
  const lean = leanFor(game, kind);
  if (!lean) {
    return <p className="text-xs text-ink-muted">No {kind} lean</p>;
  }
  const grade = resultFor(game, kind);
  const text = coverText(coverMargin(game, kind));
  return (
    <div className="space-y-0.5 text-xs">
      <div className="flex items-center gap-2">
        <LeanMarker lean={lean} />
        <span className="min-w-0 break-words text-sm font-semibold text-ink"><PhoneSwap full={lean.pick} phone={phoneLean(lean).pick} /></span>
        <span className="shrink-0 tabular-nums text-ink-muted">Difference: {lean.edge.toFixed(1)} pts</span>
        {grade && <ResultBadge grade={grade} />}
      </div>
      {text && <p className="tabular-nums text-ink-muted">{text}</p>}
    </div>
  );
}

function LeanCell({ game, kind }: { game: Game; kind: "spread" | "total" }) {
  const lean = leanFor(game, kind);
  return lean ? <LeanPill lean={lean} compact /> : <p className="text-xs text-ink-muted">No {kind} lean</p>;
}

/** The spread or total pick of a compact phone row: the lean, or the market line in market mode. */
function compactPick(game: Game, kind: "spread" | "total"): string {
  if (game.publicationMode === "market") {
    if (kind === "total") return game.totalLine === null ? "O/U —" : `O/U ${game.totalLine.toFixed(1)}`;
    return spreadLabel(marketSpreadView(game.homeTeam, game.awayTeam, game.homeTeamSpreadLine), phoneTeamName);
  }
  const lean = leanFor(game, kind);
  return lean ? phoneLean(lean).pick : "No lean";
}

/**
 * Phone list row: the whole row is one link to the matchup (when open). Line one is kickoff (or the
 * day, once final), then both teams with logos and any score; line two is the spread and total pick.
 */
function CompactGameRow({ game }: { game: Game }) {
  const final = isFinal(game);
  const when = final ? dayShort(game.startDate) : isTimeTbd(game.startDate) ? "TBD" : etClock(game.startDate);
  const grade = (kind: "spread" | "total") => (final ? resultFor(game, kind) : null);
  const side = (name: string, points: number | null, won: boolean) => (
    <span className="flex min-w-0 items-center gap-1">
      <TeamLogo name={name} px={16} />
      <span className={clsx("min-w-0 truncate text-sm", won ? "font-semibold text-accent-ink" : "text-ink")}>{phoneTeamName(name)}</span>
      {points !== null && <span className="shrink-0 font-mono text-sm font-semibold tabular-nums text-ink">{points}</span>}
    </span>
  );
  const awayWon = final && (game.awayPoints ?? 0) > (game.homePoints ?? 0);
  const homeWon = final && (game.homePoints ?? 0) > (game.awayPoints ?? 0);
  const open = useContext(MatchupLinksContext);
  const rowClass = "block min-h-11 px-3 py-2";
  const body = (
    <>
      <span className="flex min-w-0 items-center gap-2">
        <span className="shrink-0 whitespace-nowrap text-xs tabular-nums text-ink-muted">{when}</span>
        {side(game.awayTeam, game.awayPoints, awayWon)}
        <span aria-hidden className="shrink-0 text-xs text-ink-muted">@</span>
        {side(game.homeTeam, game.homePoints, homeWon)}
      </span>
      <span className="mt-0.5 flex flex-wrap items-center gap-x-3 text-xs text-ink-muted">
        <span className="whitespace-nowrap">{compactPick(game, "spread")}{grade("spread") && <> <ResultBadge grade={grade("spread")!} /></>}</span>
        <span className="whitespace-nowrap">{compactPick(game, "total")}{grade("total") && <> <ResultBadge grade={grade("total")!} /></>}</span>
      </span>
    </>
  );
  return (
    <li id={`game-${game.gameId}`} data-compact-row="" className="scroll-mt-24 border-b border-line last:border-b-0">
      {open ? (
        <Link href={`/matchup/${game.gameId}`} data-testid="matchup-link" className={clsx(rowClass, "focus-visible:outline-2 focus-visible:outline-accent")}>{body}</Link>
      ) : (
        <div className={rowClass}>{body}</div>
      )}
    </li>
  );
}

/** Dense one-line-per-game layout; finished games show the graded pick, others the lean. */
export function SlateGameRow({ game, now, compact = false }: { game: Game; now: Date; compact?: boolean }) {
  if (compact) return <CompactGameRow game={game} />;
  const final = isFinal(game);
  if (game.publicationMode === "market") {
    return <MarketGameCard game={game} showBetResult={final} now={now} />;
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

        </div>
        <AwaitingTag game={game} now={now} className="mt-1" />
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
