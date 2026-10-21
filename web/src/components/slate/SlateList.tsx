"use client";

import { useMemo, useState } from "react";
import { Eyebrow } from "@/components/ui/SectionHeading";
import { Notice } from "@/components/ui/Notice";
import {
  buildConferenceMap,
  conferenceOptions,
  matchesTeamConference,
  type ConferenceFilter,
  type RosterRow,
} from "@/lib/conferences";
import type { Game } from "@/lib/queries";
import { slateSorts, sortSlate, weekPhase, type SlateSort } from "@/lib/slate";
import { SlateToolbar } from "./SlateToolbar";
import { SlateGameList } from "./SlateGameList";
import { dayLabel } from "./format";

const SORT_LABEL: Record<SlateSort, string> = {
  kickoff: "Kickoff time",
  bestEdge: "Biggest edge",
  spreadEdge: "Spread edge",
  totalEdge: "Total edge",
  bestResult: "Biggest hit",
  worstResult: "Biggest miss",
};

type View = "grid" | "list";

/** Search, sort, conference filter and grid/list view over one week's games, graded or not. */
export function SlateList({
  games,
  roster = [],
  initialSort = "kickoff",
}: {
  games: Game[];
  roster?: RosterRow[];
  /** Deep-linked sort (the `?sort=` param); the list owns it afterwards. */
  initialSort?: SlateSort;
}) {
  const [query, setQuery] = useState("");
  const [conference, setConference] = useState<ConferenceFilter>("all");
  const [sort, setSort] = useState<SlateSort>(initialSort);
  const [view, setView] = useState<View>("grid");
  const conferenceMap = useMemo(() => buildConferenceMap(roster), [roster]);
  const conferences = useMemo(() => conferenceOptions(roster), [roster]);

  const phase = useMemo(() => weekPhase(games), [games]);
  const predictionsVisible = useMemo(
    () => games.some((g) => g.publicationMode === "predictions"),
    [games],
  );
  const effectiveSort: SlateSort = predictionsVisible && slateSorts(phase).includes(sort) ? sort : "kickoff";
  const sortLabels = useMemo(
    () => Object.fromEntries(slateSorts(phase).map((key) => [key, SORT_LABEL[key]])) as Record<SlateSort, string>,
    [phase],
  );

  const visible = useMemo(() => {
    const q = query.trim().toLowerCase();
    let rows = [...games];
    if (conference !== "all") {
      rows = rows.filter(
        (g) =>
          matchesTeamConference(conference, g.homeTeam, conferenceMap) ||
          matchesTeamConference(conference, g.awayTeam, conferenceMap),
      );
    }
    if (q) {
      rows = rows.filter(
        (g) => g.homeTeam.toLowerCase().includes(q) || g.awayTeam.toLowerCase().includes(q),
      );
    }
    return sortSlate(rows, effectiveSort, phase);
  }, [games, query, conference, conferenceMap, effectiveSort, phase]);

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

  return (
    <div className="space-y-2 sm:space-y-4">
      <SlateToolbar query={query} onQueryChange={setQuery} conference={conference} onConferenceChange={setConference} conferences={conferences} sort={effectiveSort} onSortChange={setSort} sortLabels={sortLabels} predictionsVisible={predictionsVisible} view={view} onViewChange={setView} />
      <p role="status" className="sr-only">Showing {visible.length} of {games.length} games</p>

      {visible.length === 0 ? (
        <Notice tone="empty">No games match these filters.</Notice>
      ) : groups ? (
        <div className="space-y-6">
          {groups.map((group) => (
            <section key={group.day} aria-label={group.day} className="space-y-3">
              <Eyebrow as="div" className="sticky top-0 z-10 -mx-4 flex items-center gap-2 border-b border-line bg-surface-page/95 px-4 py-2 backdrop-blur-xs">
                <span>{group.day}</span>
                <span className="font-normal lowercase text-ink-muted">
                  · {group.games.length} {group.games.length === 1 ? "game" : "games"}
                </span>
              </Eyebrow>
              <SlateGameList games={group.games} view={view} />
            </section>
          ))}
        </div>
      ) : (
        <SlateGameList games={visible} view={view} />
      )}
    </div>
  );
}
