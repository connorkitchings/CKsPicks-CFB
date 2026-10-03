"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import type { Game } from "@/lib/queries";
import { sortResults, type ResultSort } from "@/lib/slate";
import { dayLabel } from "./format";
import { ResultGameCard } from "./ResultGameCard";
import { ResultGameRow } from "./ResultGameRow";

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

  const control =
    "rounded-md border border-line bg-surface-card px-2.5 py-1.5 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-accent";

  function renderList(rows: Game[]) {
    const items = rows.map((g) =>
      view === "grid" ? (
        <ResultGameCard key={g.gameId} game={g} showBetResult={showBetResult} />
      ) : (
        <ResultGameRow key={g.gameId} game={g} showBetResult={showBetResult} />
      ),
    );
    return view === "grid" ? (
      <ul className="grid gap-3 md:grid-cols-2">{items}</ul>
    ) : (
      <ul className="overflow-hidden rounded-xl border border-line bg-surface-card shadow-sm">{items}</ul>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 rounded-xl border border-line bg-surface-card p-3 shadow-sm sm:flex-row sm:items-center">
        <div className="relative w-full sm:flex-1">
          <label htmlFor="slate-search" className="sr-only">Filter by team</label>
          <input
            id="slate-search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by team…"
            className={clsx(
              control,
              "w-full text-base font-normal text-ink placeholder:text-ink-faint sm:text-sm [&::-webkit-search-cancel-button]:hidden",
              query && "pr-8",
            )}
          />
          {query && (
            <button
              type="button"
              onClick={() => setQuery("")}
              aria-label="Clear filter"
              className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full p-1 text-ink-faint transition-colors hover:text-ink focus-visible:outline-2 focus-visible:outline-accent"
            >
              <svg className="h-4 w-4" viewBox="0 0 20 20" fill="currentColor" aria-hidden="true">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.28 7.22a.75.75 0 00-1.06 1.06L8.94 10l-1.72 1.72a.75.75 0 101.06 1.06L10 11.06l1.72 1.72a.75.75 0 101.06-1.06L11.06 10l1.72-1.72a.75.75 0 00-1.06-1.06L10 8.94 8.28 7.22z" clipRule="evenodd" />
              </svg>
            </button>
          )}
        </div>
        <div className="flex w-full items-center justify-between gap-2 sm:w-auto sm:justify-start">
          {predictionsVisible && (
            <div className="flex-1 sm:flex-none">
              <label htmlFor="slate-sort" className="sr-only">Sort by</label>
              <select
                id="slate-sort"
                value={sort}
                onChange={(e) => setSort(e.target.value as ResultSort)}
                className={clsx(control, "w-full text-ink-muted sm:w-auto")}
              >
                {(Object.keys(SORT_LABEL) as ResultSort[]).map((k) => (
                  <option key={k} value={k}>{SORT_LABEL[k]}</option>
                ))}
              </select>
            </div>
          )}
          <div role="group" aria-label="Layout" className="flex shrink-0 overflow-hidden rounded-md border border-line">
            {(["grid", "list"] as View[]).map((v) => (
              <button
                key={v}
                type="button"
                aria-pressed={view === v}
                onClick={() => setView(v)}
                className={clsx(
                  "px-2.5 py-1.5 text-xs font-medium capitalize",
                  view === v ? "bg-accent-soft text-accent-ink" : "bg-surface-card text-ink-muted hover:bg-surface-inset",
                )}
              >
                {v}
              </button>
            ))}
          </div>
        </div>
      </div>

      <p className="px-1 text-xs text-ink-faint">Showing {visible.length} of {games.length} games</p>
      {predictionsVisible && (
        <p className="px-1 text-xs text-ink-faint">
          The number in parentheses after a pick is its edge: how many points the model differs from the market.
        </p>
      )}

      {visible.length === 0 ? (
        <div className="rounded-xl border border-line bg-surface-card p-6 text-center text-sm text-ink-faint">
          No games match these filters.
        </div>
      ) : groups ? (
        <div className="space-y-6">
          {groups.map((group) => (
            <section key={group.day} aria-label={group.day} className="space-y-3">
              <div className="sticky top-0 z-10 -mx-4 flex items-center gap-2 border-b border-line bg-surface-page/95 px-4 py-2 text-xs font-semibold uppercase tracking-wider text-ink-muted backdrop-blur-xs">
                <span>{group.day}</span>
                <span className="font-normal lowercase text-ink-faint">
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
