import Image from "next/image";
import { Fragment } from "react";
import { clsx } from "clsx";
import { logoUrl } from "@/lib/teams";
import { BetTable } from "./BetTable";
import type { Game } from "@/lib/queries";

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

function signedSpread(n: number): string {
  return n > 0 ? `+${n.toFixed(1)}` : n.toFixed(1);
}

/** Favorite-relative spread view: the team the number favors plus its line. */
type SpreadView = { team: string; line: number } | "PK" | null;

/** Market line is the home team's spread: -home favorite, +home dog. */
function marketSpreadView(
  homeTeam: string,
  awayTeam: string,
  homeLine: number | null,
): SpreadView {
  if (homeLine === null) return null;
  if (homeLine === 0) return "PK";
  return homeLine < 0
    ? { team: homeTeam, line: homeLine }
    : { team: awayTeam, line: -homeLine };
}

/** predictedSpread is the home margin (+home wins); flip to favorite-relative. */
function modelSpreadView(
  homeTeam: string,
  awayTeam: string,
  predictedSpread: number | null,
): SpreadView {
  if (predictedSpread === null) return null;
  if (predictedSpread === 0) return "PK";
  return predictedSpread > 0
    ? { team: homeTeam, line: -predictedSpread }
    : { team: awayTeam, line: predictedSpread };
}

function spreadLabel(view: SpreadView): string {
  if (view === null) return "—";
  if (view === "PK") return "PK";
  return `${view.team} ${signedSpread(view.line)}`;
}

/** Signed difference between the displayed model and market spread numbers. */
function spreadEdge(model: SpreadView, market: SpreadView): number | null {
  if (
    model === null ||
    market === null ||
    model === "PK" ||
    market === "PK"
  ) {
    return null;
  }
  return model.line - market.line;
}

/** Signed difference between the model and market totals. */
function totalEdge(
  predictedTotal: number | null,
  totalLine: number | null,
): number | null {
  if (predictedTotal === null || totalLine === null) return null;
  return predictedTotal - totalLine;
}

/** The bet the model would place: the leaned team and the line it would take. */
function spreadBetLabel(
  homeTeam: string,
  awayTeam: string,
  lean: "home" | "away" | null,
  homeLine: number | null,
): string | null {
  if (lean === null || homeLine === null) return null;
  return lean === "home"
    ? `${homeTeam} ${signedSpread(homeLine)}`
    : `${awayTeam} ${signedSpread(-homeLine)}`;
}

function totalBetLabel(
  lean: "over" | "under" | null,
  totalLine: number | null,
): string | null {
  if (lean === null || totalLine === null) return null;
  return `${lean === "over" ? "↑ Over" : "↓ Under"} ${totalLine.toFixed(1)}`;
}

/** Editorial cutoffs for edge coloring (points): below LOW is faint,
 * LOW–HIGH is medium, above HIGH is strong. Not derived from a fitted
 * threshold — retune against observed spread/total MAE if they change. */
const SPREAD_EDGE_LOW = 3;
const SPREAD_EDGE_HIGH = 8;
const TOTAL_EDGE_LOW = 2;
const TOTAL_EDGE_HIGH = 7;

/** Color reflects the size of the disagreement; the signed number preserves direction. */
function edgeTone(edge: number, target: "spread" | "total"): string {
  const magnitude = Math.abs(edge);
  const [lowThreshold, highThreshold] =
    target === "spread"
      ? [SPREAD_EDGE_LOW, SPREAD_EDGE_HIGH]
      : [TOTAL_EDGE_LOW, TOTAL_EDGE_HIGH];
  if (magnitude < lowThreshold) return "edge-low";
  if (magnitude <= highThreshold) return "edge-medium";
  return "edge-high";
}

/** Quiet parenthetical in the Model cell: how far model sits from market. */
function EdgeNote({ edge, target }: { edge: number | null; target: "spread" | "total" }) {
  if (edge === null) return null;
  const note = `(${signedSpread(edge)})`;
  return (
    <span
      className={clsx("ml-1 font-medium", edgeTone(edge, target))}
      title="Model minus market"
      aria-label={`Model minus market ${note}`}
    >
      {note}
    </span>
  );
}

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
 * Matchup-centric game card. One shell serves both publication modes: the
 * box-score block (logos, names, final scores) is always present, followed by
 * a compact market-vs-model table. Predictions mode shows Market / Model /
 * Model Bet / Bet Result; market mode (fail-closed, no model output) shows
 * Market / Bet Result only.
 */
export function GameRow({ game }: { game: Game }) {
  if (game.publicationMode === "market") {
    return <MarketGameRow game={game} />;
  }
  const hasAnyLine =
    game.homeTeamSpreadLine !== null || game.totalLine !== null;
  const marketSpread = marketSpreadView(
    game.homeTeam,
    game.awayTeam,
    game.homeTeamSpreadLine,
  );
  const modelSpread = modelSpreadView(
    game.homeTeam,
    game.awayTeam,
    game.predictedSpread,
  );
  const spreadBet = spreadBetLabel(
    game.homeTeam,
    game.awayTeam,
    game.spreadLean,
    game.homeTeamSpreadLine,
  );
  const totalBet = totalBetLabel(game.totalLean, game.totalLine);

  return (
    <li className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
      {/* Meta row: kickoff + high-confidence marker */}
      <div className="mb-3 flex items-center justify-between gap-2 text-xs text-ink-faint">
        <span>{formatKickoff(game.startDate)}</span>
        {game.highConfidence && (
          <span
            className="text-sm leading-none text-accent"
            title="High confidence lean"
            aria-label="High confidence lean"
          >
            ★
          </span>
        )}
      </div>

      {/* Box score: logos, teams, finals */}
      <div className="space-y-1.5">
        <TeamLine
          name={game.awayTeam}
          record={game.awayRecord}
          score={game.awayPoints}
          highlighted={game.spreadLean === "away"}
        />
        <TeamLine
          name={game.homeTeam}
          record={game.homeRecord}
          home
          score={game.homePoints}
          highlighted={game.spreadLean === "home"}
        />
      </div>

      {/* Desktop keeps the full comparison table; phone cards use three value columns. */}
      <div className="mt-3 hidden sm:block">
        <BetTable
          ariaLabel="Market and model comparison"
          tableClassName="w-full tabular-nums text-xs"
          headerCellClassName="pl-2 text-right"
          bodyCellClassName="py-1.5 pl-2 text-right font-mono tabular-nums"
          columns={[
            { header: "Market" },
            { header: "Model" },
            { header: "Model Bet" },
            { header: "Bet Result" },
          ]}
          rows={[
            {
              label: "Spread",
              cells: [
                spreadLabel(marketSpread),
                <Fragment key="model">
                  {spreadLabel(modelSpread)}
                  <EdgeNote edge={spreadEdge(modelSpread, marketSpread)} target="spread" />
                </Fragment>,
                spreadBet ? <span key="bet" className="font-medium text-accent-ink">{spreadBet}</span> : <span key="bet" className="text-ink-faint">No lean</span>,
                <ResultCell key="result" result={game.spreadResult} />,
              ],
            },
            {
              label: "Total",
              cells: [
                game.totalLine === null ? "—" : game.totalLine.toFixed(1),
                <Fragment key="model">
                  {game.predictedTotal === null ? "—" : game.predictedTotal.toFixed(1)}
                  <EdgeNote edge={totalEdge(game.predictedTotal, game.totalLine)} target="total" />
                </Fragment>,
                totalBet ? <span key="bet" className="font-medium text-accent-ink">{totalBet}</span> : <span key="bet" className="text-ink-faint">No lean</span>,
                <ResultCell key="result" result={game.totalResult} />,
              ],
            },
          ]}
        />
      </div>
      <div className="mt-3 sm:hidden">
        <BetTable
          ariaLabel="Market and model comparison"
          tableClassName="w-full table-fixed tabular-nums text-[11px]"
          rowHeaderWidthClass="w-[16%] text-left"
          headerCellClassName="pl-2 text-right"
          bodyCellClassName={[
            "py-1.5 pl-2 text-right font-mono tabular-nums text-ink break-words",
            "py-1.5 pl-2 text-right font-mono tabular-nums text-ink break-words",
            "break-words py-1.5 pl-2 text-right font-mono tabular-nums",
          ]}
          columns={[
            { header: "Market", widthClass: "w-[28%]" },
            { header: "Model", widthClass: "w-[28%]" },
            { header: "Bet", widthClass: "w-[28%]" },
          ]}
          rows={[
            {
              label: "Spread",
              cells: [
                spreadLabel(marketSpread),
                <Fragment key="model">
                  {spreadLabel(modelSpread)}
                  <EdgeNote edge={spreadEdge(modelSpread, marketSpread)} target="spread" />
                </Fragment>,
                <Fragment key="bet">
                  {spreadBet ? <span className="font-medium text-accent-ink">{spreadBet}</span> : <span className="text-ink-faint">No lean</span>}
                  {game.spreadResult && <div className="mt-1"><ResultCell result={game.spreadResult} /></div>}
                </Fragment>,
              ],
            },
            {
              label: "Total",
              cells: [
                game.totalLine === null ? "—" : game.totalLine.toFixed(1),
                <Fragment key="model">
                  {game.predictedTotal === null ? "—" : game.predictedTotal.toFixed(1)}
                  <EdgeNote edge={totalEdge(game.predictedTotal, game.totalLine)} target="total" />
                </Fragment>,
                <Fragment key="bet">
                  {totalBet ? <span className="font-medium text-accent-ink">{totalBet}</span> : <span className="text-ink-faint">No lean</span>}
                  {game.totalResult && <div className="mt-1"><ResultCell result={game.totalResult} /></div>}
                </Fragment>,
              ],
            },
          ]}
        />
      </div>

      {!hasAnyLine && (
        <p className="mt-2 text-xs text-ink-faint">
          No market line — model prediction shown, no lean.
        </p>
      )}
    </li>
  );
}

/** Market-mode card: same shell; the table omits model columns (fail-closed). */
function MarketGameRow({
  game,
}: {
  game: Extract<Game, { publicationMode: "market" }>;
}) {
  const hasResults = game.homePoints !== null && game.awayPoints !== null;
  const marketSpread = marketSpreadView(
    game.homeTeam,
    game.awayTeam,
    game.homeTeamSpreadLine,
  );
  return (
    <li className="rounded-xl border border-line bg-surface-card p-4 shadow-sm">
      <div className="mb-3 flex items-center justify-between gap-2 text-xs text-ink-faint">
        <span>{formatKickoff(game.startDate)}</span>
        {hasResults && (
          <span className="rounded-full bg-surface-inset px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-ink-muted">
            Final
          </span>
        )}
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
        bodyCellClassName="py-1.5 pl-2 text-right font-mono tabular-nums text-ink"
        columns={[{ header: "Market" }, { header: "Bet Result" }]}
        rows={[
          {
            label: "Spread",
            cells: [
              spreadLabel(marketSpread),
              <ResultCell key="result" result={game.spreadResult} />,
            ],
          },
          {
            label: "Total",
            cells: [
              game.totalLine === null
                ? "O/U —"
                : `O/U ${game.totalLine.toFixed(1)}`,
              <ResultCell key="result" result={game.totalResult} />,
            ],
          },
        ]}
      />
    </li>
  );
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
      <Image
        src={logoUrl(name)}
        alt={name}
        width={28}
        height={28}
        className="h-7 w-7 shrink-0 object-contain"
        unoptimized
      />
      <span
        className={clsx(
          "min-w-0 truncate text-sm text-ink",
          highlighted && "font-semibold",
        )}
      >
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
