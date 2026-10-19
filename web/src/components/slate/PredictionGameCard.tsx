import clsx from "clsx";
import type { PredictionGame } from "@/lib/queries";
import { coverMargin, edgeTone, isFinal, leanFor, resultFor, venueLabel, type Lean } from "@/lib/slate";
import { MatchupButton } from "@/components/MatchupLinks";
import { Disclosure } from "@/components/ui/Disclosure";
import { kickoffTime, dayShort } from "./format";
import { TeamPair } from "./TeamPair";
import { ResultBadge, coverText } from "./ResultBadge";

function modelForecast(game: PredictionGame, lean: Lean): string {
  if (lean.kind !== "spread" || !lean.team) return lean.model ?? "—";
  const match = lean.model?.match(/^(.+?)\s+by\s+(-?\d+(?:\.\d+)?)$/);
  if (match && Number(match[2]) < 0) {
    return `${lean.team === game.homeTeam ? game.awayTeam : game.homeTeam} by ${Math.abs(Number(match[2])).toFixed(1)}`;
  }
  return lean.model ?? "—";
}

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
  const missingLine = kind === "spread" ? game.homeTeamSpreadLine === null : game.totalLine === null;
  return (
    <div className="min-w-0 px-3 py-2.5">
      <div className="mb-1 flex flex-wrap items-center gap-1.5 text-xs font-medium text-ink-muted">
        <span>{kind === "spread" ? "Spread" : "Total"}</span>
        {grade ? <ResultBadge grade={grade} /> : results && <span>Ungraded</span>}
      </div>
      {lean ? <>
        <p data-pick className={clsx("break-words text-sm font-semibold", results ? "text-ink" : "text-accent-ink")}>{lean.pick}</p>
        <p className="mt-1 flex flex-wrap gap-x-1 text-sm tabular-nums text-ink-muted">
          <span>Model: <span className="font-medium text-ink">{modelNumber(lean)}</span></span>
          <span className={clsx("font-medium", edgeTone(lean.edge, kind))}>(+{lean.edge.toFixed(1)})</span>
        </p>
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
    <li id={`game-${game.gameId}`} className="scroll-mt-12 overflow-hidden rounded-xl border border-line bg-surface-card shadow-sm">
      <div className="px-3 pb-3 pt-2">
        <div className="mb-1 flex items-center justify-between gap-2 text-xs text-ink-muted">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium tabular-nums">{results ? dayShort(game.startDate) : `${kickoffTime(game.startDate)} ET`}</span>
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
      <Disclosure title="Game details" className="rounded-none border-0 border-t border-line">
        {where && <p className="mb-1">· {where}</p>}
        {game.neutralSite && <p className="mb-1">Neutral site</p>}
        <div className="space-y-2">
          {(["spread", "total"] as const).map((kind) => {
            const lean = leanFor(game, kind);
            if (!lean) return null;
            const cover = results ? coverText(coverMargin(game, kind)) : null;
            return <p key={kind}>
              <span className="font-semibold text-ink">{kind === "spread" ? "Spread" : "Total"}: </span>
              Model: {modelForecast(game, lean)}{lean.source && <> · Line source: ({lean.source})</>}{cover && <> · {cover}</>}
            </p>;
          })}
        </div>
        <p className="mt-2 text-xs">The number in parentheses after the model is its edge: how many points the model differs from the market.</p>
      </Disclosure>
    </li>
  );
}
