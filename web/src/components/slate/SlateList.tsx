"use client";

import clsx from "clsx";
import { useSearchParams } from "next/navigation";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { MarketComparison } from "./MarketComparison";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Eyebrow } from "@/components/ui/SectionHeading";
import { Notice } from "@/components/ui/Notice";
import {
  buildConferenceMap,
  conferenceOptions,
  matchesTeamConference,
  type RosterRow,
} from "@/lib/conferences";
import type { Game } from "@/lib/queries";
import { byKickoff, slateSorts, sortSlate, weekPhase, gameState, parseSlateStatus, matchesSlateStatus, type SlateSort, type SlateStatusFilter } from "@/lib/slate";
import { SlateToolbar } from "./SlateToolbar";
import { SlateGameList } from "./SlateGameList";
import { dayLabel } from "./format";
import { Chevron } from "./Chevron";

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
  weekNav,
  extras,
  now,
  matchupEnabled,
}: {
  games: Game[];
  roster?: RosterRow[];
  /** Deep-linked sort (the `?sort=` param); the list owns it afterwards. */
  initialSort?: SlateSort;
  /** Phone copy of the week navigator, pinned beside the Filters button. */
  weekNav?: ReactNode;
  /**
   * Collapsed disclosures (biggest edges, underdog picks, highlights). Rendered once, after the game
   * groups: flex `order-2` places it below the `order-1` games at every width.
   * On phones the collapsed disclosures sit side by side to save vertical space.
   */
  extras?: ReactNode;
  /** The clock for awaiting-result tags. */
  now: Date;
  matchupEnabled: boolean;
}) {
  const params = useSearchParams();
  const [scrollGame, setScrollGame] = useState<number | null>(null);
  const query = params.get("q") ?? "";
  const requestedConference = params.get("conference") ?? "all";
  const sort = (params.get("sort") ?? initialSort) as SlateSort;
  const view: View = params.get("view") === "list" ? "list" : "grid";
  const marketView = params.get("view") === "market";
  const status = parseSlateStatus(params.get("status"), games, now);
  function setParam(key: string, value: string) {
    const next = new URLSearchParams(window.location.search);
    next.set(key, value);
    window.history[key === "q" ? "replaceState" : "pushState"](null, "", `${window.location.pathname}?${next}`);
  }
  function showAllGames() {
    const next = new URLSearchParams(window.location.search);
    next.set("status", "all"); next.delete("q"); next.delete("conference");
    window.history.pushState(null, "", `${window.location.pathname}?${next}`);
  }
  const awaiting = games.filter((game) => gameState(game, now) === "awaiting").sort(byKickoff);
  const conferenceMap = useMemo(() => buildConferenceMap(roster), [roster]);
  const conferences = useMemo(() => conferenceOptions(roster), [roster]);
  const conference = requestedConference === "all" || requestedConference === "p4" || conferences.includes(requestedConference) ? requestedConference : "all";

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
    let rows = games.filter((game) => matchesSlateStatus(game, status, now));
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
  }, [games, query, conference, conferenceMap, effectiveSort, phase, status, now]);

  useEffect(() => {
    if (scrollGame === null || marketView || !visible.some((game) => game.gameId === scrollGame)) return;
    const frame = requestAnimationFrame(() => {
      document.getElementById(`game-${scrollGame}`)?.scrollIntoView({ block: "center" });
      setScrollGame(null);
    });
    return () => cancelAnimationFrame(frame);
  }, [scrollGame, marketView, visible]);

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
    <div className="flex flex-col gap-2 [--slate-bar-h:108px] sm:gap-4">
      <SlateToolbar query={query} onQueryChange={(value) => setParam("q", value)} conference={conference} onConferenceChange={(value) => setParam("conference", value)} conferences={conferences} sort={effectiveSort} onSortChange={(value) => setParam("sort", value)} sortLabels={sortLabels} predictionsVisible={predictionsVisible} view={view} onViewChange={(value) => setParam("view", value)} weekNav={weekNav} />
      <div className="order-1 flex flex-wrap items-center justify-between gap-3 py-2">
        <SegmentedControl label="Game status" value={status} onChange={(value: SlateStatusFilter) => setParam("status", value)} options={[{value:"today",label:"Today"},{value:"upcoming",label:"Upcoming"},{value:"results",label:"Results"},{value:"all",label:"All"}]} />
        {predictionsVisible && <SegmentedControl label="Games analysis" value={marketView ? "market" : "games"} onChange={(value) => setParam("view", value === "market" ? "market" : "grid")} options={[{value:"games",label:"Games"},{value:"market",label:"Model vs market"}]} />}
      </div>
      {awaiting.length > 0 && <p className="order-1 text-sm text-ink-muted"><button className="min-h-11 text-accent-ink underline" onClick={() => {
        const next = new URLSearchParams(window.location.search);
        next.set("status", "all"); next.delete("q"); next.delete("conference"); next.set("view", "grid");
        window.history.pushState(null, "", `${window.location.pathname}?${next}#game-${awaiting[0].gameId}`);
        setScrollGame(awaiting[0].gameId);
      }}>Awaiting published results: {awaiting.length}</button>. Results arrive with a data release, not a live score feed.</p>}
      {extras && <details className="order-2 border-t border-line py-3"><summary className="flex min-h-11 cursor-pointer items-center justify-between gap-2 text-sm font-semibold [&::-webkit-details-marker]:hidden">Featured comparisons and weekly highlights<Chevron /></summary><div className="mt-3">{extras}</div></details>}
      <p role="status" className="sr-only">Showing {visible.length} of {games.length} games</p>

      {marketView && predictionsVisible ? <div className="order-1"><MarketComparison games={visible} matchupEnabled={matchupEnabled} now={now} onReset={showAllGames} /></div> : visible.length === 0 ? (
        <div className="order-1"><Notice tone="empty">No games match these filters. <button className="-my-3 inline-flex min-h-11 items-center underline pointer-fine:my-0 pointer-fine:inline pointer-fine:min-h-0" onClick={showAllGames}>Show all games</button></Notice></div>
      ) : groups ? (
        groups.map((group, index) => (
          <section key={group.day} aria-label={group.day} className={clsx("space-y-1 sm:space-y-3", "order-1", index > 0 && "mt-4 sm:mt-2")}>
            <Eyebrow as="div" className="sticky z-10 -mx-4 flex items-center gap-2 border-b border-line bg-surface-page px-4 py-1 sm:bg-surface-page/95 sm:backdrop-blur-xs max-sm:top-[calc(var(--app-bar-h)+var(--slate-bar-h))] sm:top-0 sm:py-2">
              <span>{group.day}</span>
              <span className="font-normal lowercase text-ink-muted">
                · {group.games.length} {group.games.length === 1 ? "game" : "games"}
              </span>
            </Eyebrow>
            <SlateGameList games={group.games} view={view} now={now} />
          </section>
        ))
      ) : (
        <div className="order-1"><SlateGameList games={visible} view={view} now={now} /></div>
      )}
    </div>
  );
}
