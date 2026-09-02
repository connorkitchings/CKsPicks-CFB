import Image from "next/image";
import { clsx } from "clsx";
import { logoUrl } from "@/lib/teams";
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
function spreadEdgeNote(model: SpreadView, market: SpreadView): string | null {
  if (
    model === null ||
    market === null ||
    model === "PK" ||
    market === "PK"
  ) {
    return null;
  }
  return `(${signedSpread(model.line - market.line)})`;
}

/** Signed difference between the model and market totals. */
function totalEdgeNote(
  predictedTotal: number | null,
  totalLine: number | null,
): string | null {
  if (predictedTotal === null || totalLine === null) return null;
  return `(${signedSpread(predictedTotal - totalLine)})`;
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

const colHeaderCls =
  "py-1 text-[10px] font-medium uppercase tracking-wide text-ink-faint";
const rowHeaderCls = "py-1.5 pr-2 text-left font-medium text-ink-muted";
const numberCellCls = "py-1.5 pl-2 text-right font-mono tabular-nums text-ink";

/** Quiet parenthetical in the Model cell: how far model sits from market. */
function EdgeNote({ note }: { note: string | null }) {
  if (note === null) return null;
  return (
    <span className="ml-1 text-ink-faint" title="Model minus market">
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

      {/* Market vs model comparison */}
      <table className="mt-3 w-full tabular-nums text-[11px] sm:text-xs">
        <thead>
          <tr>
            <th scope="col" className={colHeaderCls}>
              <span className="sr-only">Bet type</span>
            </th>
            <th scope="col" className={`${colHeaderCls} pl-2 text-right`}>
              Market
            </th>
            <th scope="col" className={`${colHeaderCls} pl-2 text-right`}>
              Model
            </th>
            <th scope="col" className={`${colHeaderCls} pl-2 text-right`}>
              Model Bet
            </th>
            <th scope="col" className={`${colHeaderCls} pl-2 text-right`}>
              Bet Result
            </th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-t border-line">
            <th scope="row" className={rowHeaderCls}>
              Spread
            </th>
            <td className={numberCellCls}>{spreadLabel(marketSpread)}</td>
            <td className={numberCellCls}>
              {spreadLabel(modelSpread)}
              <EdgeNote note={spreadEdgeNote(modelSpread, marketSpread)} />
            </td>
            <td className="py-1.5 pl-2 text-right font-mono tabular-nums">
              {spreadBet ? (
                <span className="font-medium text-accent-ink">{spreadBet}</span>
              ) : (
                <span className="text-ink-faint">No lean</span>
              )}
            </td>
            <td className="py-1.5 pl-2 text-right">
              <ResultCell result={game.spreadResult} />
            </td>
          </tr>
          <tr className="border-t border-b border-line">
            <th scope="row" className={rowHeaderCls}>
              Total
            </th>
            <td className={numberCellCls}>
              {game.totalLine === null ? "—" : game.totalLine.toFixed(1)}
            </td>
            <td className={numberCellCls}>
              {game.predictedTotal === null
                ? "—"
                : game.predictedTotal.toFixed(1)}
              <EdgeNote
                note={totalEdgeNote(game.predictedTotal, game.totalLine)}
              />
            </td>
            <td className="py-1.5 pl-2 text-right font-mono tabular-nums">
              {totalBet ? (
                <span className="font-medium text-accent-ink">{totalBet}</span>
              ) : (
                <span className="text-ink-faint">No lean</span>
              )}
            </td>
            <td className="py-1.5 pl-2 text-right">
              <ResultCell result={game.totalResult} />
            </td>
          </tr>
        </tbody>
      </table>

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
      <table className="mt-3 w-full tabular-nums text-[11px] sm:text-xs">
        <thead>
          <tr>
            <th scope="col" className={colHeaderCls}>
              <span className="sr-only">Bet type</span>
            </th>
            <th scope="col" className={`${colHeaderCls} pl-2 text-right`}>
              Market
            </th>
            <th scope="col" className={`${colHeaderCls} pl-2 text-right`}>
              Bet Result
            </th>
          </tr>
        </thead>
        <tbody>
          <tr className="border-t border-line">
            <th scope="row" className={rowHeaderCls}>
              Spread
            </th>
            <td className={numberCellCls}>{spreadLabel(marketSpread)}</td>
            <td className="py-1.5 pl-2 text-right">
              <ResultCell result={game.spreadResult} />
            </td>
          </tr>
          <tr className="border-t border-b border-line">
            <th scope="row" className={rowHeaderCls}>
              Total
            </th>
            <td className={numberCellCls}>
              {game.totalLine === null
                ? "O/U —"
                : `O/U ${game.totalLine.toFixed(1)}`}
            </td>
            <td className="py-1.5 pl-2 text-right">
              <ResultCell result={game.totalResult} />
            </td>
          </tr>
        </tbody>
      </table>
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
          "truncate text-sm text-ink",
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
