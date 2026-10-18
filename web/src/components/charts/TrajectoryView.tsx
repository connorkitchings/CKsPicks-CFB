"use client";

import { useMemo, useState } from "react";
import { CHART_REGISTRY, TRAJECTORY_METRICS, chartSubtitle, conferenceLabel, formatEpaTick, groupLabel } from "@/lib/chart-config";
import {
  domainFor,
  formatEpa,
  matchesConference,
  trajectorySeries,
  type AdjustedRow,
  type TrajectoryMetric,
  type TrajectorySeries,
} from "@/lib/charts";
import { ChartFrame, EXPORT_CHART_HEIGHT, EXPORT_SIZE, ExportCard, HighlightStatus, SegmentedControl, type SharedChartProps } from "./ChartFrame";
import { ChartTable, type TableColumn } from "./ChartTable";
import { TrajectoryChart } from "./TrajectoryChart";

const TRAJECTORY_VIEW = { width: 1000, height: 600 };
const METRIC_OPTIONS = (Object.keys(TRAJECTORY_METRICS) as TrajectoryMetric[]).map((value) => ({
  value,
  label: TRAJECTORY_METRICS[value].label,
  testId: `trajectory-metric-${value}`,
}));

function windowText(weeks: readonly number[]): string {
  if (!weeks.length) return "";
  return weeks.length === 1 ? `Through Week ${weeks[0]}` : `Through Weeks ${weeks[0]}–${weeks[weeks.length - 1]}`;
}

/** Adjusted PPA/play of every team across the stored windows: national context in gray, the group in team colors. */
export function TrajectoryView({ shared, rows, initialMetric }: { shared: SharedChartProps; rows: AdjustedRow[]; initialMetric: TrajectoryMetric }) {
  const [metric, setMetric] = useState<TrajectoryMetric>(initialMetric);
  const { season, roster, filter, highlight, onHighlight } = shared;
  const data = useMemo(() => trajectorySeries(roster, rows, metric), [roster, rows, metric]);
  const { weeks } = data;
  const title = CHART_REGISTRY.trajectory.title;
  const footnote = CHART_REGISTRY.trajectory.footnote;
  const metricText = TRAJECTORY_METRICS[metric];
  const subtitle = [metricText.label, chartSubtitle("trajectory", season, 0, "offense"), windowText(weeks)].filter(Boolean).join(" | ");
  const latest = weeks[weeks.length - 1] ?? shared.week;

  const eligibleRoster = roster.filter((r) => matchesConference(filter, r.team, r.conference));
  const groupSeries = data.series.filter((s) => matchesConference(filter, s.team, s.conference));
  const unavailable = data.unavailable.filter((team) => eligibleRoster.some((r) => r.team === team));
  const highlightAvailable = data.series.some((s) => s.team === highlight);
  // The national population sets the domain, so filtering never moves a line.
  const yDomain = domainFor(
    [...data.series.flatMap((s) => s.values), ...data.average].filter((v): v is number => v !== null),
    0.08,
  );
  const stateOf = (s: TrajectorySeries) =>
    s.team === highlight ? "highlight" : filter !== "all" && matchesConference(filter, s.team, s.conference) ? "group" : "context";
  const describe = (s: TrajectorySeries) =>
    `${s.team} (${conferenceLabel(s.conference)}): ${metricText.yLabel} ${s.values
      .map((value, i) => `Through Week ${weeks[i]} ${value === null ? "n/a" : formatEpa(value)}`)
      .join(", ")}`;
  const label = `${title}. ${subtitle}`;
  const viewSubtitle = [subtitle, groupLabel(filter), `Highlight: ${highlight ?? "None"}${highlight && !highlightAvailable ? " (unavailable)" : ""}`].join(" | ");

  const chart = (view: { width: number; height: number }, interactive: boolean) => (
    <TrajectoryChart
      data={data}
      yDomain={yDomain}
      stateOf={stateOf}
      onToggleHighlight={onHighlight}
      describe={describe}
      formatY={formatEpaTick}
      yLabel={metricText.yLabel}
      width={view.width}
      height={view.height}
      interactive={interactive}
      label={label}
    />
  );

  const columns: TableColumn<TrajectorySeries>[] = [
    { key: "team", label: "Team", value: (s) => s.team },
    { key: "conference", label: "Conference", value: (s) => s.conference, format: (s) => conferenceLabel(s.conference) },
    ...weeks.map((week, i): TableColumn<TrajectorySeries> => ({
      key: `w${week}`,
      label: `Through Week ${week}`,
      value: (s) => s.values[i],
      format: (s) => (s.values[i] === null ? "n/a" : formatEpa(s.values[i]!)),
      numeric: true,
    })),
  ];

  return (
    <ChartFrame
      shared={shared}
      title={title}
      subtitle={subtitle}
      headerControls={<SegmentedControl label="Trajectory metric" options={METRIC_OPTIONS} value={metric} onChange={setMetric} testId="trajectory-metric-switcher" />}
      highlightTeams={eligibleRoster}
      exportSpec={{
        filename: `ckspicks-trajectory-${metric}-${season}.png`,
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
          {metric === "defense" && <p className="mt-1 text-center text-[11px] text-ink-faint">Axis inverted: up is better defense (less allowed).</p>}
        </>
      }
      table={<ChartTable rows={groupSeries} columns={columns} rowKey={(s) => s.team} caption={`${title}, ${viewSubtitle}`} initialSort={{ key: "team" }} />}
      unavailable={unavailable}
      footnote={footnote}
    />
  );
}
