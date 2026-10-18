"use client";

import { ADJUSTED_CONFIG, describeAdjustedPoint } from "@/lib/chart-config";
import type { AdjustedScatter } from "@/lib/charts";
import type { SharedChartProps } from "./ChartFrame";
import { ScatterView } from "./ScatterView";

/** Opponent-adjusted offense against defense allowed, with labeled equal-net diagonals. */
export function AdjustedView({ shared, scatter }: { shared: SharedChartProps; scatter: AdjustedScatter }) {
  return (
    <ScatterView
      shared={shared}
      kind="adjusted"
      side="offense"
      data={scatter}
      config={ADJUSTED_CONFIG}
      describe={(point) => describeAdjustedPoint(point, scatter.roles)}
      netLevels={scatter.netLevels}
    />
  );
}
