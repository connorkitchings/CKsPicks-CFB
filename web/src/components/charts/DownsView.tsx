"use client";

import { useMemo } from "react";
import { describeDownsPoint, downsConfig } from "@/lib/chart-config";
import { downsScatterPoints, type Side, type TeamSeasonStatRow } from "@/lib/charts";
import type { SharedChartProps } from "./ChartFrame";
import { ScatterView } from "./ScatterView";

/** Situational downs: early-down EPA vs 3rd/4th down conversion rate. */
export function DownsView({
  shared,
  rows,
  side,
}: {
  shared: SharedChartProps;
  rows: TeamSeasonStatRow[];
  side: Side;
}) {
  const data = useMemo(
    () => downsScatterPoints(shared.roster, rows, side),
    [shared.roster, rows, side],
  );
  return (
    <ScatterView
      shared={shared}
      kind="downs"
      side={side}
      data={data}
      config={downsConfig(side)}
      describe={(point) => describeDownsPoint(point, side)}
    />
  );
}
