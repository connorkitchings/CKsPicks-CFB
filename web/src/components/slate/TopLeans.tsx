"use client";

import { ResponsiveDisclosure } from "@/components/ui/ResponsiveDisclosure";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
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
        <p className="py-2 text-center text-xs text-ink-muted">No leans yet.</p>
      ) : (
        <ol className="divide-y divide-line/40">
          {rows.map((l) => (
            <li key={l.game.gameId}>
              <a
                href={`#game-${l.game.gameId}`}
                aria-label={`${l.game.awayTeam} at ${l.game.homeTeam}: ${l.pick}`}
                className="flex min-h-11 min-w-0 items-center justify-between gap-2 rounded-md px-2.5 transition-colors hover:bg-surface-card focus-visible:outline-2 focus-visible:outline-accent"
              >
                {/* Left: The Matchup */}
                <span className="flex min-w-0 items-center gap-1.5 text-sm text-ink-muted">
                  <TeamLogo name={l.game.awayTeam} px={16} />
                  <span className="truncate">{l.game.awayTeam}</span>
                  <span className="shrink-0 text-ink-muted">@</span>
                  <TeamLogo name={l.game.homeTeam} px={16} />
                  <span className="truncate">{l.game.homeTeam}</span>
                </span>

                {/* Right: Pick Logo/Direction + Line */}
                <span className="flex shrink-0 items-center gap-1 text-sm font-semibold tabular-nums text-ink">
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

/** Largest-edge leans first; every game is still listed below. */
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

  const title = (
    <span>
      Biggest edges
      {record && (decided + record.push) > 0 && (
        <span className="ml-2 text-xs font-normal text-ink-muted">
          {season}: {record.win}–{record.loss}–{record.push}{rate !== null ? ` (${rate.toFixed(1)}%)` : ""}
        </span>
      )}
    </span>
  );

  return (
    <section aria-label="Biggest edges">
      <ResponsiveDisclosure
        className="rounded-xl border border-line bg-surface-card"
        title={title}
        heading={title}
      >
        <div className="mb-3 sm:hidden">
          <SegmentedControl label="Biggest edges category" value={tab} onChange={setTab} options={[{ value: "spread", label: "Spreads" }, { value: "total", label: "Totals" }]} fill />
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
      </ResponsiveDisclosure>
    </section>
  );
}
