import Image from "next/image";
import { clsx } from "clsx";
import { LeanBadge, TotalLeanChip } from "./LeanBadge";
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

function signedSpread(n: number | null): string {
  if (n === null) return "—";
  return n > 0 ? `+${n.toFixed(1)}` : n.toFixed(1);
}

function marketSpreadLabel(homeTeam: string, line: number | null): string {
  if (line === null) return "PK / no line";
  // Line is the home team's spread; +home dog, -home favorite.
  return `${homeTeam} ${signedSpread(line)}`;
}

export function GameRow({ game }: { game: Game }) {
  const hasResults = game.homePoints !== null && game.awayPoints !== null;
  const hasAnyLine = game.homeTeamSpreadLine !== null || game.totalLine !== null;
  const regimeLabel = {
    preseason: "Preseason",
    one_game: "1 game",
    two_games: "2 games",
    three_games: "3 games",
    established: "Established",
  }[game.regime ?? "established"];

  return (
    <li
      className={clsx(
        "rounded-xl border border-zinc-200 bg-white p-4 shadow-sm transition-colors dark:border-zinc-800 dark:bg-zinc-950",
        game.highConfidence &&
          "ring-2 ring-blue-500/40 dark:ring-blue-400/30",
      )}
    >
      {/* Header row: time + confidence marker */}
      <div className="mb-3 flex items-center justify-between text-xs text-zinc-500 dark:text-zinc-400">
        <span>{formatKickoff(game.startDate)}</span>
        <div className="flex items-center gap-2">
          {game.regime && (
            <span className="rounded-full bg-zinc-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-zinc-600 dark:bg-zinc-900 dark:text-zinc-300">
              {regimeLabel}
            </span>
          )}
          {game.highConfidence && (
            <span className="rounded-full bg-blue-100 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-blue-700 dark:bg-blue-950 dark:text-blue-300">
              ★ High Confidence
            </span>
          )}
        </div>
      </div>

      {!hasAnyLine && (
        <div className="mt-3 rounded-md bg-amber-50 px-3 py-2 text-xs font-medium text-amber-800 dark:bg-amber-950/50 dark:text-amber-200">
          Line unavailable—model prediction shown, no lean.
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
        {/* Teams + logos */}
        <div className="space-y-2">
          <TeamLine
            name={game.awayTeam}
            role="away"
            highlighted={game.spreadLean === "away"}
          />
          <TeamLine
            name={game.homeTeam}
            role="home"
            highlighted={game.spreadLean === "home"}
          />
        </div>

        {/* Model output + leans */}
        <div className="flex flex-col items-end gap-2 text-right">
          <LeanBadge
            lean={game.spreadLean}
            edge={game.edgeSpread}
            homeTeam={game.homeTeam}
            awayTeam={game.awayTeam}
          />
          <TotalLeanChip
            lean={game.totalLean}
            edge={game.edgeTotal}
            totalLine={game.totalLine}
          />
        </div>
      </div>

      {/* Market lines + model predictions */}
      <div className="mt-3 grid grid-cols-2 gap-2 border-t border-zinc-100 pt-3 text-xs dark:border-zinc-900">
        <div>
          <div className="text-zinc-400 dark:text-zinc-500">Market</div>
          <div className="font-mono text-zinc-700 dark:text-zinc-300">
            {marketSpreadLabel(game.homeTeam, game.homeTeamSpreadLine)}
          </div>
          {game.totalLine !== null && (
            <div className="font-mono text-zinc-700 dark:text-zinc-300">
              O/U {game.totalLine.toFixed(1)}
            </div>
          )}
        </div>
        <div className="text-right">
          <div className="text-zinc-400 dark:text-zinc-500">Model says</div>
          <div className="font-mono text-zinc-700 dark:text-zinc-300">
            pred spread {signedSpread(game.predictedSpread)}
          </div>
          {game.predictedTotal !== null && (
            <div className="font-mono text-zinc-700 dark:text-zinc-300">
              pred total {game.predictedTotal.toFixed(1)}
            </div>
          )}
        </div>
      </div>

      {/* Score (if game has been played) */}
      {hasResults && (
        <div className="mt-2 flex items-center gap-3 text-xs">
          <span className="text-zinc-500 dark:text-zinc-400">Final:</span>
          <span className="font-mono font-semibold">
            {game.awayPoints}–{game.homePoints}
          </span>
          {game.spreadResult && (
            <span
              className={clsx(
                "rounded px-1.5 py-0.5 font-medium",
                game.spreadResult === "win"
                  ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                  : game.spreadResult === "loss"
                    ? "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300"
                    : "bg-zinc-100 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400",
              )}
            >
              spread {game.spreadResult}
            </span>
          )}
          {game.totalResult && (
            <span
              className={clsx(
                "rounded px-1.5 py-0.5 font-medium",
                game.totalResult === "win"
                  ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300"
                  : game.totalResult === "loss"
                    ? "bg-rose-100 text-rose-700 dark:bg-rose-950 dark:text-rose-300"
                    : "bg-zinc-100 text-zinc-600 dark:bg-zinc-900 dark:text-zinc-400",
              )}
            >
              total {game.totalResult}
            </span>
          )}
        </div>
      )}
      {(game.spreadModelVersion || game.totalModelVersion) && (
        <div className="mt-2 text-[10px] text-zinc-400 dark:text-zinc-600">
          Spread {game.spreadModelVersion ?? "—"} · Total {game.totalModelVersion ?? "—"}
        </div>
      )}
    </li>
  );
}

function TeamLine({
  name,
  role,
  highlighted,
}: {
  name: string;
  role: "home" | "away";
  highlighted: boolean;
}) {
  return (
    <div
      className={clsx(
        "flex items-center gap-2.5",
        highlighted && "font-semibold",
      )}
    >
      <Image
        src={logoUrl(name)}
        alt={name}
        width={28}
        height={28}
        className="h-7 w-7 shrink-0 object-contain"
        unoptimized
      />
      <span className="text-sm text-zinc-900 dark:text-zinc-100">
        {name}
      </span>
      {role === "home" && (
        <span className="text-[10px] uppercase tracking-wide text-zinc-400">
          home
        </span>
      )}
    </div>
  );
}
