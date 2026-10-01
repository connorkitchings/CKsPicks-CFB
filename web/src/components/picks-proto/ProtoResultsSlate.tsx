"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import type { Game } from "@/lib/queries";
import { matchesResult, sortResults, type ResultFilter, type ResultSort } from "@/lib/picks-proto";
import { dayLabel } from "./format";
import { ProtoResultCard } from "./ProtoResultCard";
import { ProtoResultRow } from "./ProtoResultRow";

const FILTERS: [ResultFilter, string][] = [
  ["all", "All"],
  ["win", "Wins"],
  ["loss", "Losses"],
  ["push", "Pushes"],
  ["none", "No lean"],
];

const SORT_LABEL: Record<ResultSort, string> = {
  kickoff: "Kickoff time",
  bestEdge: "Biggest edge",
  bestResult: "Biggest hit",
  worstResult: "Biggest miss",
};

type View = "grid" | "list";

/** Search, result filter, sort and grid/list view over a scored slate. */
export function ProtoResultsSlate({ games, ranks }: { games: Game[]; ranks: Record<string, number> }) {
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<ResultFilter>("all");
  const [sort, setSort] = useState<ResultSort>("kickoff");
  const [view, setView] = useState<View>("grid");

  const counts = useMemo(() => {
    const c: Record<ResultFilter, number> = { all: games.length, win: 0, loss: 0, push: 0, none: 0 };
    for (const f of ["win", "loss", "push", "none"] as const) {
      c[f] = games.filter((g) => matchesResult(g, f)).length;
    }
    return c;
  }, [games]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    let rows = games.filter((g) => g.publicationMode === "predictions");
    if (q) {
      rows = rows.filter(
        (g) => g.homeTeam.toLowerCase().includes(q) || g.awayTeam.toLowerCase().includes(q),
      );
    }
    rows = rows.filter((g) => matchesResult(g, filter));
    return sortResults(rows, sort);
  }, [games, query, filter, sort]);

  const groups = useMemo(() => {
    if (sort !== "kickoff") return null;
    const out: { day: string; games: Game[] }[] = [];
    for (const g of visible) {
      const day = dayLabel(g.startDate);
      const last = out[out.length - 1];
      if (last && last.day === day) last.games.push(g);
      else out.push({ day, games: [g] });
    }
    return out;
  }, [visible, sort]);

  const control =
    "rounded-md border border-line bg-surface-card px-2.5 py-1.5 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-accent";

  function renderList(rows: Game[]) {
    const items = rows.map((g) =>
      g.publicationMode === "predictions" ? (
        view === "grid" ? (
          <ProtoResultCard key={g.gameId} game={g} ranks={ranks} />
        ) : (
          <ProtoResultRow key={g.gameId} game={g} ranks={ranks} />
        )
      ) : null,
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
          <label htmlFor="proto-search" className="sr-only">Filter by team</label>
          <input
            id="proto-search"
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filter by team…"
            className={clsx(control, "w-full text-sm font-normal text-ink placeholder:text-ink-faint")}
          />
        </div>
        <div role="group" aria-label="Result filter" className="flex overflow-hidden rounded-md border border-line">
          {FILTERS.map(([key, label]) => (
            <button
              key={key}
              type="button"
              aria-pressed={filter === key}
              onClick={() => setFilter(key)}
              className={clsx(
                "px-2.5 py-1.5 text-xs font-medium",
                filter === key ? "bg-accent-soft text-accent-ink" : "bg-surface-card text-ink-muted hover:bg-surface-inset",
              )}
            >
              {label} <span className="tabular-nums text-ink-faint">{counts[key]}</span>
            </button>
          ))}
        </div>
        <label htmlFor="proto-sort" className="sr-only">Sort by</label>
        <select
          id="proto-sort"
          value={sort}
          onChange={(e) => setSort(e.target.value as ResultSort)}
          className={clsx(control, "text-ink-muted")}
        >
          {(Object.keys(SORT_LABEL) as ResultSort[]).map((k) => (
            <option key={k} value={k}>{SORT_LABEL[k]}</option>
          ))}
        </select>
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
      <p className="px-1 text-xs text-ink-faint">
        The number in parentheses after a pick is its edge: how many points the model differs from the market.
      </p>

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
