"use client";

import { useState } from "react";
import { EFFICIENCY_METRICS, EXPLOSIVENESS_METRICS, describeEfficiencyPoint, efficiencyConfig } from "@/lib/chart-config";
import type { EfficiencyMetric, ScatterData, Side } from "@/lib/charts";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import type { SharedChartProps } from "./ChartFrame";
import { ScatterView } from "./ScatterView";

/** Per-metric points for the page's week and side, aggregated on the server (not the game rows). */
export type EfficiencyData = Partial<Record<EfficiencyMetric, ScatterData>>;

export type EfficiencyViewProps = {
  shared: SharedChartProps;
  side: Side;
  data: EfficiencyData;
  initialMetric: EfficiencyMetric;
  /** The release serves yardage (`charts_v2`): offer the 20+ rate / yards-per-success toggle. */
  explosiveness: boolean;
};

/** Cumulative success rate against PPA/play, or an explosiveness metric when yardage is served. */
export function EfficiencyView({ shared, side, data: byMetric, initialMetric, explosiveness }: EfficiencyViewProps) {
  const [metric, setMetric] = useState<EfficiencyMetric>(explosiveness ? initialMetric : "ppa");
  const data = byMetric[metric] ?? byMetric.ppa!;

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
    />
  );
}
