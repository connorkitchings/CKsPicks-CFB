"use client";

import { useMemo, useState } from "react";
import { RATING_METRICS, describeRatingPoint, formatRating } from "@/lib/chart-config";
import { ratingTrajectorySeries, type RatingMetric, type RatingSnapshotRow, type RatingTrajectorySeries } from "@/lib/charts";
import { SegmentedControl, type SharedChartProps } from "./ChartFrame";
import { TrajectoryPanel } from "./TrajectoryPanel";

const METRIC_OPTIONS = (Object.keys(RATING_METRICS) as RatingMetric[]).map((value) => ({
  value,
  label: RATING_METRICS[value].label,
  testId: `rating-metric-${value}`,
}));

/** Index of the series' last week with a rating (every series has one). */
function lastIndex(series: RatingTrajectorySeries): number {
  return series.values.findLastIndex((value) => value !== null);
}

/** V5 model rating of every team after each week's games, against the weekly FBS mean. */
export function RatingTrajectoryView({ shared, rows, initialMetric }: { shared: SharedChartProps; rows: RatingSnapshotRow[]; initialMetric: RatingMetric }) {
  const [metric, setMetric] = useState<RatingMetric>(initialMetric);
  const data = useMemo(() => ratingTrajectorySeries(shared.roster, rows, metric), [shared.roster, rows, metric]);
  return (
    <TrajectoryPanel
      shared={shared}
      kind="rating-trajectory"
      data={data}
      metric={{ ...RATING_METRICS[metric], slug: metric }}
      metricControl={<SegmentedControl label="Rating component" options={METRIC_OPTIONS} value={metric} onChange={setMetric} testId="rating-metric-switcher" />}
      formatTick={formatRating}
      formatCell={(s, i) => `${formatRating(s.values[i]!)}${s.sd[i] === null ? "" : ` ± ${formatRating(s.sd[i]!)}`}`}
      tooltip={(s) => describeRatingPoint(data, s, lastIndex(s), metric)}
      averageLabel="FBS mean"
      figureNote="V5 model rating scale (not PPA/play), not centered at zero; higher is better, defense included. Dashed line: weekly FBS mean."
    />
  );
}
