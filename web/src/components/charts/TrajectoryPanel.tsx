"use client";

import type { ReactNode } from "react";
import { CHART_REGISTRY, chartSubtitle, conferenceLabel, exportFilename, groupLabel } from "@/lib/chart-config";
import { domainFor, matchesConference, type TrajectorySeries } from "@/lib/charts";
import { ChartFrame, EXPORT_CHART_HEIGHT, EXPORT_SIZE, ExportCard, HighlightStatus, type SharedChartProps } from "./ChartFrame";
import { ChartTable, type TableColumn } from "./ChartTable";
import { TrajectoryChart, type TrajectoryChartData } from "./TrajectoryChart";

const TRAJECTORY_VIEW = { width: 1000, height: 600 };

function windowText(weeks: readonly number[]): string {
  if (!weeks.length) return "";
  return weeks.length === 1 ? `Through Week ${weeks[0]}` : `Through Weeks ${weeks[0]}–${weeks[weeks.length - 1]}`;
}

export type TrajectoryPanelProps<S extends TrajectorySeries> = {
  shared: SharedChartProps;
  kind: "trajectory" | "rating-trajectory";
  data: TrajectoryChartData<S>;
  /** Selected metric: switcher text (subtitle lead) and export-name slug. */
  metric: { label: string; slug: string; yLabel: string };
  metricControl: ReactNode;
  formatTick: (value: number) => string;
  /** Table cell (and accessible-name value) of week index `index`; the value is never null here. */
  formatCell: (series: S, index: number) => string;
  tooltip?: (series: S) => string;
  averageLabel?: string;
  figureNote?: string;
};

/**
 * Every team's line across the stored windows in the shared frame: national context in
 * gray, the conference group in team colors, the highlighted team bold, with table and
 * PNG export. The national population sets the domain, so filtering never moves a line.
 */
export function TrajectoryPanel<S extends TrajectorySeries>({
  shared,
  kind,
  data,
  metric,
  metricControl,
  formatTick,
  formatCell,
  tooltip,
  averageLabel,
  figureNote,
}: TrajectoryPanelProps<S>) {
  const { season, roster, filter, highlight, onHighlight } = shared;
  const { weeks } = data;
  const { title, footnote } = CHART_REGISTRY[kind];
  const subtitle = [metric.label, chartSubtitle(kind, season, 0, "offense"), windowText(weeks)].filter(Boolean).join(" | ");
  const latest = weeks[weeks.length - 1] ?? shared.week;

  const eligibleRoster = roster.filter((r) => matchesConference(filter, r.team, r.conference));
  const groupSeries = data.series.filter((s) => matchesConference(filter, s.team, s.conference));
  const unavailable = data.unavailable.filter((team) => eligibleRoster.some((r) => r.team === team));
  const highlightAvailable = data.series.some((s) => s.team === highlight);
  const yDomain = domainFor(
    [...data.series.flatMap((s) => s.values), ...data.average].filter((v): v is number => v !== null),
    0.08,
  );
  const stateOf = (s: S) =>
    s.team === highlight ? "highlight" : filter !== "all" && matchesConference(filter, s.team, s.conference) ? "group" : "context";
  const cell = (s: S, i: number) => (s.values[i] === null ? "n/a" : formatCell(s, i));
  const describe = (s: S) =>
    `${s.team} (${conferenceLabel(s.conference)}): ${metric.yLabel} ${weeks.map((week, i) => `Through Week ${week} ${cell(s, i)}`).join(", ")}`;
  const label = `${title}. ${subtitle}`;
  const viewSubtitle = [subtitle, groupLabel(filter), `Highlight: ${highlight ?? "None"}${highlight && !highlightAvailable ? " (unavailable)" : ""}`].join(" | ");

  const chart = (view: { width: number; height: number }, interactive: boolean) => (
    <TrajectoryChart
      data={data}
      yDomain={yDomain}
      stateOf={stateOf}
      onToggleHighlight={onHighlight}
      describe={describe}
      tooltip={tooltip}
      averageLabel={averageLabel}
      formatY={formatTick}
      yLabel={metric.yLabel}
      width={view.width}
      height={view.height}
      interactive={interactive}
      label={label}
    />
  );

  const columns: TableColumn<S>[] = [
    { key: "team", label: "Team", value: (s) => s.team },
    { key: "conference", label: "Conference", value: (s) => s.conference, format: (s) => conferenceLabel(s.conference) },
    ...weeks.map((week, i): TableColumn<S> => ({
      key: `w${week}`,
      label: `Through Week ${week}`,
      value: (s) => s.values[i],
      format: (s) => cell(s, i),
      numeric: true,
    })),
  ];

  return (
    <ChartFrame
      shared={shared}
      title={title}
      subtitle={subtitle}
      controls={metricControl}
      highlightTeams={eligibleRoster}
      exportSpec={{
        filename: exportFilename(kind, season, latest, "offense", metric.slug),
        width: EXPORT_SIZE.width,
        height: EXPORT_SIZE.height,
        card: (
          <ExportCard title={title} subtitle={viewSubtitle} footnote={footnote}>
            {chart({ width: EXPORT_SIZE.width - 24, height: EXPORT_CHART_HEIGHT }, false)}
          </ExportCard>
        ),
      }}
      status={<HighlightStatus team={highlight} available={highlightAvailable} week={latest} />}
      hasData={data.series.length > 0}
      figure={
        <>
          <p className="mb-2 text-xs text-ink-muted lg:hidden">Scroll chart horizontally, or use the table.</p>
          <div className="overflow-x-auto focus-visible:outline-2 focus-visible:outline-accent" role="region" aria-label="Team trajectory chart, horizontally scrollable" tabIndex={0} data-testid="trajectory-scroll">
            <div className="min-w-[760px] lg:min-w-0">{chart(TRAJECTORY_VIEW, true)}</div>
          </div>
          {figureNote && <p className="mt-1 text-center text-[11px] text-ink-faint">{figureNote}</p>}
        </>
      }
      table={<ChartTable rows={groupSeries} columns={columns} rowKey={(s) => s.team} caption={`${title}, ${viewSubtitle}`} initialSort={{ key: "team" }} />}
      unavailable={unavailable}
      footnote={footnote}
    />
  );
}
