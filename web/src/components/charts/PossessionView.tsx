"use client";

import { useMemo, useState } from "react";
import { POSSESSION_METRICS, describePossessionPoint, possessionConfig } from "@/lib/chart-config";
import { possessionPoints, type PossessionMetric, type PossessionRow } from "@/lib/charts";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import type { SharedChartProps } from "./ChartFrame";
import { ScatterView } from "./ScatterView";

const METRIC_OPTIONS = (Object.keys(POSSESSION_METRICS) as PossessionMetric[]).map((value) => ({
  value,
  label: POSSESSION_METRICS[value].label,
  testId: `possession-metric-${value.replaceAll("_", "-")}`,
}));

/** Opponent-adjusted possession offense against defense allowed, with averages and corner labels. */
export function PossessionView({ shared, rows, initialMetric }: { shared: SharedChartProps; rows: PossessionRow[]; initialMetric: PossessionMetric }) {
  const [metric, setMetric] = useState<PossessionMetric>(initialMetric);
  const scatter = useMemo(() => possessionPoints(shared.roster, rows, metric), [shared.roster, rows, metric]);
  return (
    <ScatterView
      shared={shared}
      kind="possession"
      side="offense"
      data={scatter}
      config={possessionConfig(metric)}
      describe={(point) => describePossessionPoint(point, scatter, metric)}
      exportMetric={POSSESSION_METRICS[metric].slug}
      controls={<SegmentedControl size="sm" label="Possession measurement" options={METRIC_OPTIONS} value={metric} onChange={setMetric} testId="possession-metric-switcher" />}
    />
  );
}
