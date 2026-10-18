"use client";

import type { ReactNode } from "react";
import { CHART_REGISTRY, chartSubtitle, conferenceLabel, exportFilename, groupLabel, type ScatterConfig } from "@/lib/chart-config";
import { domainFor, matchesConference, scatterRanks, type ChartKind, type ScatterData, type ScatterPoint, type Side } from "@/lib/charts";
import { ChartFrame, EXPORT_CHART_HEIGHT, EXPORT_SIZE, ExportCard, HighlightStatus, type SharedChartProps } from "./ChartFrame";
import { ChartTable, type TableColumn } from "./ChartTable";
import { ScatterChart } from "./ScatterChart";

const SCATTER_VIEW = { width: 1000, height: 640 };

export type ScatterViewProps = {
  shared: SharedChartProps;
  kind: ChartKind;
  side: Side;
  data: ScatterData;
  config: ScatterConfig;
  describe: (point: ScatterPoint) => string;
  /** Equal-net diagonals (adjusted chart). */
  netLevels?: readonly number[];
  headerControls?: ReactNode;
  /** Note under the figure, e.g. the defense inversion. */
  figureNote?: string;
};

/** A team scatter in the shared frame: national geometry, conference filter, highlight, table and export. */
export function ScatterView({ shared, kind, side, data, config, describe, netLevels, headerControls, figureNote }: ScatterViewProps) {
  const { season, week, roster, filter, highlight, onHighlight } = shared;
  const title = CHART_REGISTRY[kind].title;
  const subtitle = chartSubtitle(kind, season, week, side);
  const eligibleRoster = roster.filter((r) => matchesConference(filter, r.team, r.conference));
  const points = data.points.filter((p) => matchesConference(filter, p.team, p.conference));
  const unavailable = data.unavailable.filter((team) => eligibleRoster.some((r) => r.team === team));
  const ranks = scatterRanks(data);
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
      netLevels={netLevels}
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

  const columns: TableColumn<ScatterPoint>[] = [
    { key: "team", label: "Team", value: (r) => r.team },
    { key: "conference", label: "Conference", value: (r) => r.conference, format: (r) => conferenceLabel(r.conference) },
    { key: "x", label: config.xLabel, value: (r) => r.x, format: (r) => config.valueX(r.x), numeric: true },
    { key: "xRank", label: `${config.xLabel} national rank`, value: (r) => ranks.get(r.team)?.x ?? null, numeric: true },
    { key: "y", label: config.yLabel, value: (r) => r.y, format: (r) => config.valueY(r.y), numeric: true },
    { key: "yRank", label: `${config.yLabel} national rank`, value: (r) => ranks.get(r.team)?.y ?? null, numeric: true },
    { key: "n", label: "Plays", value: (r) => r.n, numeric: true },
  ];

  return (
    <ChartFrame
      shared={shared}
      title={title}
      subtitle={subtitle}
      headerControls={headerControls}
      highlightTeams={eligibleRoster}
      exportSpec={{
        filename: exportFilename(kind, season, week, side),
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
          <p className="mb-2 text-xs text-ink-muted lg:hidden">Scroll chart horizontally to see every team, or use the table.</p>
          <div className="overflow-x-auto focus-visible:outline-2 focus-visible:outline-accent" role="region" aria-label="Team scatter chart, horizontally scrollable" tabIndex={0} data-testid="scatter-scroll">
            <div className="min-w-[760px] lg:min-w-0">{chart(SCATTER_VIEW, true)}</div>
          </div>
          {figureNote && <p className="mt-1 text-center text-[11px] text-ink-faint">{figureNote}</p>}
        </>
      }
      table={<ChartTable rows={points} columns={columns} rowKey={(r) => r.team} caption={`${title}, ${viewSubtitle}`} initialSort={{ key: "team" }} />}
      unavailable={unavailable}
      footnote={config.footnote}
    />
  );
}
