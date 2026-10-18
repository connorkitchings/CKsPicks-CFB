"use client";

import { useMemo, useState } from "react";
import { TRAJECTORY_METRICS, formatEpaTick } from "@/lib/chart-config";
import { formatEpa, trajectorySeries, type AdjustedRow, type TrajectoryMetric } from "@/lib/charts";
import { SegmentedControl, type SharedChartProps } from "./ChartFrame";
import { TrajectoryPanel } from "./TrajectoryPanel";

const METRIC_OPTIONS = (Object.keys(TRAJECTORY_METRICS) as TrajectoryMetric[]).map((value) => ({
  value,
  label: TRAJECTORY_METRICS[value].label,
  testId: `trajectory-metric-${value}`,
}));

/** Adjusted PPA/play of every team across the stored windows: national context in gray, the group in team colors. */
export function TrajectoryView({ shared, rows, initialMetric }: { shared: SharedChartProps; rows: AdjustedRow[]; initialMetric: TrajectoryMetric }) {
  const [metric, setMetric] = useState<TrajectoryMetric>(initialMetric);
  const data = useMemo(() => trajectorySeries(shared.roster, rows, metric), [shared.roster, rows, metric]);
  return (
    <TrajectoryPanel
      shared={shared}
      kind="trajectory"
      data={data}
      metric={{ ...TRAJECTORY_METRICS[metric], slug: metric }}
      metricControl={<SegmentedControl label="Trajectory metric" options={METRIC_OPTIONS} value={metric} onChange={setMetric} testId="trajectory-metric-switcher" />}
      formatTick={formatEpaTick}
      formatCell={(s, i) => formatEpa(s.values[i]!)}
      figureNote={metric === "defense" ? "Axis inverted: up is better defense (less allowed)." : undefined}
    />
  );
}
