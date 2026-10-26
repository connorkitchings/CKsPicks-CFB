"use client";

import { useMemo } from "react";
import { describeFinishingDrivesPoint, finishingDrivesConfig } from "@/lib/chart-config";
import { finishingDrivesScatterPoints, type Side, type TeamSeasonStatRow } from "@/lib/charts";
import type { SharedChartProps } from "./ChartFrame";
import { ScatterView } from "./ScatterView";

/** Finishing drives: scoring opportunity rate vs points per scoring opportunity. */
export function FinishingDrivesView({
  shared,
  rows,
  side,
}: {
  shared: SharedChartProps;
  rows: TeamSeasonStatRow[];
  side: Side;
}) {
  const data = useMemo(
    () => finishingDrivesScatterPoints(shared.roster, rows, side),
    [shared.roster, rows, side],
  );
  return (
    <ScatterView
      shared={shared}
      kind="finishing-drives"
      side={side}
      data={data}
      config={finishingDrivesConfig(side)}
      describe={(point) => describeFinishingDrivesPoint(point, side)}
    />
  );
}
