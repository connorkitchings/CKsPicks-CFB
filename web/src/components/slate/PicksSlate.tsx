"use client";

import { useMemo, useState } from "react";
import type { Game } from "@/lib/queries";
import { sortGames, type SortKey } from "@/lib/slate";
import { SlateToolbar } from "./SlateToolbar";
import { SlateGameList } from "./SlateGameList";
import { dayLabel } from "./format";

const SORT_LABEL: Record<SortKey, string> = {
  kickoff: "Kickoff time",
  bestEdge: "Biggest edge",
  spreadEdge: "Spread edge",
  totalEdge: "Total edge",
};

type View = "grid" | "list";

/** Search, sort, "leans only" and grid/list view over the full slate. */
export function PicksSlate({
  games,
  showBetResult = true,
  initialSort = "kickoff",
}: {
  games: Game[];
  /** Show graded results on market-mode cards (the Results page). */
  showBetResult?: boolean;
  /** Deep-linked sort (the `?sort=` param); the slate owns it afterwards. */
  initialSort?: SortKey;
}) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>(initialSort);
  const [view, setView] = useState<View>("grid");

  const predictionsVisible = useMemo(
    () => games.some((g) => g.publicationMode === "predictions"),
    [games],
  );
  const effectiveSort: SortKey = predictionsVisible ? sort : "kickoff";

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    let rows = [...games];
    if (q) {
      rows = rows.filter(
        (g) => g.homeTeam.toLowerCase().includes(q) || g.awayTeam.toLowerCase().includes(q),
      );
    }
    return sortGames(rows, effectiveSort);
  }, [games, query, effectiveSort]);

  const groups = useMemo(() => {
    if (effectiveSort !== "kickoff") return null;
    const out: { day: string; games: Game[] }[] = [];
    for (const g of visible) {
      const day = dayLabel(g.startDate);
      const last = out[out.length - 1];
      if (last && last.day === day) last.games.push(g);
      else out.push({ day, games: [g] });
    }
    return out;
  }, [visible, effectiveSort]);

  function renderList(rows: Game[]) {
    return <SlateGameList games={rows} view={view} mode="picks" showBetResult={showBetResult} />;
  }

  return (
    <div className="space-y-2 sm:space-y-4">
      <SlateToolbar query={query} onQueryChange={setQuery} sort={sort} onSortChange={setSort} sortLabels={SORT_LABEL} predictionsVisible={predictionsVisible} view={view} onViewChange={setView} />


      {visible.length === 0 ? (
        <div className="rounded-xl border border-line bg-surface-card p-6 text-center text-sm text-ink-muted">
          No games match these filters.
        </div>
      ) : groups ? (
        <div className="space-y-6">
          {groups.map((group) => (
            <section key={group.day} aria-label={group.day} className="space-y-3">
              <div className="sticky top-0 z-10 -mx-4 flex items-center gap-2 border-b border-line bg-surface-page/95 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-ink-muted backdrop-blur-xs">
                <span>{group.day}</span>
                <span className="font-normal lowercase text-ink-muted">
                  · {group.games.length} {group.games.length === 1 ? "game" : "games"}
                </span>
              </div>
              {renderList(group.games)}
            </section>
          ))}
        </div>
      ) : (
        renderList(visible)
      )}
    </div>
  );
}
