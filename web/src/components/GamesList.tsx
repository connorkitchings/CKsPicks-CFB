"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import { GameRow } from "./GameRow";
import type { Game } from "@/lib/queries";

type SortKey = "kickoff" | "spreadEdge" | "totalEdge";

const SORT_LABEL: Record<SortKey, string> = {
  kickoff: "Kickoff time",
  spreadEdge: "Spread edge",
  totalEdge: "Total edge",
};

/**
 * Client-side wrapper around the games list with filter + sort controls.
 * ~70 games per week fits comfortably in the browser; no server round-trip
 * needed when the user types or toggles.
 */
export function GamesList({ games }: { games: Game[] }) {
  const [query, setQuery] = useState("");
  const [hcOnly, setHcOnly] = useState(false);
  const [sort, setSort] = useState<SortKey>("kickoff");
  const predictionsVisible = games[0]?.publicationMode === "predictions";

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    let rows = games;
    if (q) {
      rows = rows.filter(
        (g) =>
          g.homeTeam.toLowerCase().includes(q) ||
          g.awayTeam.toLowerCase().includes(q),
      );
    }
    if (hcOnly && predictionsVisible) {
      rows = rows.filter(
        (g) => g.publicationMode === "predictions" && g.highConfidence,
      );
    }

    const sorted = [...rows];
    sorted.sort((a, b) => {
      if (sort === "kickoff" || !predictionsVisible) {
        return a.startDate.getTime() - b.startDate.getTime();
      }
      if (sort === "spreadEdge") {
        const aEdge = a.publicationMode === "predictions" ? a.edgeSpread : null;
        const bEdge = b.publicationMode === "predictions" ? b.edgeSpread : null;
        return (bEdge ?? -Infinity) - (aEdge ?? -Infinity);
      }
      const aEdge = a.publicationMode === "predictions" ? a.edgeTotal : null;
      const bEdge = b.publicationMode === "predictions" ? b.edgeTotal : null;
      return (bEdge ?? -Infinity) - (aEdge ?? -Infinity);
    });
    return sorted;
  }, [games, query, hcOnly, predictionsVisible, sort]);

  const inputCls =
    "w-full rounded-md border border-zinc-200 bg-white px-2 py-1.5 text-sm text-zinc-800 placeholder:text-zinc-400 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100";

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex flex-col gap-2 rounded-xl border border-zinc-200 bg-white p-3 shadow-sm sm:flex-row sm:items-center dark:border-zinc-800 dark:bg-zinc-950">
        <div className="flex-1">
          <label htmlFor="team-search" className="sr-only">
            Filter by team
          </label>
          <input
            id="team-search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by team…"
            className={inputCls}
          />
        </div>
        {predictionsVisible && <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setHcOnly((v) => !v)}
            aria-pressed={hcOnly}
            className={clsx(
              "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors",
              hcOnly
                ? "border-blue-500 bg-blue-50 text-blue-700 dark:border-blue-400 dark:bg-blue-950 dark:text-blue-200"
                : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-100 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-300 dark:hover:bg-zinc-800",
            )}
          >
            <span aria-hidden>{hcOnly ? "\u2605" : "\u2606"}</span>
            High confidence
          </button>
          <label htmlFor="sort-select" className="sr-only">
            Sort by
          </label>
          <select
            id="sort-select"
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            className="rounded-md border border-zinc-200 bg-white px-2 py-1.5 text-xs font-medium text-zinc-700 focus:outline-none focus:ring-2 focus:ring-blue-500 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200"
          >
            {(Object.keys(SORT_LABEL) as SortKey[]).map((k) => (
              <option key={k} value={k}>
                {SORT_LABEL[k]}
              </option>
            ))}
          </select>
        </div>}
      </div>

      <div className="px-1 text-xs text-zinc-400 dark:text-zinc-500">
        Showing {visible.length} of {games.length} games
      </div>

      {visible.length === 0 ? (
        <div className="rounded-xl border border-zinc-200 bg-white p-6 text-center text-sm text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400">
          No games match these filters.
        </div>
      ) : (
        <ul className="space-y-3">
          {visible.map((g) => (
            <GameRow key={g.gameId} game={g} />
          ))}
        </ul>
      )}
    </div>
  );
}
