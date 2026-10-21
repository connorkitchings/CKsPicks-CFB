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

/** Search, sort, conference filter and grid/list view over a scored slate. */
export function ResultsSlate({
  games,
  roster = [],
  showBetResult = true,
  initialSort = "kickoff",
}: {
  games: Game[];
  roster?: RosterRow[];
  /** Show graded results on market-mode cards. */
  showBetResult?: boolean;
  /** Deep-linked sort (the `?sort=` param maps edge sorts to biggest edge). */
  initialSort?: ResultSort;
}) {
  const [query, setQuery] = useState("");
  const [conference, setConference] = useState<ConferenceFilter>("all");
  const [sort, setSort] = useState<ResultSort>(initialSort);
  const [view, setView] = useState<View>("grid");
  const conferenceMap = useMemo(() => buildConferenceMap(roster), [roster]);
  const conferences = useMemo(() => conferenceOptions(roster), [roster]);

  const predictionsVisible = useMemo(
    () => games.some((g) => g.publicationMode === "predictions"),
    [games],
  );
  const effectiveSort: ResultSort = predictionsVisible ? sort : "kickoff";

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
    return sortResults(rows, effectiveSort);
  }, [games, query, conference, conferenceMap, effectiveSort]);

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
      <SlateToolbar query={query} onQueryChange={setQuery} conference={conference} onConferenceChange={setConference} conferences={conferences} sort={sort} onSortChange={setSort} sortLabels={SORT_LABEL} predictionsVisible={predictionsVisible} view={view} onViewChange={setView} />
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
