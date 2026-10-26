"use client";

import { useMemo } from "react";
import { RESUME_QUALITY_CONFIG, describeResumePoint } from "@/lib/chart-config";
import {
  resumeQualityScatterPoints,
  type RatingSnapshotRow,
  type TeamResumeChartRow,
} from "@/lib/charts";
import type { SharedChartProps } from "./ChartFrame";
import { ScatterView } from "./ScatterView";

/** Resume vs dominance: V5 overall rating dominance vs Strength of Record (SOR). */
export function ResumeQualityView({
  shared,
  ratings,
  resumeRows,
}: {
  shared: SharedChartProps;
  ratings: RatingSnapshotRow[];
  resumeRows: TeamResumeChartRow[];
}) {
  const data = useMemo(
    () => resumeQualityScatterPoints(shared.roster, ratings, resumeRows),
    [shared.roster, ratings, resumeRows],
  );
  return (
    <ScatterView
      shared={shared}
      kind="resume-quality"
      side="offense"
      data={data}
      config={RESUME_QUALITY_CONFIG}
      describe={describeResumePoint}
    />
  );
}
