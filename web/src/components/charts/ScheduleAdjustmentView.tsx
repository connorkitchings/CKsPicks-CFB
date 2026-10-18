"use client";

import { useState, useSyncExternalStore } from "react";
import { CHART_REGISTRY, chartSubtitle, conferenceLabel, describeScheduleRow, exportFilename, groupLabel, scheduleAxisLabel } from "@/lib/chart-config";
import { domainFor, formatEpa, matchesConference, scheduleReading, scheduleSubset, SCHEDULE_EDGE, type ScheduleData, type ScheduleRow } from "@/lib/charts";
import { ChartFrame, EXPORT_SIZE, ExportCard, HighlightStatus, type SharedChartProps } from "./ChartFrame";
import { ChartTable, type TableColumn } from "./ChartTable";
import { ScheduleAdjustmentChart, scheduleChartHeight } from "./ScheduleAdjustmentChart";

const subscribeNarrow = (callback: () => void) => {
  const query = window.matchMedia("(max-width: 639px)");
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
};
const isNarrow = () => window.matchMedia("(max-width: 639px)").matches;
const serverWide = () => false;

/** One dumbbell per team from venue-neutral to opponent-adjusted PPA/play, ordered by schedule effect. */
export function ScheduleAdjustmentView({ shared, data }: { shared: SharedChartProps; data: ScheduleData }) {
  const [showAll, setShowAll] = useState(false);
  const narrow = useSyncExternalStore(subscribeNarrow, isNarrow, serverWide);
  const { season, week, roster, filter, highlight, onHighlight } = shared;
  const { side } = data;
  const { title, footnote } = CHART_REGISTRY.schedule;
  const subtitle = chartSubtitle("schedule", season, week, side);
  const eligibleRoster = roster.filter((r) => matchesConference(filter, r.team, r.conference));
  const group = data.rows.filter((r) => matchesConference(filter, r.team, r.conference));
  const unavailable = data.unavailable.filter((team) => eligibleRoster.some((r) => r.team === team));
  const subset = scheduleSubset(group, { showAll, highlight });
  const truncatable = scheduleSubset(group, { showAll: false, highlight: null }).bottom.length > 0;
  const position = new Map(group.map((row, index) => [row.team, index + 1]));
  const highlightAvailable = position.has(highlight ?? "");
  // The domain covers the national population, so filtering never moves a team.
  const domain = domainFor(data.rows.flatMap((r) => [r.neutral, r.adjusted]), 0.06);
  const axisLabel = scheduleAxisLabel(side);
  const describe = (row: ScheduleRow) => describeScheduleRow(row, side);
  const label = `${title}. ${subtitle}`;
  const drawn = [...subset.top, ...subset.bottom, ...(subset.extra ? [subset.extra.row] : [])];

  const viewSubtitle = [
    subtitle,
    groupLabel(filter),
    `Highlight: ${highlight ?? "None"}${highlight && !highlightAvailable ? " (unavailable in this window)" : ""}`,
  ].join(" | ");
  const exportChartWidth = EXPORT_SIZE.width - 24;
  const exportHeight = Math.max(EXPORT_SIZE.height, EXPORT_SIZE.header + EXPORT_SIZE.footer + scheduleChartHeight(subset, exportChartWidth));
  const unit = side === "defense" ? " allowed" : "";

  const columns: TableColumn<ScheduleRow>[] = [
    { key: "position", label: "Position", value: (r) => position.get(r.team) ?? null, numeric: true },
    { key: "team", label: "Team", value: (r) => r.team },
    { key: "conference", label: "Conference", value: (r) => r.conference, format: (r) => conferenceLabel(r.conference) },
    { key: "raw", label: `Raw PPA/play${unit}`, value: (r) => r.raw, format: (r) => formatEpa(r.raw), numeric: true },
    { key: "venue", label: "Venue correction", value: (r) => r.venueCorrection, format: (r) => formatEpa(r.venueCorrection), numeric: true },
    { key: "neutral", label: "Venue-neutral", value: (r) => r.neutral, format: (r) => formatEpa(r.neutral), numeric: true },
    { key: "adjusted", label: "Adjusted", value: (r) => r.adjusted, format: (r) => formatEpa(r.adjusted), numeric: true },
    { key: "effect", label: "Schedule effect", value: (r) => r.effect, format: (r) => formatEpa(r.effect), numeric: true },
    { key: "reading", label: "Reading", value: (r) => scheduleReading(r.effect) },
    { key: "plays", label: "Plays", value: (r) => r.epaN, numeric: true },
  ];

  const chart = (width: number, interactive: boolean) => (
    <ScheduleAdjustmentChart
      subset={subset}
      domain={domain}
      invert={data.invert}
      axisLabel={axisLabel}
      highlight={highlight}
      onToggleHighlight={onHighlight}
      describe={describe}
      width={width}
      interactive={interactive}
      label={label}
    />
  );

  return (
    <ChartFrame
      shared={shared}
      title={title}
      subtitle={subtitle}
      highlightTeams={eligibleRoster}
      controls={truncatable && (
        <button
          type="button"
          aria-pressed={showAll}
          onClick={() => setShowAll((current) => !current)}
          className="min-h-9 rounded-lg border border-line bg-surface-card px-3 py-1.5 text-xs font-medium text-ink hover:border-accent hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent aria-pressed:border-accent aria-pressed:text-accent-ink"
          data-testid="schedule-show-all"
        >
          {showAll ? `Show top and bottom ${SCHEDULE_EDGE}` : `Show all ${group.length}`}
        </button>
      )}
      exportSpec={{
        filename: exportFilename("schedule", season, week, side),
        width: EXPORT_SIZE.width,
        height: exportHeight,
        card: (
          <ExportCard title={title} subtitle={viewSubtitle} footnote={footnote}>
            {chart(exportChartWidth, false)}
          </ExportCard>
        ),
      }}
      status={<HighlightStatus team={highlight} available={highlightAvailable} week={week} />}
      hasData={group.length > 0}
      figure={
        <>
          {chart(narrow ? 400 : 1000, true)}
          {side === "defense" && (
            <p className="mt-1 text-center text-[11px] text-ink-faint" data-testid="schedule-inverted-note">
              Defense plots PPA/play allowed with the axis inverted: better (fewer allowed) is to the right.
            </p>
          )}
        </>
      }
      table={<ChartTable rows={drawn} columns={columns} rowKey={(r) => r.team} caption={`${title}, ${viewSubtitle}`} initialSort={{ key: "position" }} />}
      unavailable={unavailable}
      footnote={footnote}
    />
  );
}
