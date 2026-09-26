"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import { GameRow } from "./GameRow";
import type { Game } from "@/lib/queries";

type SortKey = "kickoff" | "spreadEdge" | "totalEdge";

const SORT_LABEL: Record<SortKey, string> = {
  kickoff: "Kickoff time",
  spreadEdge: "Spread Edge",
  totalEdge: "Totals Edge",
};

/**
 * Client-side wrapper around the games list with filter + sort controls.
 * ~70 games per week fits comfortably in the browser; no server round-trip
 * needed when the user types or toggles.
 */
export function GamesList({
  games,
  initialSort = "kickoff",
}: {
  games: Game[];
  initialSort?: SortKey;
}) {
  const [query, setQuery] = useState("");
  const [hcOnly, setHcOnly] = useState(false);
  const [sort, setSort] = useState<SortKey>(initialSort);
  const predictionsVisible = games[0]?.publicationMode === "predictions";
  const hasHighConfidence =
    predictionsVisible &&
    games.some(
      (game) => game.publicationMode === "predictions" && game.highConfidence,
    );

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
      // Sort edges descending by absolute size (|model − market|), putting
      // the biggest model/market disagreement first. Direction (home/away,
      // over/under) comes from the lean shown on each card. Unlined games
      // (null edge) stay at the bottom.
      const edgeField = sort === "spreadEdge" ? "edgeSpread" : "edgeTotal";
      const aRaw = a.publicationMode === "predictions" ? a[edgeField] : null;
      const bRaw = b.publicationMode === "predictions" ? b[edgeField] : null;
      const aEdge = aRaw !== null ? Math.abs(aRaw) : null;
      const bEdge = bRaw !== null ? Math.abs(bRaw) : null;
      if (aEdge === null && bEdge === null) return 0;
      if (aEdge === null) return 1;
      if (bEdge === null) return -1;
      return bEdge - aEdge;
    });
    return sorted;
  }, [games, query, hcOnly, predictionsVisible, sort]);


  const inputCls =
    "w-full rounded-md border border-line bg-surface-card px-2 py-1.5 text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:ring-2 focus:ring-accent";

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex flex-col gap-2 rounded-xl border border-line bg-surface-card p-3 shadow-sm sm:flex-row sm:items-center">
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
          {hasHighConfidence && (
            <button
              type="button"
              onClick={() => setHcOnly((v) => !v)}
              aria-pressed={hcOnly}
              className={clsx(
                "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors",
                hcOnly
                  ? "border-accent bg-accent-soft text-accent-ink"
                  : "border-line bg-surface-card text-ink-muted hover:bg-surface-inset",
              )}
            >
              <span aria-hidden>{hcOnly ? "\u2605" : "\u2606"}</span>
              High confidence
            </button>
          )}
          <label htmlFor="sort-select" className="sr-only">
            Sort by
          </label>
          <select
            id="sort-select"
            value={sort}
            onChange={(e) => setSort(e.target.value as SortKey)}
            className="rounded-md border border-line bg-surface-card px-2 py-1.5 text-xs font-medium text-ink-muted focus:outline-none focus:ring-2 focus:ring-accent"
          >
            {(Object.keys(SORT_LABEL) as SortKey[]).map((k) => (
              <option key={k} value={k}>
                {SORT_LABEL[k]}
              </option>
            ))}
          </select>
        </div>}
      </div>

      <div className="px-1 text-xs text-ink-faint">
        Showing {visible.length} of {games.length} games
      </div>

      {visible.length === 0 ? (
        <div className="rounded-xl border border-line bg-surface-card p-6 text-center text-sm text-ink-faint">
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
