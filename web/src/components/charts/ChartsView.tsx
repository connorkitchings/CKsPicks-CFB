"use client";

import { type ReactNode } from "react";
import dynamic from "next/dynamic";
import { usePathname, useSearchParams } from "next/navigation";
import { CHART_REGISTRY, parseTeamParam, withTeamParam } from "@/lib/chart-config";
import { replaceSearchParams, searchParamsUrl } from "@/lib/url-state";
import {
  conferenceOptions,
  type AdjustedRow,
  type AdjustedScatter,
  type ConferenceFilter,
  type EfficiencyMetric,
  type GameLogMetric,
  type MarketBoardMetric,
  type NetSuccessBar,
  type NotCharted,
  type PossessionMetric,
  type PossessionRow,
  type RatingMetric,
  type RatingSnapshotRow,
  type RosterRow,
  type Side,
  type SlateMarketGameRow,
  type TeamGameRow,
  type TeamResumeChartRow,
  type TeamSeasonStatRow,
} from "@/lib/charts";
import { AdjustedView } from "./AdjustedView";
import type { SharedChartProps } from "./ChartFrame";
import { DownsView } from "./DownsView";
import { EfficiencyView, type EfficiencyData } from "./EfficiencyView";
import { FinishingDrivesView } from "./FinishingDrivesView";
import { GameLogView } from "./GameLogView";
import { NetSuccessView } from "./NetSuccessView";
import { PossessionView } from "./PossessionView";

/** The data of one chart view; a new chart adds its variant here and its case below. */
export type ChartPayload =
  | { kind: "net-success"; bars: NetSuccessBar[]; notCharted: NotCharted[] }
  | { kind: "efficiency"; side: Side; data: EfficiencyData; initialMetric: EfficiencyMetric; explosiveness: boolean }
  | { kind: "adjusted"; scatter: AdjustedScatter }
  | { kind: "rating-trajectory"; rows: RatingSnapshotRow[]; initialMetric: RatingMetric }
  | { kind: "possession"; rows: PossessionRow[]; initialMetric: PossessionMetric }
  | { kind: "game-log"; rows: TeamGameRow[]; adjusted: AdjustedRow[]; initialMetric: GameLogMetric; explosiveness: boolean }
  | { kind: "downs"; rows: TeamSeasonStatRow[]; side: Side }
  | { kind: "finishing-drives"; rows: TeamSeasonStatRow[]; side: Side }
  | { kind: "resume-quality"; ratings: RatingSnapshotRow[]; resumeRows: TeamResumeChartRow[] }
  | { kind: "market-board"; games: SlateMarketGameRow[]; initialMetric: MarketBoardMetric };

export type ChartsViewProps = {
  season: number;
  /** Week of the net-success chart, or the "Through Week N" of a scatter. */
  week: number;
  roster: RosterRow[];
  chart: ChartPayload;
  /** The page's URL-backed settings (side links, week stepper) for the controls row. */
  settings?: ReactNode;
  nextMatchups?: Record<string, number>;
};

/**
 * Owns the state shared by every chart (conference filter, highlighted team) and renders
 * the view of `chart.kind`. It stays mounted across chart, week and side navigation, so
 * the filter persists; the highlight lives in the `team=` URL param, updated in place
 * with the History API (no navigation), which Next keeps in sync with `useSearchParams`.
 */
export function ChartsView({ season, week, roster, chart, settings, nextMatchups }: ChartsViewProps) {
  const pathname = usePathname();
  const params = useSearchParams();
  const highlight = parseTeamParam(params.get("team"), roster);
  const compareCandidate = parseTeamParam(params.get("compare"), roster);
  const compare = compareCandidate === highlight ? null : compareCandidate;
  const rawFilter = params.get("conf");
  const filter: ConferenceFilter = rawFilter && ["all", "p4", ...conferenceOptions(roster)].includes(rawFilter) ? rawFilter : "all";
  const update = (key: string, value: string | null) => {
    replaceSearchParams(pathname, (next) => { if (value) next.set(key, value); else next.delete(key); });
  };

  const setHighlight = (team: string | null) => {
    window.history.replaceState(null, "", withTeamParam(searchParamsUrl(pathname, () => {}), team));
  };
  const shared: SharedChartProps = {
    season,
    week,
    roster,
    filter,
    onFilterChange: (next) => update("conf", next === "all" ? null : next),
    compare,
    onCompare: (team) => update("compare", team === highlight ? null : team),
    highlight: CHART_REGISTRY[chart.kind].controls.team ? highlight : null,
    onHighlight: (team) => setHighlight(team === null || team === highlight ? null : team),
    settings,
    nextMatchups,
  };

  return renderView(chart, shared);
}

// Views behind charts that are not in the public navigation stay out of the main chart bundle.
const RatingTrajectoryView = dynamic(() => import("./RatingTrajectoryView").then((m) => m.RatingTrajectoryView));
const ResumeQualityView = dynamic(() => import("./ResumeQualityView").then((m) => m.ResumeQualityView));
const MarketBoardView = dynamic(() => import("./MarketBoardView").then((m) => m.MarketBoardView));

function renderView(chart: ChartPayload, shared: SharedChartProps) {
  switch (chart.kind) {
    case "net-success":
      return <NetSuccessView shared={shared} bars={chart.bars} notCharted={chart.notCharted} />;
    case "efficiency":
      return <EfficiencyView key={chart.explosiveness ? "charts_v2" : "charts_v1"} shared={shared} side={chart.side} data={chart.data} initialMetric={chart.initialMetric} explosiveness={chart.explosiveness} />;
    case "adjusted":
      return <AdjustedView shared={shared} scatter={chart.scatter} />;
    case "rating-trajectory":
      return <RatingTrajectoryView shared={shared} rows={chart.rows} initialMetric={chart.initialMetric} />;
    case "possession":
      return <PossessionView shared={shared} rows={chart.rows} initialMetric={chart.initialMetric} />;
    case "game-log":
      return <GameLogView key={chart.explosiveness ? "charts_v2" : "charts_v1"} shared={shared} rows={chart.rows} adjusted={chart.adjusted} initialMetric={chart.initialMetric} explosiveness={chart.explosiveness} />;
    case "downs":
      return <DownsView shared={shared} rows={chart.rows} side={chart.side} />;
    case "finishing-drives":
      return <FinishingDrivesView shared={shared} rows={chart.rows} side={chart.side} />;
    case "resume-quality":
      return <ResumeQualityView shared={shared} ratings={chart.ratings} resumeRows={chart.resumeRows} />;
    case "market-board":
      return <MarketBoardView shared={shared} games={chart.games} initialMetric={chart.initialMetric} />;
  }
}
