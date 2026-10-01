"use client";

import { useMemo, useState } from "react";
import clsx from "clsx";
import type { Game } from "@/lib/queries";
import { hasLean, sortGames, type SortKey } from "@/lib/picks-proto";
import { dayLabel } from "./format";
import { ProtoGameCard } from "./ProtoGameCard";
import { ProtoGameRow } from "./ProtoGameRow";

const SORT_LABEL: Record<SortKey, string> = {
  kickoff: "Kickoff time",
  bestEdge: "Biggest edge",
  spreadEdge: "Spread edge",
  totalEdge: "Total edge",
};

type View = "grid" | "list";

/** Search, sort, "leans only" and grid/list view over the full slate. */
export function ProtoSlate({ games, ranks }: { games: Game[]; ranks: Record<string, number> }) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("kickoff");
  const [leansOnly, setLeansOnly] = useState(false);
  const [view, setView] = useState<View>("grid");

  const leanCount = useMemo(() => games.filter(hasLean).length, [games]);

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    let rows = games.filter(
      (g) => g.publicationMode === "predictions",
    );
    if (q) {
      rows = rows.filter(
        (g) => g.homeTeam.toLowerCase().includes(q) || g.awayTeam.toLowerCase().includes(q),
      );
    }
    if (leansOnly) rows = rows.filter(hasLean);
    return sortGames(rows, sort);
  }, [games, query, sort, leansOnly]);

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
          <ProtoGameCard key={g.gameId} game={g} ranks={ranks} />
        ) : (
          <ProtoGameRow key={g.gameId} game={g} ranks={ranks} />
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
        <button
          type="button"
          aria-pressed={leansOnly}
          onClick={() => setLeansOnly((v) => !v)}
          className={clsx(
            control,
            leansOnly ? "border-accent bg-accent-soft text-accent-ink" : "text-ink-muted hover:bg-surface-inset",
          )}
        >
          Leans only ({leanCount})
        </button>
        <label htmlFor="proto-sort" className="sr-only">Sort by</label>
        <select
          id="proto-sort"
          value={sort}
          onChange={(e) => setSort(e.target.value as SortKey)}
          className={clsx(control, "text-ink-muted")}
        >
          {(Object.keys(SORT_LABEL) as SortKey[]).map((k) => (
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

      <p className="px-1 text-xs text-ink-faint">
        Showing {visible.length} of {games.length} games · {leanCount} with a lean
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
