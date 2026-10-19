"use client";

import { useMemo, useState } from "react";
import { EFFICIENCY_METRICS, EXPLOSIVENESS_METRICS, describeEfficiencyPoint, efficiencyConfig } from "@/lib/chart-config";
import { efficiencyPoints, type EfficiencyMetric, type Side, type TeamGameRow } from "@/lib/charts";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import type { SharedChartProps } from "./ChartFrame";
import { ScatterView } from "./ScatterView";

export type EfficiencyViewProps = {
  shared: SharedChartProps;
  side: Side;
  rows: TeamGameRow[];
  initialMetric: EfficiencyMetric;
  /** The release serves yardage (`charts_v2`): offer the 20+ rate / yards-per-success toggle. */
  explosiveness: boolean;
};

/** Cumulative success rate against PPA/play, or an explosiveness metric when yardage is served. */
export function EfficiencyView({ shared, side, rows, initialMetric, explosiveness }: EfficiencyViewProps) {
  const [metric, setMetric] = useState<EfficiencyMetric>(explosiveness ? initialMetric : "ppa");
  const { roster, week } = shared;
  const data = useMemo(() => efficiencyPoints(roster, rows, week, side, metric), [roster, rows, week, side, metric]);

  return (
    <ScatterView
      shared={shared}
      kind="efficiency"
      side={side}
      data={data}
      config={efficiencyConfig(side, metric)}
      description={metric === "ppa" ? "Each team's success rate against its PPA/play." : undefined}
      describe={(point) => describeEfficiencyPoint(point, metric)}
      controls={explosiveness && (
        <SegmentedControl
          size="sm"
          label="Explosiveness metric"
          options={EXPLOSIVENESS_METRICS.map((value) => ({ value, label: EFFICIENCY_METRICS[value].label, testId: `metric-toggle-${value.replaceAll("_", "-")}` }))}
          value={metric}
          onChange={setMetric}
          testId="efficiency-metric-switcher"
        />
      )}
      figureNote={side === "defense" ? "Axes are inverted: up and right is better defense." : undefined}
    />
  );
}
