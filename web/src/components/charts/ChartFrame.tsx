"use client";

import { useState, type ReactNode } from "react";
import { footnoteLines, groupLabel } from "@/lib/chart-config";
import { conferenceOptions, type ConferenceFilter, type NotCharted, type RosterRow, type Side } from "@/lib/charts";
import { ChartExportButton } from "./ChartExportButton";
import { MobileChartSettings } from "./MobileChartSettings";
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
  /** URL-backed settings rendered by the page (side links, week stepper), placed before `controls`. */
  settings?: ReactNode;
};

/**
 * The one phone summary line of every chart, "·"-joined and without the season (the site
 * header shows it): `Alabama · Offense · Through Week 7 · All FBS · 20+ yard rate`. `scope` stands in
 * for an unfiltered conference ("FBS opponents" on the game log).
 */
export function mobileSummary({ team, side, week, filter, scope, metric }: {
  team?: string | null;
  side?: Side | null;
  week?: { n: number; through: boolean } | null;
  filter: ConferenceFilter;
  scope?: string;
  metric?: string | null;
}): string {
  const conference = scope && filter === "all" ? scope : groupLabel(filter);
  return [
    team,
    side ? (side === "offense" ? "Offense" : "Defense") : null,
    week ? `${week.through ? "Through Week" : "Week"} ${week.n}` : null,
    conference,
    metric,
  ].filter(Boolean).join(" · ");
}

// Exports are captured at 2x: 1000 x 562.5 CSS px is a 2000 x 1125 px PNG.
export const EXPORT_SIZE = { width: 1000, height: 562.5, header: 70, footer: 86 };
/** Height left for the chart inside an export card. */
export const EXPORT_CHART_HEIGHT = EXPORT_SIZE.height - EXPORT_SIZE.header - EXPORT_SIZE.footer;

/**
 * A " | "-joined subtitle as quiet meta text with "·" separators. Only the display changes:
 * callers keep the " | " string for aria labels, table captions and filenames.
 */
export function SubtitleText({ subtitle }: { subtitle: string }) {
  return subtitle.split(" | ").map((part, index) => (
    <span key={index}>
      {index > 0 && <span className="text-ink-faint"> · </span>}
      {part}
    </span>
  ));
}

/** The static card a PNG export captures: title (with an optional credit), subtitle, chart and footnote. */
export function ExportCard({ title, subtitle, credit, footnote, children }: { title: string; subtitle: string; credit?: string; footnote: string; children: ReactNode }) {
  return (
    <div className="flex h-full flex-col" data-testid="export-card">
      <div className="px-5 pt-3" style={{ height: EXPORT_SIZE.header }}>
        <div className="flex items-baseline justify-between gap-6">
          <div className="text-2xl font-bold tracking-tight text-ink">{title}</div>
          {credit && <div className="shrink-0 text-xs text-ink-muted">{credit}</div>}
        </div>
        <div className="text-sm text-ink-muted">
          <SubtitleText subtitle={subtitle} />
        </div>
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

export type ChartFrameProps = {
  shared: SharedChartProps;
  title: string;
  /** Metadata line ("Week 7 | 2026 | FBS vs FBS"): read by assistive tech and printed in the PNG export. */
  subtitle: string;
  /** The one plain sentence shown under the title; falls back to the visible subtitle without one. */
  description?: string;
  /** Quiet attribution line under the subtitle (the registry's `credit`). */
  credit?: string;
  /** Right end of the title row (a key figure); wraps under the subtitle on narrow screens. */
  headerControls?: ReactNode;
  /** Teams offered by the highlight picker; omitted for charts without a highlight. */
  highlightTeams?: readonly RosterRow[];
  /** The chart's own settings (metric or sort toggle), after the page's side and week settings. */
  controls?: ReactNode;
  /** The phone summary row, built with `mobileSummary`. */
  summary: string;
  /** PNG export of `card`, offered while the chart has data. */
  exportSpec: { filename: string; width: number; height: number; card: ReactNode };
  /** A compact line between the header hairline and the figure (highlight status, summaries). */
  status?: ReactNode;
  hasData: boolean;
  emptyText?: string;
  /** The interactive chart, inside the `chart-figure` card. */
  figure: ReactNode;
  /** The same rows as a sortable `ChartTable` behind a "Show as table" toggle; the visible charts pass none. */
  table?: ReactNode;
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
  description,
  credit,
  headerControls,
  highlightTeams,
  controls,
  summary,
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
  const { roster, filter, onFilterChange, highlight, onHighlight, settings } = shared;

  return (
    <section className="space-y-3" aria-label={title}>
      {/* One row of every setting: filter, highlight, side, week, metric/sort; display and export at the right end. */}
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-2" data-testid="chart-controls">
        <MobileChartSettings finder={highlightTeams && <TeamHighlightCombobox teams={highlightTeams} highlight={highlight} onSelect={onHighlight} />} summary={summary} conference={
          <select
            className="min-h-11 max-w-full rounded-lg border border-line bg-surface-card px-3 py-1.5 text-sm font-medium text-ink focus:outline-none focus:ring-2 focus:ring-accent sm:min-h-9 sm:text-xs"
            value={filter}
            onChange={(event) => onFilterChange(event.target.value)}
            data-testid="conference-filter"
            aria-label="Filter by conference"
          >
            <option value="all">All FBS</option>
            <option value="p4">Power Four + Notre Dame</option>
            {conferenceOptions(roster).map((conference) => <option key={conference} value={conference}>{conference}</option>)}
          </select>
        }>
          {settings}
          {controls}
        </MobileChartSettings>
        <div className="order-2 ml-auto flex flex-wrap items-center gap-2" role="group" aria-label="Chart display and export">
          {table && (
            <button
              type="button"
              aria-pressed={asTable}
              onClick={() => setAsTable((current) => !current)}
              className="min-h-11 rounded-lg border border-line bg-surface-card px-3 py-1.5 sm:min-h-9 text-xs font-medium text-ink hover:border-accent hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent aria-pressed:border-accent aria-pressed:text-accent-ink"
              data-testid="table-toggle"
            >
              {asTable ? "Show chart" : "Show as table"}
            </button>
          )}
          {hasData && (
            <ChartExportButton filename={exportSpec.filename} shareTitle={title} width={exportSpec.width} height={exportSpec.height}>
              {exportSpec.card}
            </ChartExportButton>
          )}
        </div>
      </div>

      {/* One card: header (title, meta, header controls with the credit beneath), hairline, status, then the chart or table. */}
      <div data-card="" className="rounded-xl border border-line bg-surface-card shadow-2xs">
        <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2.5 px-3 py-3 sm:px-4">
          <div className="min-w-0">
            <h2 className="text-lg font-bold leading-tight tracking-tight text-ink sm:text-xl">{title}</h2>
            {description && <p className="mt-1 text-xs text-ink-muted sm:text-[13px]" data-testid="chart-description">{description}</p>}
            <p className={description ? "sr-only" : "mt-1 text-xs text-ink-muted sm:text-[13px]"} data-testid="chart-subtitle">
              <SubtitleText subtitle={subtitle} />
            </p>
          </div>
          {(headerControls || credit) && (
            <div className="flex flex-col items-start gap-0.5 sm:items-end">
              {headerControls}
              {credit && (
                <p className="text-[10.5px] text-ink-muted/80" data-testid="chart-credit">
                  {credit}
                </p>
              )}
            </div>
          )}
        </header>
        <div className="border-t border-line">
          {/* HighlightStatus renders nothing without a highlight; :empty drops this padding with it. */}
          <div className="px-3 pt-2 empty:hidden sm:px-4">{status}</div>
          {!hasData ? (
            <p role="status" className="p-5 text-ink-muted" data-testid="chart-empty">
              {emptyText}
            </p>
          ) : asTable && table ? (
            <div className="p-2 sm:p-3">{table}</div>
          ) : (
            <div className="px-2 pt-1 pb-2 sm:px-3 sm:pb-3" data-testid="chart-figure">
              {figure}
            </div>
          )}
        </div>
      </div>

      {notCharted.length > 0 && (
        <p className="text-xs text-ink-muted" data-testid="not-charted">
          Not charted ({notCharted.length}): {notCharted.map((n) => `game ${n.gameId} (${n.reason})`).join(", ")}.
        </p>
      )}
      {unavailable.length > 0 && (
        <details data-card="" className="rounded-xl border border-line bg-surface-card px-3 py-2 text-xs text-ink-muted shadow-2xs" data-testid="unavailable-teams">
          <summary className="cursor-pointer font-semibold text-ink">Not plotted ({unavailable.length} teams)</summary>
          <p className="mt-1.5 leading-relaxed">
            {unavailable.join(", ")}. These teams have no eligible FBS games or no valid observations for this chart yet.
          </p>
        </details>
      )}
      <div className="text-[11px] leading-relaxed text-ink-faint" data-testid="chart-footnote">
        {footnoteLines(footnote).map((line) => <p key={line}>{line}</p>)}
      </div>
    </section>
  );
}
