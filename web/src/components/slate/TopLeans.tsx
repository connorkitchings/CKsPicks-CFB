"use client";

import { useState } from "react";
import clsx from "clsx";
import type { Game } from "@/lib/queries";
import { topLeans, winRatePct, type LeanKind, type Tally } from "@/lib/slate";
import { LeanMarker } from "./LeanMarker";
import TeamLogo from "@/components/TeamLogo";

function Column({
  games,
  kind,
  title,
  className,
}: {
  games: Game[];
  kind: LeanKind;
  title: string;
  className?: string;
}) {
  const rows = topLeans(games, kind, 5);
  return (
    <div className={clsx("min-w-0 rounded-lg border border-line/60 bg-surface-inset/50 p-2 sm:p-3", className)}>
      <h3 className="mb-1.5 hidden text-center text-xs font-semibold uppercase tracking-wider text-ink-muted sm:mb-2 sm:block">
        {title}
      </h3>
      {rows.length === 0 ? (
        <p className="py-2 text-center text-xs text-ink-faint">No leans yet.</p>
      ) : (
        <ol className="divide-y divide-line/40">
          {rows.map((l) => (
            <li key={l.game.gameId}>
              <a
                href={`#game-${l.game.gameId}`}
                aria-label={`${l.game.awayTeam} at ${l.game.homeTeam}: ${l.pick}`}
                className="flex h-10 min-w-0 items-center justify-between gap-2 rounded-md px-2.5 transition-colors hover:bg-surface-card focus-visible:outline-2 focus-visible:outline-accent"
              >
                {/* Left: The Matchup */}
                <span className="flex min-w-0 items-center gap-1.5 text-xs text-ink-muted">
                  <TeamLogo name={l.game.awayTeam} px={16} />
                  <span className="truncate">{l.game.awayTeam}</span>
                  <span className="shrink-0 text-ink-faint">@</span>
                  <TeamLogo name={l.game.homeTeam} px={16} />
                  <span className="truncate">{l.game.homeTeam}</span>
                </span>

                {/* Right: Pick Logo/Direction + Line */}
                <span className="flex shrink-0 items-center gap-1 text-xs font-semibold tabular-nums text-ink sm:text-sm">
                  <LeanMarker lean={l} />
                  <span>
                    {kind === "spread" && l.team
                      ? l.pick.replace(l.team, "").trim()
                      : l.pick}
                  </span>
                </span>
              </a>
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

/** Highest-edge leans first; every game is still listed below. */
export function TopLeans({
  games,
  record,
  season,
}: {
  games: Game[];
  record?: Tally | null;
  season: number;
}) {
  const [tab, setTab] = useState<LeanKind>("spread");
  const decided = (record?.win ?? 0) + (record?.loss ?? 0);
  const rate = decided > 0 && record ? winRatePct(record.win, record.loss) : null;

  return (
    <section aria-label="Best bets" className="rounded-xl border border-line bg-surface-card p-3 shadow-sm sm:p-4">
      <div className="mb-2.5 flex items-baseline justify-between gap-2 sm:mb-3">
        <h2 className="text-sm font-semibold text-ink">Best Bets</h2>
        {record && (decided + (record.push ?? 0)) > 0 && (
          <span className="text-xs tabular-nums text-ink-muted">
            {season}: {record.win}–{record.loss}–{record.push}{rate !== null ? ` (${rate.toFixed(1)}%)` : ""}
          </span>
        )}
      </div>

      {/* Mobile-only Segmented Control */}
      <div className="mb-2.5 flex sm:hidden">
        <div className="grid w-full grid-cols-2 rounded-lg border border-line bg-surface-inset p-0.5 text-xs">
          <button
            type="button"
            onClick={() => setTab("spread")}
            className={clsx(
              "rounded-md py-1.5 font-medium transition-all",
              tab === "spread"
                ? "bg-surface-card font-semibold text-ink shadow-2xs"
                : "text-ink-muted hover:text-ink",
            )}
          >
            Spreads
          </button>
          <button
            type="button"
            onClick={() => setTab("total")}
            className={clsx(
              "rounded-md py-1.5 font-medium transition-all",
              tab === "total"
                ? "bg-surface-card font-semibold text-ink shadow-2xs"
                : "text-ink-muted hover:text-ink",
            )}
          >
            Totals
          </button>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Column
          games={games}
          kind="spread"
          title="Spread"
          className={tab !== "spread" ? "hidden sm:block" : undefined}
        />
        <Column
          games={games}
          kind="total"
          title="Total"
          className={tab !== "total" ? "hidden sm:block" : undefined}
        />
      </div>
    </section>
  );
}
