"use client";

import { useEffect, useState, type ReactNode } from "react";
import { CHART_REGISTRY, chartSubtitle, exportFilename, groupLabel, type ScatterConfig } from "@/lib/chart-config";
import { domainFor, matchesConference, type ChartKind, type ScatterData, type ScatterPoint, type Side } from "@/lib/charts";
import { ChartFrame, mobileSummary, EXPORT_CHART_HEIGHT, EXPORT_SIZE, ExportCard, HighlightStatus, type SharedChartProps } from "./ChartFrame";
import { ScatterChart } from "./ScatterChart";
import { useMobileChart } from "./useMobileChart";

const SCATTER_VIEW = { width: 1000, height: 640 };
/** Phone portrait view: the viewBox follows the container width (1:1 scale, so text is true size) in a tall aspect. */
const MOBILE_FALLBACK_WIDTH = 360;
const MOBILE_ASPECT = 1.45;
const mobileView = (width: number) => ({ width, height: Math.round(width * MOBILE_ASPECT) });

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
};

/** A team scatter in the shared frame: national geometry, conference filter, highlight and export. */
export function ScatterView({ shared, kind, side, data, config, describe, controls, exportMetric, description }: ScatterViewProps) {
  const mobile = useMobileChart();
  const [fitNode, setFitNode] = useState<HTMLDivElement | null>(null);
  const [fitWidth, setFitWidth] = useState(MOBILE_FALLBACK_WIDTH);
  useEffect(() => {
    if (!mobile || !fitNode) return;
    const observer = new ResizeObserver(([entry]) => setFitWidth(Math.round(entry.contentRect.width) || MOBILE_FALLBACK_WIDTH));
    observer.observe(fitNode);
    return () => observer.disconnect();
  }, [mobile, fitNode]);
  const [detailsContainer, setDetailsContainer] = useState<HTMLDivElement | null>(null);
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
      highlight={highlight}
      average={data.average}
      invertX={data.invertX}
      invertY={data.invertY}
      xLabel={config.xLabel}
      yLabel={config.yLabel}
      width={view.width}
      height={view.height}
      cornerCaptions={config.captions}
      averageNames={config.averageNames}
      stateOf={(p) => (p.team === highlight ? "searched" : "active")}
      describe={describe}
      formatX={config.tickX}
      formatY={config.tickY}
      interactive={interactive}
      detailsContainer={interactive ? detailsContainer : undefined}
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
      summary={mobileSummary({ side: CHART_REGISTRY[kind].controls.side ? side : null, week: { n: week, through: CHART_REGISTRY[kind].controls.week === "through-week" }, filter, metric: config.metricLabel })}
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
          {mobile ? (
            <div ref={setFitNode} data-testid="scatter-fit">{chart(mobileView(fitWidth), true)}</div>
          ) : (
            <>
              <p className="mb-2 text-xs text-ink-muted lg:hidden">Scroll chart horizontally to see every team.</p>
              <div className="overflow-x-auto focus-visible:outline-2 focus-visible:outline-accent" role="region" aria-label="Team scatter chart, horizontally scrollable" tabIndex={0} data-testid="scatter-scroll">
                <div className="min-w-[760px] lg:min-w-0">{chart(SCATTER_VIEW, true)}</div>
              </div>
            </>
          )}
          <div ref={setDetailsContainer} />
        </>
      }
      unavailable={unavailable}
      footnote={config.footnote}
    />
  );
}
