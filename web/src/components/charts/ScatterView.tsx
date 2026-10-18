"use client";

import type { ReactNode } from "react";
import { CHART_REGISTRY, chartSubtitle, exportFilename, groupLabel, type ScatterConfig } from "@/lib/chart-config";
import { domainFor, matchesConference, type ChartKind, type ScatterData, type ScatterPoint, type Side } from "@/lib/charts";
import { ChartFrame, EXPORT_CHART_HEIGHT, EXPORT_SIZE, ExportCard, HighlightStatus, type SharedChartProps } from "./ChartFrame";
import { ScatterChart } from "./ScatterChart";

const SCATTER_VIEW = { width: 1000, height: 640 };

export type ScatterViewProps = {
  shared: SharedChartProps;
  kind: ChartKind;
  side: Side;
  data: ScatterData;
  config: ScatterConfig;
  describe: (point: ScatterPoint) => string;
  /** The chart's metric switcher, in the controls row. */
  controls?: ReactNode;
  /** Metric slug in the PNG name, for charts whose metric switcher changes the data. */
  exportMetric?: string;
  /** Replaces the registry sentence when it depends on the metric. */
  description?: string;
  /** Note under the figure, e.g. the defense inversion. */
  figureNote?: string;
};

/** A team scatter in the shared frame: national geometry, conference filter, highlight and export. */
export function ScatterView({ shared, kind, side, data, config, describe, controls, exportMetric, figureNote, description }: ScatterViewProps) {
  const { season, week, roster, filter, highlight, onHighlight } = shared;
  const title = CHART_REGISTRY[kind].title;
  const subtitle = chartSubtitle(kind, season, week, side);
  const eligibleRoster = roster.filter((r) => matchesConference(filter, r.team, r.conference));
  const points = data.points.filter((p) => matchesConference(filter, p.team, p.conference));
  const unavailable = data.unavailable.filter((team) => eligibleRoster.some((r) => r.team === team));
  const highlightAvailable = points.some((p) => p.team === highlight);
  // Domains come from the national population, so filtering never moves a team.
  const withAverage = (axis: "x" | "y") => [...data.points.map((p) => p[axis]), ...(data.average ? [data.average[axis]] : [])];
  const xDomain = domainFor(withAverage("x"), 0.08);
  const yDomain = domainFor(withAverage("y"), 0.08);

  const chart = (view: { width: number; height: number }, interactive: boolean) => (
    <ScatterChart
      points={points}
      xDomain={xDomain}
      yDomain={yDomain}
      onToggleHighlight={onHighlight}
      average={data.average}
      invertX={data.invertX}
      invertY={data.invertY}
      xLabel={config.xLabel}
      yLabel={config.yLabel}
      width={view.width}
      height={view.height}
      cornerCaptions={config.captions}
      stateOf={(p) => (p.team === highlight ? "searched" : "active")}
      describe={describe}
      formatX={config.tickX}
      formatY={config.tickY}
      interactive={interactive}
      label={`${title}. ${subtitle}`}
    />
  );

  const viewSubtitle = [
    subtitle,
    groupLabel(filter),
    ...(config.metricLabel ? [config.metricLabel] : []),
    `Highlight: ${highlight ?? "None"}${highlight && !highlightAvailable ? " (unavailable in this window)" : ""}`,
  ].join(" | ");

  return (
    <ChartFrame
      shared={shared}
      title={title}
      subtitle={subtitle}
      description={description ?? CHART_REGISTRY[kind].description}
      controls={controls}
      highlightTeams={eligibleRoster}
      exportSpec={{
        filename: exportFilename(kind, season, week, side, exportMetric),
        width: EXPORT_SIZE.width,
        height: EXPORT_SIZE.height,
        card: (
          <ExportCard title={title} subtitle={viewSubtitle} footnote={config.footnote}>
            {chart({ width: EXPORT_SIZE.width - 24, height: EXPORT_CHART_HEIGHT }, false)}
          </ExportCard>
        ),
      }}
      status={<HighlightStatus team={highlight} available={highlightAvailable} week={week} />}
      hasData={points.length > 0}
      figure={
        <>
          <p className="mb-2 text-xs text-ink-muted lg:hidden">Scroll chart horizontally to see every team.</p>
          <div className="overflow-x-auto focus-visible:outline-2 focus-visible:outline-accent" role="region" aria-label="Team scatter chart, horizontally scrollable" tabIndex={0} data-testid="scatter-scroll">
            <div className="min-w-[760px] lg:min-w-0">{chart(SCATTER_VIEW, true)}</div>
          </div>
          {figureNote && <p className="mt-1 text-center text-[11px] text-ink-faint">{figureNote}</p>}
        </>
      }
      unavailable={unavailable}
      footnote={config.footnote}
    />
  );
}
