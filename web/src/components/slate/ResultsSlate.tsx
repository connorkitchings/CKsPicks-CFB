"use client";

import { useMemo, useState } from "react";
import type { Game } from "@/lib/queries";
import { sortResults, type ResultSort } from "@/lib/slate";
import { SlateToolbar } from "./SlateToolbar";
import { SlateGameList } from "./SlateGameList";
import { dayLabel } from "./format";

const SORT_LABEL: Record<ResultSort, string> = {
  kickoff: "Kickoff time",
  bestEdge: "Biggest edge",
  bestResult: "Biggest hit",
  worstResult: "Biggest miss",
};

type View = "grid" | "list";

/** Search, sort and grid/list view over a scored slate. */
export function ResultsSlate({
  games,
  showBetResult = true,
  initialSort = "kickoff",
}: {
  games: Game[];
  /** Show graded results on market-mode cards. */
  showBetResult?: boolean;
  /** Deep-linked sort (the `?sort=` param maps edge sorts to biggest edge). */
  initialSort?: ResultSort;
}) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<ResultSort>(initialSort);
  const [view, setView] = useState<View>("grid");

  const predictionsVisible = useMemo(
    () => games.some((g) => g.publicationMode === "predictions"),
    [games],
  );
  const effectiveSort: ResultSort = predictionsVisible ? sort : "kickoff";

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    let rows = [...games];
    if (q) {
      rows = rows.filter(
        (g) => g.homeTeam.toLowerCase().includes(q) || g.awayTeam.toLowerCase().includes(q),
      );
    }
    return sortResults(rows, effectiveSort);
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
    return <SlateGameList games={rows} view={view} mode="results" showBetResult={showBetResult} />;
  }

  return (
    <div className="space-y-2 sm:space-y-4">
      <SlateToolbar query={query} onQueryChange={setQuery} sort={sort} onSortChange={setSort} sortLabels={SORT_LABEL} predictionsVisible={predictionsVisible} view={view} onViewChange={setView} />
      <p role="status" className="sr-only">Showing {visible.length} of {games.length} games</p>


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
