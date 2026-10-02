import { clsx } from "clsx";
import TeamLogo from "@/components/TeamLogo";
import { MatchupButton } from "@/components/MatchupLinks";
import { BetTable } from "../BetTable";
import type { Game } from "@/lib/queries";

import {
  marketSpreadView,
  spreadLabel,
} from "@/lib/betting-format";

function ResultCell({ result }: { result: "win" | "loss" | "push" | null }) {
  if (result === null) {
    return <span className="text-ink-faint">—</span>;
  }
  return (
    <span
      className={clsx(
        "inline-block rounded px-1.5 py-0.5 text-[11px] font-medium",
        result === "win" && "bg-win-soft text-win",
        result === "loss" && "bg-loss-soft text-loss",
        result === "push" && "bg-surface-inset text-ink-muted",
      )}
    >
      {result === "win" ? "Win" : result === "loss" ? "Loss" : "Push"}
    </span>
  );
}

/**
 * Fail-closed market-mode card: same shell as the lean cards, but the table
 * shows Market columns only — no model numbers, no leans, no invented output.
 * DOM is unchanged from the former MarketGameRow so existing market-mode
 * assertions keep passing.
 */
export function MarketGameCard({
  game,
  showBetResult = true,
}: {
  game: Extract<Game, { publicationMode: "market" }>;
  showBetResult?: boolean;
}) {
  const hasResults = game.homePoints !== null && game.awayPoints !== null;
  const marketSpread = marketSpreadView(
    game.homeTeam,
    game.awayTeam,
    game.homeTeamSpreadLine,
  );

  return (
    <li className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
      <div className="mb-3 flex items-center gap-2 text-xs text-ink-faint">
        <span>{formatKickoff(game.startDate)}</span>
        {hasResults && (
          <span className="rounded-full bg-surface-inset px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
            Final
          </span>
        )}
        <span className="ml-auto">
          <MatchupButton gameId={game.gameId} />
        </span>
      </div>
      <div className="space-y-1.5">
        <TeamLine
          name={game.awayTeam}
          record={game.awayRecord}
          score={game.awayPoints}
          highlighted={false}
        />
        <TeamLine
          name={game.homeTeam}
          record={game.homeRecord}
          home
          score={game.homePoints}
          highlighted={false}
        />
      </div>
      <BetTable
        ariaLabel="Market and results"
        tableClassName="mt-3 w-full tabular-nums text-[11px] sm:text-xs"
        headerCellClassName="pl-2 text-right"
        bodyCellClassName={[
          "py-1.5 pl-2 text-right font-mono tabular-nums text-ink",
          ...(showBetResult ? ["py-1.5 pl-2 text-right text-ink"] : []),
        ]}
        columns={[
          { header: "Market" },
          ...(showBetResult ? [{ header: "Bet Result" }] : []),
        ]}
        rows={[
          {
            label: "Spread",
            cells: [
              spreadLabel(marketSpread),
              ...(showBetResult
                ? [<ResultCell key="result" result={game.spreadResult} />]
                : []),
            ],
          },
          {
            label: "Total",
            cells: [
              game.totalLine === null
                ? "O/U —"
                : `O/U ${game.totalLine.toFixed(1)}`,
              ...(showBetResult
                ? [<ResultCell key="result" result={game.totalResult} />]
                : []),
            ],
          },
        ]}
      />
    </li>
  );
}

function formatKickoff(startDate: Date): string {
  return startDate.toLocaleString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  });
}

function TeamLine({
  name,
  record = null,
  home = false,
  score,
  highlighted,
}: {
  name: string;
  /** Season W-L as of kickoff (e.g. "1-0"); null hides the marker. */
  record?: string | null;
  home?: boolean;
  score: number | null;
  highlighted: boolean;
}) {
  return (
    <div className="flex items-center gap-2.5">
      <TeamLogo name={name} px={28} decorative={false} />
      <span className={clsx("min-w-0 truncate text-sm text-ink", highlighted && "font-semibold")}>
        {name}
      </span>
      {record && (
        <span className="text-xs tabular-nums text-ink-faint">({record})</span>
      )}
      {home && (
        <span className="text-[10px] uppercase tracking-wide text-ink-faint">
          home
        </span>
      )}
      {score !== null && (
        <span className="ml-auto font-mono text-base font-semibold tabular-nums text-ink">
          {score}
        </span>
      )}
    </div>
  );
}
