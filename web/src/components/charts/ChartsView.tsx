"use client";

import { useState, useMemo, useSyncExternalStore } from "react";
import clsx from "clsx";
import {
  CHART_FOOTNOTES,
  CHART_TITLES,
  chartSubtitle,
  conferenceOptions,
  efficiencyPoints,
  formatEpa,
  domainFor,
  filterNetSuccessBars,
  scatterRanks,
  formatPercent,
  matchesConference,
  matchesSearch,
  type ChartKind,
  type ConferenceFilter,
  type EfficiencyMetric,
  type NetSuccessBar,
  type NotCharted,
  type RosterRow,
  type ScatterData,
  type ScatterPoint,
  type Side,
  type TeamGameRow,
} from "@/lib/charts";
import { ChartExportButton } from "./ChartExportButton";
import { NetSuccessChart } from "./NetSuccessChart";
import { ScatterChart, type CornerCaptions, type MarkerState } from "./ScatterChart";
import { TeamHighlightCombobox } from "./TeamHighlightCombobox";

export type ChartsViewProps = {
  kind: ChartKind;
  side: Side;
  season: number;
  /** Week of the net-success chart, or the "Through Week N" of a scatter. */
  week: number;
  roster: RosterRow[];
  /** Efficiency / adjusted scatter. */
  scatter?: (ScatterData & { netLevels?: number[] }) | null;
  /** Net-success bars. */
  bars?: NetSuccessBar[] | null;
  notCharted?: NotCharted[];
  rows?: TeamGameRow[];
  initialMetric?: EfficiencyMetric;
};

const SCATTER_VIEW = { width: 1000, height: 640 };
// Exports are captured at 2x: 1000 x 562.5 CSS px is a 2000 x 1125 px PNG, and the
// net-success width max(1000, 70 + 15 n) is the contract's max(2000, 140 + 30 n) px.
const EXPORT_SCATTER = { width: 1000, height: 562.5 };
const netSuccessWidth = (games: number) => Math.max(1000, 70 + 15 * games);
const EXPORT_HEADER = 70;
const EXPORT_FOOTER = 50;

const subscribeNarrow = (callback: () => void) => {
  const query = window.matchMedia("(max-width: 639px)");
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
};
const isNarrow = () => window.matchMedia("(max-width: 639px)").matches;
const serverWide = () => false;

function conferenceLabel(conference: string | null): string {
  return conference ?? "Independent";
}

export function ChartsView({ kind, side, season, week, roster, scatter, bars, notCharted = [], rows, initialMetric }: ChartsViewProps) {
  const [filter, setFilter] = useState<ConferenceFilter>("all");
  const [highlight, setHighlight] = useState<string | null>(null);
  const [efficiencyMetric, setEfficiencyMetric] = useState<EfficiencyMetric>(initialMetric ?? "explosive_rate");
  const narrow = useSyncExternalStore(subscribeNarrow, isNarrow, serverWide);

  const activeScatter: (ScatterData & { netLevels?: number[] }) | null | undefined = useMemo(() => {
    if (kind !== "efficiency") return scatter;
    if (efficiencyMetric === "ppa" && scatter) return scatter;
    return efficiencyPoints(roster, rows ?? [], week, side, efficiencyMetric);
  }, [kind, efficiencyMetric, scatter, roster, rows, week, side]);

  const eligibleRoster = roster.filter((r) => matchesConference(filter, r.team, r.conference));
  const filteredPoints = (activeScatter?.points ?? []).filter((p) => matchesConference(filter, p.team, p.conference));
  const filteredBars = filterNetSuccessBars(bars ?? [], roster, filter);
  const ranks = activeScatter ? scatterRanks(activeScatter) : new Map<string, { x: number; y: number }>();
  const highlightAvailable = filteredPoints.some((p) => p.team === highlight);
  function pointState(p: ScatterPoint): MarkerState {
    return p.team === highlight ? "searched" : "active";
  }
  const barState = (): MarkerState => "active";
  const toggleHighlight = (team: string) => setHighlight((current) => current === team ? null : team);

  const title = CHART_TITLES[kind];
  const subtitle = chartSubtitle(kind, season, week, side);
  const adjusted = kind === "adjusted";
  const xLabel = adjusted ? "Adjusted offense PPA/play" : "Success Rate";
  const yLabel = adjusted
    ? "Adjusted defense PPA/play allowed"
    : efficiencyMetric === "explosive_rate"
    ? (side === "defense" ? "20+ Yard Play Rate Allowed" : "20+ Yard Play Rate")
    : efficiencyMetric === "yards_per_success"
    ? (side === "defense" ? "Yards / Success Allowed" : "Yards / Successful Play")
    : "PPA/play";
  const formatX = adjusted
    ? formatEpa
    : kind === "efficiency"
    ? (v: number) => `${Math.round(v * 100)}%`
    : (v: number) => formatPercent(v);
  const formatY = adjusted
    ? formatEpa
    : efficiencyMetric === "explosive_rate"
    ? (v: number) => `${Math.round(v * 100)}%`
    : efficiencyMetric === "yards_per_success"
    ? (v: number) => `${Math.round(v)} yds`
    : formatEpa;

  function describePoint(p: ScatterPoint): string {
    const where = conferenceLabel(p.conference);
    if (adjusted) {
      return `${p.team} (${where}): adjusted offense ${formatEpa(p.x)}, adjusted defense allowed ${formatEpa(p.y)} PPA/play`;
    }
    if (efficiencyMetric === "explosive_rate") {
      return `${p.team} (${where}): success rate ${formatPercent(p.x)}, 20+ yard rate ${formatPercent(p.y)}, ${p.n} plays`;
    }
    if (efficiencyMetric === "yards_per_success") {
      return `${p.team} (${where}): success rate ${formatPercent(p.x)}, yards/success ${p.y.toFixed(2)} yds, ${p.n} plays`;
    }
    return `${p.team} (${where}): success rate ${formatPercent(p.x)}, PPA/play ${formatEpa(p.y)}, ${p.n} plays`;
  }
  function describeBar(b: NetSuccessBar): string {
    return `${b.winner} beat ${b.loser} ${b.winnerPoints}-${b.loserPoints}: offensive success rate ${formatPercent(b.winnerSuccessRate)} to ${formatPercent(b.loserSuccessRate)}, winner's success-rate ${b.value >= 0 ? "advantage" : "disadvantage"} ${Math.abs(b.value * 100).toFixed(1)} percentage points`;
  }

  const hasData = kind === "net-success" ? Boolean(filteredBars.length) : Boolean(filteredPoints.length);
  const unavailable = kind === "net-success" ? [] : (activeScatter?.unavailable ?? []).filter((team) => eligibleRoster.some((r) => r.team === team));

  const cornerCaptions: CornerCaptions = useMemo(() => {
    if (adjusted) {
      return {
        topLeft: "Lower offense / Better defense",
        topRight: "Better offense / Better defense",
        bottomLeft: "Lower offense / Higher defense allowed",
        bottomRight: "Better offense / Higher defense allowed",
        note: "Relative to play-weighted FBS averages; diagonals: equal net PPA (offense − defense allowed)",
      };
    }
    const isDefense = side === "defense";
    if (efficiencyMetric === "explosive_rate") {
      if (isDefense) {
        return {
          topLeft: "Higher allowed success / Lower allowed 20+ rate",
          topRight: "Lower allowed success / Lower allowed 20+ rate",
          bottomLeft: "Higher allowed success / Higher allowed 20+ rate",
          bottomRight: "Lower allowed success / Higher allowed 20+ rate",
          note: "Relative to play-weighted FBS averages",
        };
      }
      return {
        topLeft: "Lower success / Higher 20+ rate",
        topRight: "Higher success / Higher 20+ rate",
        bottomLeft: "Lower success / Lower 20+ rate",
        bottomRight: "Higher success / Lower 20+ rate",
        note: "Relative to play-weighted FBS averages",
      };
    }
    if (efficiencyMetric === "yards_per_success") {
      if (isDefense) {
        return {
          topLeft: "Higher allowed success / Lower allowed yards/success",
          topRight: "Lower allowed success / Lower allowed yards/success",
          bottomLeft: "Higher allowed success / Higher allowed yards/success",
          bottomRight: "Lower allowed success / Higher allowed yards/success",
          note: "Relative to play-weighted FBS averages",
        };
      }
      return {
        topLeft: "Lower success / Higher yards/success",
        topRight: "Higher success / Higher yards/success",
        bottomLeft: "Lower success / Lower yards/success",
        bottomRight: "Higher success / Lower yards/success",
        note: "Relative to play-weighted FBS averages",
      };
    }
    if (isDefense) {
      return {
        topLeft: "Higher allowed success / Lower allowed PPA",
        topRight: "Lower allowed success / Lower allowed PPA",
        bottomLeft: "Higher allowed success / Higher allowed PPA",
        bottomRight: "Lower allowed success / Higher allowed PPA",
        note: "Relative to play-weighted FBS averages",
      };
    }
    return {
      topLeft: "Lower success / Higher PPA",
      topRight: "Higher success / Higher PPA",
      bottomLeft: "Lower success / Lower PPA",
      bottomRight: "Higher success / Lower PPA",
      note: "Relative to play-weighted FBS averages",
    };
  }, [adjusted, side, efficiencyMetric]);

  const scatterChart = (view: { width: number; height: number }, interactive: boolean) =>
    activeScatter ? (
      <ScatterChart
        points={filteredPoints}
        xDomain={domainFor([...activeScatter.points.map((p) => p.x), ...(activeScatter.average ? [activeScatter.average.x] : [])], 0.08)}
        yDomain={domainFor([...activeScatter.points.map((p) => p.y), ...(activeScatter.average ? [activeScatter.average.y] : [])], 0.08)}
        onToggleHighlight={toggleHighlight}
        average={activeScatter.average}
        invertX={activeScatter.invertX}
        invertY={activeScatter.invertY}
        xLabel={xLabel}
        yLabel={yLabel}
        width={view.width}
        height={view.height}
        netLevels={adjusted ? activeScatter.netLevels : undefined}
        cornerLabels={adjusted}
        cornerCaptions={cornerCaptions}
        stateOf={pointState}
        describe={describePoint}
        formatX={formatX}
        formatY={formatY}
        interactive={interactive}
        label={`${title}. ${subtitle}`}
      />
    ) : null;

  const barCount = filteredBars.length;
  const groupLabel = filter === "all" ? "All FBS" : filter === "p4" ? "Power Four + Notre Dame" : filter;
  const metricLabel = efficiencyMetric === "explosive_rate" ? "20+ Yard Rate" : efficiencyMetric === "yards_per_success" ? "Yards / Success" : "PPA/play";
  const viewSubtitle = `${subtitle} | ${groupLabel}${kind === "efficiency" ? ` | ${metricLabel}` : ""}${kind === "net-success" ? "" : ` | Highlight: ${highlight ?? "None"}${highlight && !highlightAvailable ? " (unavailable in this window)" : ""}`}`;
  const exportWidth = kind === "net-success" ? netSuccessWidth(barCount) : EXPORT_SCATTER.width;
  const exportHeight = EXPORT_SCATTER.height;
  const exportChartHeight = exportHeight - EXPORT_HEADER - EXPORT_FOOTER;

  const footnote =
    kind === "efficiency"
      ? efficiencyMetric === "explosive_rate"
        ? "Cumulative success rate and 20+ yard play rate on eligible plays (regulation only; garbage time and special teams excluded), FBS vs FBS games. Dashed lines are FBS averages. On defense, axes are inverted so up and right is better. Research comparison dataset."
        : efficiencyMetric === "yards_per_success"
        ? "Cumulative success rate and yards per successful play on eligible plays (regulation only; garbage time and special teams excluded), FBS vs FBS games. Dashed lines are FBS averages. On defense, axes are inverted so up and right is better. Research comparison dataset."
        : CHART_FOOTNOTES[kind]
      : CHART_FOOTNOTES[kind];

  const exportCard = (
    <div className="flex h-full flex-col" data-testid="export-card">
      <div className="px-5 pt-3" style={{ height: EXPORT_HEADER }}>
        <div className="text-2xl font-bold tracking-tight text-ink">{title}</div>
        <div className="text-sm text-ink-muted">{viewSubtitle}</div>
      </div>
      <div className="min-h-0 flex-1 px-3">
        {kind === "net-success" ? (
          <NetSuccessChart
            bars={filteredBars}
            stateOf={barState}
            describe={describeBar}
            width={exportWidth - 24}
            height={exportChartHeight}
            interactive={false}
            label={`${title}. ${subtitle}`}
          />
        ) : (
          scatterChart({ width: EXPORT_SCATTER.width - 24, height: exportChartHeight }, false)
        )}
      </div>
      <div className="px-5 text-[11px] leading-snug text-ink-muted" style={{ height: EXPORT_FOOTER }}>
        {footnote} ckspicks-cfb.vercel.app
      </div>
    </div>
  );

  return (
    <section className="space-y-3" aria-label={title}>
      <header className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-bold tracking-tight text-ink sm:text-xl">{title}</h2>
          <p className="text-xs text-ink-muted sm:text-sm" data-testid="chart-subtitle">
            {subtitle}
          </p>
        </div>
        {kind === "efficiency" && (
          <div className="inline-flex gap-1 rounded-lg border border-line bg-surface-card p-1 shadow-2xs" data-testid="efficiency-metric-switcher">
            <button
              type="button"
              onClick={() => setEfficiencyMetric("explosive_rate")}
              aria-pressed={efficiencyMetric === "explosive_rate"}
              className={clsx(
                "inline-flex min-h-8 items-center rounded-md px-3 py-1 text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                efficiencyMetric === "explosive_rate" ? "bg-ink text-surface-card shadow-2xs" : "text-ink-muted hover:text-ink hover:bg-surface-inset",
              )}
              data-testid="metric-toggle-explosive-rate"
            >
              20+ Yard Rate
            </button>
            <button
              type="button"
              onClick={() => setEfficiencyMetric("yards_per_success")}
              aria-pressed={efficiencyMetric === "yards_per_success"}
              className={clsx(
                "inline-flex min-h-8 items-center rounded-md px-3 py-1 text-xs font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent",
                efficiencyMetric === "yards_per_success" ? "bg-ink text-surface-card shadow-2xs" : "text-ink-muted hover:text-ink hover:bg-surface-inset",
              )}
              data-testid="metric-toggle-yards-per-success"
            >
              Yards / Success
            </button>
          </div>
        )}
      </header>

      <div className="flex flex-col gap-3 rounded-xl border border-line bg-surface-inset p-2.5 sm:p-3 sm:flex-row sm:items-center sm:justify-between" data-testid="chart-controls">
        <div className="flex flex-wrap items-center gap-2.5" role="group" aria-label="Chart controls">
          <select
            className="min-h-9 rounded-lg border border-line bg-surface-card px-3 py-1.5 text-xs font-medium text-ink focus:outline-none focus:ring-2 focus:ring-accent"
            value={filter}
            onChange={(event) => {
              const next = event.target.value;
              setFilter(next);
              const selected = roster.find((r) => r.team === highlight);
              if (selected && !matchesConference(next, selected.team, selected.conference)) setHighlight(null);
            }}
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
          {kind !== "net-success" && (
            <TeamHighlightCombobox
              teams={eligibleRoster}
              highlight={highlight}
              onSelect={setHighlight}
            />
          )}
        </div>
        <div className="flex items-center gap-2" role="group" aria-label="Chart export">
          {hasData && (
            <ChartExportButton
              filename={`ckspicks-${kind}${kind === "efficiency" ? `-${side}` : ""}-${season}-${kind === "net-success" ? "week" : "through-week"}-${week}.png`}
              width={exportWidth}
              height={exportHeight}
            >
              {exportCard}
            </ChartExportButton>
          )}
        </div>
      </div>

      {kind !== "net-success" && highlight && (
        <p role="status" className="text-xs text-ink-muted" data-testid="highlight-status">
          Highlight: {highlight}{highlightAvailable ? ". Click again or clear to unhighlight." : ` — no available observation Through Week ${week}.`}
        </p>
      )}
      {!hasData ? (
        <p role="status" className="rounded-xl border border-line bg-surface-card p-5 text-ink-muted" data-testid="chart-empty">
          No teams can be charted for this week yet.
        </p>
      ) : (
        <div className="rounded-xl border border-line bg-surface-card p-2 sm:p-3" data-testid="chart-figure">
          {kind === "net-success" ? (
            <NetSuccessChart
              bars={filteredBars}
              stateOf={barState}
              describe={describeBar}
              orientation={narrow ? "horizontal" : "vertical"}
              width={narrow ? 420 : netSuccessWidth(barCount)}
              height={narrow ? 56 + 36 * barCount : 640}
              label={`${title}. ${subtitle}`}
            />
          ) : (
            <>
              <p className="mb-2 text-xs text-ink-muted lg:hidden">Scroll chart horizontally to see every team.</p>
              <div className="overflow-x-auto focus-visible:outline-2 focus-visible:outline-accent" role="region" aria-label="Team scatter chart, horizontally scrollable" tabIndex={0} data-testid="scatter-scroll">
                <div className="min-w-[760px] lg:min-w-0">{scatterChart(SCATTER_VIEW, true)}</div>
              </div>
            </>
          )}
          {kind === "efficiency" && side === "defense" && (
            <p className="mt-1 text-center text-[11px] text-ink-faint">Axes are inverted: up and right is better defense.</p>
          )}
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
