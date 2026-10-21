"use client";

import { useState, type ReactNode } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import { CHART_REGISTRY, parseTeamParam, withTeamParam } from "@/lib/chart-config";
import {
  matchesConference,
  type AdjustedRow,
  type AdjustedScatter,
  type ConferenceFilter,
  type EfficiencyMetric,
  type GameLogMetric,
  type NetSuccessBar,
  type NotCharted,
  type PossessionMetric,
  type PossessionRow,
  type RatingMetric,
  type RatingSnapshotRow,
  type RosterRow,
  type Side,
  type TeamGameRow,
} from "@/lib/charts";
import { AdjustedView } from "./AdjustedView";
import type { SharedChartProps } from "./ChartFrame";
import { EfficiencyView, type EfficiencyData } from "./EfficiencyView";
import { GameLogView } from "./GameLogView";
import { NetSuccessView } from "./NetSuccessView";
import { PossessionView } from "./PossessionView";
import { RatingTrajectoryView } from "./RatingTrajectoryView";

/** The data of one chart view; a new chart adds its variant here and its case below. */
export type ChartPayload =
  | { kind: "net-success"; bars: NetSuccessBar[]; notCharted: NotCharted[] }
  | { kind: "efficiency"; side: Side; data: EfficiencyData; initialMetric: EfficiencyMetric; explosiveness: boolean }
  | { kind: "adjusted"; scatter: AdjustedScatter }
  | { kind: "rating-trajectory"; rows: RatingSnapshotRow[]; initialMetric: RatingMetric }
  | { kind: "possession"; rows: PossessionRow[]; initialMetric: PossessionMetric }
  | { kind: "game-log"; rows: TeamGameRow[]; adjusted: AdjustedRow[]; initialMetric: GameLogMetric; explosiveness: boolean };

export type ChartsViewProps = {
  season: number;
  /** Week of the net-success chart, or the "Through Week N" of a scatter. */
  week: number;
  roster: RosterRow[];
  chart: ChartPayload;
  /** The page's URL-backed settings (side links, week stepper) for the controls row. */
  settings?: ReactNode;
};

/**
 * Owns the state shared by every chart (conference filter, highlighted team) and renders
 * the view of `chart.kind`. It stays mounted across chart, week and side navigation, so
 * the filter persists; the highlight lives in the `team=` URL param, updated in place
 * with the History API (no navigation), which Next keeps in sync with `useSearchParams`.
 */
export function ChartsView({ season, week, roster, chart, settings }: ChartsViewProps) {
  const [filter, setFilter] = useState<ConferenceFilter>("all");
  const pathname = usePathname();
  const params = useSearchParams();
  const highlight = parseTeamParam(params.get("team"), roster);

  const setHighlight = (team: string | null) => {
    window.history.replaceState(null, "", withTeamParam(`${pathname}?${params.toString()}`, team));
  };
  const shared: SharedChartProps = {
    season,
    week,
    roster,
    filter,
    onFilterChange: (next) => {
      setFilter(next);
      const selected = roster.find((r) => r.team === highlight);
      if (selected && !matchesConference(next, selected.team, selected.conference)) setHighlight(null);
    },
    highlight: CHART_REGISTRY[chart.kind].controls.team ? highlight : null,
    onHighlight: (team) => setHighlight(team === null || team === highlight ? null : team),
    settings,
  };

  return renderView(chart, shared);
}

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
  }
}
