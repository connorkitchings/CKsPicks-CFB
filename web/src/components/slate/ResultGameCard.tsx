import clsx from "clsx";
import type { Game } from "@/lib/queries";
import { edgeTone, leanFor, resultFor, type Lean } from "@/lib/slate";
import { MatchupButton } from "@/components/MatchupLinks";
import { MarketGameCard } from "./MarketGameCard";
import { dayShort } from "./format";
import { GameWhen } from "./GameWhen";
import { ResultBadge } from "./ResultBadge";
import { TeamPair } from "./TeamPair";

function formatModelForecast(game: Game, lean: Lean, kind: "spread" | "total"): string {
  if (kind === "total" || !lean.team) {
    return lean.model ?? "—";
  }
  const match = lean.model?.match(/^(.+?)\s+by\s+(-?\d+(?:\.\d+)?)$/);
  if (match) {
    const margin = parseFloat(match[2]);
    if (margin < 0) {
      const opposingTeam = lean.team === game.homeTeam ? game.awayTeam : game.homeTeam;
      return `${opposingTeam} by ${Math.abs(margin).toFixed(1)}`;
    }
  }
  return lean.model ?? "—";
}

function formatModelSpreadLine(lean: Lean): string {
  if (!lean.model) return "—";
  const match = lean.model.match(/by\s+(-?\d+(?:\.\d+)?)$/);
  if (!match) return lean.model;
  const margin = parseFloat(match[1]);
  if (Math.abs(margin) < 0.05) return "PK";
  const modelLine = -margin;
  return modelLine > 0 ? `+${modelLine.toFixed(1)}` : modelLine.toFixed(1);
}

function ResultBetCell({
  game,
  title,
  lean,
  kind,
}: {
  game: Game;
  title: string;
  lean: Lean | null;
  kind: "spread" | "total";
}) {
  if (!lean) {
    return (
      <div className="px-3 pt-2 pb-2.5 text-center">
        <div className="mb-0.5 text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
          {title}
        </div>
        <p className="text-xs text-ink-faint">No lean</p>
      </div>
    );
  }

  const grade = resultFor(game, kind);
  const modelText = formatModelForecast(game, lean, kind);
  const modelSpreadLine = kind === "spread" ? formatModelSpreadLine(lean) : null;

  return (
    <div className="px-3 pt-2 pb-2.5 text-center">
      <div className="mb-0.5 flex items-center justify-center gap-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-faint">
          {title}
        </span>
        {grade ? (
          <ResultBadge grade={grade} />
        ) : (
          <span className="text-[10px] text-ink-faint">Ungraded</span>
        )}
      </div>

      <div className="mb-1 flex min-w-0 items-baseline justify-center gap-1.5">
        {kind === "total" && (
          <span aria-hidden className="shrink-0 text-xs leading-none text-accent">
            {lean.dir === "over" ? "▲" : "▼"}
          </span>
        )}
        <span data-pick className="min-w-0 break-words text-sm font-semibold text-ink">
          {lean.pick}
        </span>
        {lean.source && (
          <span className="hidden shrink-0 text-xs font-normal text-ink-faint sm:inline">
            ({lean.source})
          </span>
        )}
      </div>

      <div className="flex items-baseline justify-center truncate text-xs text-ink-muted">
        {kind === "spread" ? (
          <>
            <span className="sm:hidden">
              <span className="text-ink-faint">Model:</span>{" "}
              <span className="font-medium text-ink">{modelSpreadLine}</span>
            </span>
            <span className="hidden sm:inline">
              <span className="text-ink-faint">Model:</span>{" "}
              <span className="font-medium text-ink">{modelText}</span>
            </span>
          </>
        ) : (
          <>
            <span className="text-ink-faint">Model:</span>{" "}
            <span className="ml-1 font-medium text-ink">{modelText}</span>
          </>
        )}
        <span className={clsx("ml-1 shrink-0 font-semibold tabular-nums", edgeTone(lean.edge, kind))}>
          (+{lean.edge.toFixed(1)})
        </span>
      </div>
    </div>
  );
}

/**
 * Results card: final score first, then a 2-column horizontal split
 * for Spread and Total leans with outcome badges.
 * Market-mode games fail closed to the market-only card.
 */
export function ResultGameCard({
  game,
  showBetResult = true,
}: {
  game: Game;
  showBetResult?: boolean;
}) {
  if (game.publicationMode === "market") {
    return <MarketGameCard game={game} showBetResult={showBetResult} />;
  }
  const spread = leanFor(game, "spread");
  const total = leanFor(game, "total");
  const anyLean = spread !== null || total !== null;
  const homeWon = (game.homePoints ?? 0) > (game.awayPoints ?? 0);
  const awayWon = (game.awayPoints ?? 0) > (game.homePoints ?? 0);

  return (
    <li
      id={`game-${game.gameId}`}
      className={clsx(
        "scroll-mt-24 overflow-hidden rounded-xl border bg-surface-card shadow-sm transition-all duration-150 hover:border-line-strong hover:shadow-md",
        anyLean ? "border-line" : "border-dashed border-line",
      )}
    >
      <div className={clsx("p-4", !anyLean && "opacity-75")}>
        <div className="mb-3 flex items-center justify-between text-xs text-ink-faint">
          <div className="flex items-center gap-2">
            <GameWhen when={dayShort(game.startDate)} game={game} />
          </div>
          <div className="flex items-center gap-2">
            <MatchupButton gameId={game.gameId} />
            <span className="rounded-full bg-surface-inset px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
              Final
            </span>
          </div>
        </div>
        <TeamPair game={game} winner={awayWon ? "away" : homeWon ? "home" : null} />
      </div>

      <div className="border-t border-line bg-surface-inset/50">
        <div className="grid grid-cols-2 divide-x divide-line/60">
          <ResultBetCell game={game} title="Spread" lean={spread} kind="spread" />
          <ResultBetCell game={game} title="Total" lean={total} kind="total" />
        </div>
      </div>
    </li>
  );
}
