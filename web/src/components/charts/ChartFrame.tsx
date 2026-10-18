"use client";

import { useState, type ReactNode } from "react";
import clsx from "clsx";
import { conferenceOptions, type ConferenceFilter, type NotCharted, type RosterRow } from "@/lib/charts";
import { ChartExportButton } from "./ChartExportButton";
import { TeamHighlightCombobox } from "./TeamHighlightCombobox";

/**
 * State every chart view shares, owned by `ChartsView` so it survives switching charts:
 * the conference filter and the highlighted team (mirrored in the `team=` URL param).
 */
export type SharedChartProps = {
  season: number;
  /** The chart's week, or the N of "Through Week N". */
  week: number;
  roster: RosterRow[];
  filter: ConferenceFilter;
  onFilterChange: (filter: ConferenceFilter) => void;
  highlight: string | null;
  /** A team toggles its highlight; null clears it. */
  onHighlight: (team: string | null) => void;
};

// Exports are captured at 2x: 1000 x 562.5 CSS px is a 2000 x 1125 px PNG.
export const EXPORT_SIZE = { width: 1000, height: 562.5, header: 70, footer: 50 };
/** Height left for the chart inside an export card. */
export const EXPORT_CHART_HEIGHT = EXPORT_SIZE.height - EXPORT_SIZE.header - EXPORT_SIZE.footer;

/** The static card a PNG export captures: title, subtitle, chart and footnote. */
export function ExportCard({ title, subtitle, footnote, children }: { title: string; subtitle: string; footnote: string; children: ReactNode }) {
  return (
    <div className="flex h-full flex-col" data-testid="export-card">
      <div className="px-5 pt-3" style={{ height: EXPORT_SIZE.header }}>
        <div className="text-2xl font-bold tracking-tight text-ink">{title}</div>
        <div className="text-sm text-ink-muted">{subtitle}</div>
      </div>
      <div className="min-h-0 flex-1 px-3">{children}</div>
      <div className="px-5 text-[11px] leading-snug text-ink-muted" style={{ height: EXPORT_SIZE.footer }}>
        {footnote} ckspicks-cfb.vercel.app
      </div>
    </div>
  );
}

/** `Highlight: X` status line of the team-highlight charts. */
export function HighlightStatus({ team, available, week }: { team: string | null; available: boolean; week: number }) {
  if (!team) return null;
  return (
    <p role="status" className="text-xs text-ink-muted" data-testid="highlight-status">
      Highlight: {team}{available ? ". Click again or clear to unhighlight." : ` — no available observation Through Week ${week}.`}
    </p>
  );
}

/** Segmented button group (metric switchers, sort toggles). */
export function SegmentedControl<Value extends string>({
  label,
  options,
  value,
  onChange,
  testId,
  showLabel = false,
}: {
  /** Group name for assistive tech; also shown as lead-in text when `showLabel`. */
  label: string;
  showLabel?: boolean;
  options: readonly { value: Value; label: string; testId: string }[];
  value: Value;
  onChange: (value: Value) => void;
  testId: string;
}) {
  return (
    <div className="flex items-center gap-2" role="group" aria-label={label} data-testid={testId}>
      {showLabel && <span className="text-xs font-semibold text-ink-muted" aria-hidden>{label}</span>}
      <div className="inline-flex gap-1 rounded-lg border border-line bg-surface-card p-1 shadow-2xs">
        {options.map((option) => (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            aria-pressed={value === option.value}
            className={clsx(
              "inline-flex min-h-8 items-center rounded-md px-3 py-1 text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
              value === option.value ? "bg-ink text-surface-card shadow-2xs" : "text-ink-muted hover:bg-surface-inset hover:text-ink",
            )}
            data-testid={option.testId}
          >
            {option.label}
          </button>
        ))}
      </div>
    </div>
  );
}

export type ChartFrameProps = {
  shared: SharedChartProps;
  title: string;
  subtitle: string;
  /** Right side of the header (e.g. the efficiency metric switcher). */
  headerControls?: ReactNode;
  /** Teams offered by the highlight picker; omitted for charts without a highlight. */
  highlightTeams?: readonly RosterRow[];
  /** Extra controls after the filter and highlight picker (e.g. a sort toggle). */
  controls?: ReactNode;
  /** PNG export of `card`, offered while the chart has data. */
  exportSpec: { filename: string; width: number; height: number; card: ReactNode };
  /** Lines between the controls and the figure (highlight status, summaries). */
  status?: ReactNode;
  hasData: boolean;
  emptyText?: string;
  /** The interactive chart, inside the `chart-figure` card. */
  figure: ReactNode;
  /** The same rows as a sortable `ChartTable`, shown by the table toggle. */
  table: ReactNode;
  notCharted?: readonly NotCharted[];
  /** Roster teams the chart could not plot. */
  unavailable?: readonly string[];
  footnote: string;
};

/** Header, controls, export, table toggle, not-plotted lists and footnote shared by every chart. */
export function ChartFrame({
  shared,
  title,
  subtitle,
  headerControls,
  highlightTeams,
  controls,
  exportSpec,
  status,
  hasData,
  emptyText = "No teams can be charted for this week yet.",
  figure,
  table,
  notCharted = [],
  unavailable = [],
  footnote,
}: ChartFrameProps) {
  const [asTable, setAsTable] = useState(false);
  const { roster, filter, onFilterChange, highlight, onHighlight } = shared;

  return (
    <section className="space-y-3" aria-label={title}>
      <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-bold tracking-tight text-ink sm:text-xl">{title}</h2>
          <p className="text-xs text-ink-muted sm:text-sm" data-testid="chart-subtitle">
            {subtitle}
          </p>
        </div>
        {headerControls}
      </header>

      <div className="flex flex-col gap-3 rounded-xl border border-line bg-surface-inset p-2.5 sm:flex-row sm:items-center sm:justify-between sm:p-3" data-testid="chart-controls">
        <div className="flex flex-wrap items-center gap-2.5" role="group" aria-label="Chart controls">
          <select
            className="min-h-9 rounded-lg border border-line bg-surface-card px-3 py-1.5 text-xs font-medium text-ink focus:outline-none focus:ring-2 focus:ring-accent"
            value={filter}
            onChange={(event) => onFilterChange(event.target.value)}
            data-testid="conference-filter"
            aria-label="Filter by conference"
          >
            <option value="all">All FBS</option>
            <option value="p4">Power Four + Notre Dame</option>
            {conferenceOptions(roster).map((conference) => (
              <option key={conference} value={conference}>
                {conference}
              </option>
            ))}
          </select>
          {highlightTeams && <TeamHighlightCombobox teams={highlightTeams} highlight={highlight} onSelect={onHighlight} />}
          {controls}
        </div>
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Chart display and export">
          <button
            type="button"
            aria-pressed={asTable}
            onClick={() => setAsTable((current) => !current)}
            className="min-h-9 rounded-lg border border-line bg-surface-card px-3 py-1.5 text-xs font-medium text-ink hover:border-accent hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent aria-pressed:border-accent aria-pressed:text-accent-ink"
            data-testid="table-toggle"
          >
            {asTable ? "Show chart" : "Show as table"}
          </button>
          {hasData && (
            <ChartExportButton filename={exportSpec.filename} width={exportSpec.width} height={exportSpec.height}>
              {exportSpec.card}
            </ChartExportButton>
          )}
        </div>
      </div>

      {status}
      {!hasData ? (
        <p role="status" className="rounded-xl border border-line bg-surface-card p-5 text-ink-muted" data-testid="chart-empty">
          {emptyText}
        </p>
      ) : asTable ? (
        table
      ) : (
        <div className="rounded-xl border border-line bg-surface-card p-2 sm:p-3" data-testid="chart-figure">
          {figure}
        </div>
      )}

      {notCharted.length > 0 && (
        <p className="text-xs text-ink-muted" data-testid="not-charted">
          Not charted ({notCharted.length}): {notCharted.map((n) => `game ${n.gameId} (${n.reason})`).join(", ")}.
        </p>
      )}
      {unavailable.length > 0 && (
        <details className="rounded-xl border border-line bg-surface-card px-3 py-2 text-xs text-ink-muted" data-testid="unavailable-teams">
          <summary className="cursor-pointer font-semibold text-ink">Not plotted ({unavailable.length} teams)</summary>
          <p className="mt-1.5 leading-relaxed">
            {unavailable.join(", ")}. These teams have no eligible FBS games or no valid observations for this chart yet.
          </p>
        </details>
      )}
      <p className="text-[11px] leading-relaxed text-ink-faint">{footnote}</p>
    </section>
  );
}
