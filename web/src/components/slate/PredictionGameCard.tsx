import clsx from "clsx";
import type { PredictionGame } from "@/lib/queries";
import { Card } from "@/components/ui/Card";
import { coverMargin, edgeTone, isFinal, leanFor, modelCrossesMarket, phoneLean, resultFor, venueLabel, type Lean } from "@/lib/slate";
import { PhoneSwap } from "@/components/ui/PhoneSwap";
import { MatchupButton } from "@/components/MatchupLinks";
import { phoneTeamName } from "@/lib/team-logos";
import { kickoffTime, dayShort } from "./format";
import { TeamPair } from "./TeamPair";
import { ResultBadge, coverText } from "./ResultBadge";

function modelNumber(lean: Lean): string {
  if (lean.kind === "total") return lean.model ?? "—";
  const match = lean.model?.match(/by\s+(-?\d+(?:\.\d+)?)$/);
  if (!match) return lean.model ?? "—";
  const margin = Number(match[1]);
  if (Math.abs(margin) < 0.05) return "PK";
  return -margin > 0 ? `+${(-margin).toFixed(1)}` : (-margin).toFixed(1);
}

function BetCell({ game, kind, results }: {
  game: PredictionGame;
  kind: "spread" | "total";
  results: boolean;
}) {
  const lean = leanFor(game, kind);
  const grade = results ? resultFor(game, kind) : null;
  const cover = results ? coverText(coverMargin(game, kind)) : null;
  const missingLine = kind === "spread" ? game.homeTeamSpreadLine === null : game.totalLine === null;
  return (
    <div className="min-w-0 px-3 py-2.5">
      <div className="mb-1 flex items-center justify-between gap-1.5 text-xs font-medium text-ink-muted">
        <span className="uppercase tracking-wider">{kind === "spread" ? "Spread" : "Total"}</span>
        {grade ? <ResultBadge grade={grade} /> : results ? <span>Ungraded</span> : lean?.source ? <span className="truncate text-ink-muted">{lean.source}</span> : null}
      </div>
      {lean ? <>
        <p data-pick className={clsx("break-words text-sm font-semibold leading-snug", results ? "text-ink" : "text-accent-ink")}><PhoneSwap full={lean.pick} phone={phoneLean(lean).pick} /></p>
        <p className="mt-0.5 flex flex-wrap items-baseline gap-x-1.5 text-xs tabular-nums text-ink-muted">
          <span>
            Model:{" "}
            <span className="font-medium text-ink">
              {lean.team && modelCrossesMarket(lean)
                ? <PhoneSwap full={`${lean.team} ${modelNumber(lean)}`} phone={`${phoneTeamName(lean.team)} ${modelNumber(lean)}`} />
                : modelNumber(lean)}
            </span>
          </span>
          <span className={clsx("font-semibold", edgeTone(lean.edge, kind))}>({lean.edge.toFixed(1)})</span>
        </p>
        {results && (lean.source || cover) && (
          <p className="mt-0.5 text-xs text-ink-muted">
            {[lean.source, cover].filter(Boolean).join(" · ")}
          </p>
        )}
      </> : <p className="text-sm text-ink-muted">{missingLine ? "No market line" : "No lean"}</p>}
    </div>
  );
}

/** A shared card shell; Results adds winner emphasis and grading content. */
export function PredictionGameCard({ game, results = false }: {
  game: PredictionGame;
  results?: boolean;
}) {
  const final = isFinal(game);
  const awayWon = (game.awayPoints ?? 0) > (game.homePoints ?? 0);
  const homeWon = (game.homePoints ?? 0) > (game.awayPoints ?? 0);
  const where = venueLabel(game.venueCity, game.venueState);
  const winner = results && final ? (awayWon ? "away" : homeWon ? "home" : null) : null;
  return (
    <Card as="li" id={`game-${game.gameId}`} padding="none" className="scroll-mt-12 max-sm:scroll-mt-0 overflow-hidden">
      <div className="px-3 pb-3 pt-2">
        <div className="mb-1 flex items-center justify-between gap-2 text-xs text-ink-muted">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium tabular-nums">{results ? dayShort(game.startDate) : kickoffTime(game.startDate)}</span>
            {where && <span>· {where}</span>}
            {game.neutralSite && <span>· Neutral site</span>}
            {final && <span className="rounded bg-surface-inset px-1.5 py-0.5 text-xs font-semibold">Final</span>}
            {game.highConfidence && <span className="text-sm text-accent-ink" aria-label="High confidence lean" title="High confidence lean">★</span>}
          </div>
          <MatchupButton gameId={game.gameId} />
        </div>
        <TeamPair game={game} winner={winner} />
      </div>
      <div className="grid grid-cols-2 divide-x divide-line border-t border-line bg-surface-inset/50">
        <BetCell game={game} kind="spread" results={results} />
        <BetCell game={game} kind="total" results={results} />
      </div>
    </Card>
  );
}
