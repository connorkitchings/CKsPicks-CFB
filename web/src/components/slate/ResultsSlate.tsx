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
      <div className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-surface-card p-3 shadow-sm">
        <div className="min-w-[180px] flex-1">
          <label htmlFor="slate-search" className="sr-only">Filter by team</label>
          <input
            id="slate-search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by team…"
            className={clsx(control, "w-full text-sm font-normal text-ink placeholder:text-ink-faint")}
          />
        </div>
        {predictionsVisible && (
          <>
            <label htmlFor="slate-sort" className="sr-only">Sort by</label>
            <select
              id="slate-sort"
              value={sort}
              onChange={(e) => setSort(e.target.value as ResultSort)}
              className={clsx(control, "text-ink-muted")}
            >
              {(Object.keys(SORT_LABEL) as ResultSort[]).map((k) => (
                <option key={k} value={k}>{SORT_LABEL[k]}</option>
              ))}
            </select>
          </>
        )}
        <div role="group" aria-label="Layout" className="flex overflow-hidden rounded-md border border-line">
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
              <div className="flex items-center gap-2 border-b border-line pb-1.5 text-xs font-semibold uppercase tracking-wider text-ink-muted">
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
