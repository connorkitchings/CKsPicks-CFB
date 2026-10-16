"use client";

import { useState, useSyncExternalStore } from "react";
import clsx from "clsx";
import {
  CHART_FOOTNOTES,
  CHART_TITLES,
  chartSubtitle,
  conferenceOptions,
  formatEpa,
  domainFor,
  filterNetSuccessBars,
  scatterRanks,
  formatPercent,
  matchesConference,
  matchesSearch,
  type ChartKind,
  type ConferenceFilter,
  type NetSuccessBar,
  type NotCharted,
  type RosterRow,
  type ScatterData,
  type ScatterPoint,
  type Side,
} from "@/lib/charts";
import { ChartExportButton } from "./ChartExportButton";
import { ChartTable, type TableColumn } from "./ChartTable";
import { NetSuccessChart } from "./NetSuccessChart";
import { ScatterChart, type MarkerState } from "./ScatterChart";

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

export function ChartsView({ kind, side, season, week, roster, scatter, bars, notCharted = [] }: ChartsViewProps) {
  const [filter, setFilter] = useState<ConferenceFilter>("all");
  const [query, setQuery] = useState("");
  const [highlight, setHighlight] = useState<string | null>(null);
  const [asTable, setAsTable] = useState(false);
  const narrow = useSyncExternalStore(subscribeNarrow, isNarrow, serverWide);

  const eligibleRoster = roster.filter((r) => matchesConference(filter, r.team, r.conference));
  const filteredPoints = (scatter?.points ?? []).filter((p) => matchesConference(filter, p.team, p.conference));
  const filteredBars = filterNetSuccessBars(bars ?? [], roster, filter);
  const ranks = scatter ? scatterRanks(scatter) : new Map<string, { x: number; y: number }>();
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
  const yLabel = adjusted ? "Adjusted defense PPA/play allowed" : "PPA/play";
  const formatX = adjusted ? formatEpa : (v: number) => formatPercent(v);
  const formatY = formatEpa;

  function describePoint(p: ScatterPoint): string {
    const where = conferenceLabel(p.conference);
    return adjusted
      ? `${p.team} (${where}): adjusted offense ${formatEpa(p.x)}, adjusted defense allowed ${formatEpa(p.y)} PPA/play`
      : `${p.team} (${where}): success rate ${formatPercent(p.x)}, PPA/play ${formatEpa(p.y)}, ${p.n} plays`;
  }
  function describeBar(b: NetSuccessBar): string {
    return `${b.winner} beat ${b.loser} ${b.winnerPoints}-${b.loserPoints}: offensive success rate ${formatPercent(b.winnerSuccessRate)} to ${formatPercent(b.loserSuccessRate)}, winner's success-rate ${b.value >= 0 ? "advantage" : "disadvantage"} ${Math.abs(b.value * 100).toFixed(1)} percentage points`;
  }

  const hasData = kind === "net-success" ? Boolean(filteredBars.length) : Boolean(filteredPoints.length);
  const unavailable = kind === "net-success" ? [] : (scatter?.unavailable ?? []).filter((team) => eligibleRoster.some((r) => r.team === team));

  const scatterChart = (view: { width: number; height: number }, interactive: boolean) =>
    scatter ? (
      <ScatterChart
        points={filteredPoints}
        xDomain={domainFor([...scatter.points.map((p) => p.x), ...(scatter.average ? [scatter.average.x] : [])], 0.08)}
        yDomain={domainFor([...scatter.points.map((p) => p.y), ...(scatter.average ? [scatter.average.y] : [])], 0.08)}
        onToggleHighlight={toggleHighlight}
        average={scatter.average}
        invertX={scatter.invertX}
        invertY={scatter.invertY}
        xLabel={xLabel}
        yLabel={yLabel}
        width={view.width}
        height={view.height}
        netLevels={adjusted ? scatter.netLevels : undefined}
        cornerLabels={adjusted}
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
  const viewSubtitle = `${subtitle} | ${groupLabel}${kind === "net-success" ? "" : ` | Highlight: ${highlight ?? "None"}${highlight && !highlightAvailable ? " (unavailable in this window)" : ""}`}`;
  const exportWidth = kind === "net-success" ? netSuccessWidth(barCount) : EXPORT_SCATTER.width;
  const exportHeight = EXPORT_SCATTER.height;
  const exportChartHeight = exportHeight - EXPORT_HEADER - EXPORT_FOOTER;

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
        {CHART_FOOTNOTES[kind]} ckspicks-cfb.vercel.app
      </div>
    </div>
  );

  const pointColumns: TableColumn<ScatterPoint>[] = [
    { key: "team", label: "Team", value: (r) => r.team },
    { key: "conference", label: "Conference", value: (r) => r.conference, format: (r) => conferenceLabel(r.conference) },
    { key: "x", label: xLabel, value: (r) => r.x, format: (r) => formatX(r.x), numeric: true },
    { key: "xRank", label: `${xLabel} national rank`, value: (r) => ranks.get(r.team)?.x ?? null, numeric: true },
    { key: "y", label: yLabel, value: (r) => r.y, format: (r) => formatY(r.y), numeric: true },
    { key: "yRank", label: `${yLabel} national rank`, value: (r) => ranks.get(r.team)?.y ?? null, numeric: true },
    { key: "n", label: "Plays", value: (r) => r.n, numeric: true },
  ];
  const barColumns: TableColumn<NetSuccessBar>[] = [
    { key: "winner", label: "Winner", value: (r) => r.winner },
    { key: "loser", label: "Loser", value: (r) => r.loser },
    { key: "score", label: "Score", value: (r) => r.winnerPoints - r.loserPoints, format: (r) => `${r.winnerPoints}-${r.loserPoints}`, numeric: true },
    { key: "winnerRate", label: "Winner success", value: (r) => r.winnerSuccessRate, format: (r) => formatPercent(r.winnerSuccessRate), numeric: true },
    { key: "loserRate", label: "Loser success", value: (r) => r.loserSuccessRate, format: (r) => formatPercent(r.loserSuccessRate), numeric: true },
    { key: "value", label: "Difference (percentage points)", value: (r) => r.value, format: (r) => (r.value * 100).toFixed(1), numeric: true },
  ];

  const field =
    "min-h-10 w-full rounded-lg border border-line bg-surface-card px-3 py-2 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-accent";

  return (
    <section className="space-y-3" aria-label={title}>
      <header>
        <h2 className="text-lg font-bold tracking-tight text-ink sm:text-xl">{title}</h2>
        <p className="text-xs text-ink-muted sm:text-sm" data-testid="chart-subtitle">
          {subtitle}
        </p>
      </header>
      <div className="flex flex-col gap-3 rounded-xl border border-line bg-surface-inset p-3 lg:flex-row lg:items-end lg:justify-between" data-testid="chart-controls">
        <div className="grid min-w-0 gap-3 sm:grid-cols-2 lg:flex" role="group" aria-label="Find teams">
          <label className="flex min-w-0 flex-col gap-1 text-xs font-semibold text-ink-muted">
            Conference
            <select
              className={field}
              value={filter}
              onChange={(event) => {
                const next = event.target.value;
                setFilter(next);
                const selected = roster.find((r) => r.team === highlight);
                if (selected && !matchesConference(next, selected.team, selected.conference)) setHighlight(null);
              }}
              data-testid="conference-filter"
            >
              <option value="all">All FBS</option>
              <option value="p4">Power Four + Notre Dame</option>
              {conferenceOptions(roster).map((conference) => (
                <option key={conference} value={conference}>
                  {conference}
                </option>
              ))}
            </select>
          </label>
          {kind !== "net-success" && (
            <div className="flex min-w-0 flex-col gap-1 text-xs font-semibold text-ink-muted">
              <label htmlFor="team-search">Find a team</label>
              <input id="team-search" type="search" className={clsx(field, "lg:w-48")} value={query} maxLength={40} placeholder="Team or abbreviation" onChange={(event) => setQuery(event.target.value)} data-testid="team-search" />
              <label htmlFor="team-highlight">Highlight one team</label>
              <select id="team-highlight" className={field} value="choose" onChange={(event) => event.target.value ? toggleHighlight(event.target.value) : setHighlight(null)} data-testid="team-highlight">
                <option value="choose" disabled>Choose a team to toggle</option>
                <option value="">None</option>
                {eligibleRoster.filter((r) => !query.trim() || matchesSearch(query, r.team) || r.team === highlight).map((r) => <option key={r.team} value={r.team}>{r.team}</option>)}
              </select>
            </div>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Chart display and export">
          <button
            type="button"
            aria-pressed={asTable}
            onClick={() => setAsTable((current) => !current)}
            className="min-h-10 rounded-lg border border-line bg-surface-card px-3 py-2 text-xs font-medium text-ink hover:border-accent hover:text-accent-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent aria-pressed:border-accent aria-pressed:text-accent-ink"
            data-testid="table-toggle"
          >
            {asTable ? "Show chart" : "Show as table"}
          </button>
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
          Highlight: {highlight}{highlightAvailable ? ". Select again or choose None to clear." : ` — no available observation Through Week ${week}.`}
        </p>
      )}
      {!hasData ? (
        <p role="status" className="rounded-xl border border-line bg-surface-card p-5 text-ink-muted" data-testid="chart-empty">
          No teams can be charted for this week yet.
        </p>
      ) : asTable ? (
        kind === "net-success" ? (
          <ChartTable rows={filteredBars} columns={barColumns} rowKey={(r) => String(r.gameId)} caption={`${title}, ${viewSubtitle}`} initialSort={{ key: "value" }} />
        ) : (
          <ChartTable rows={filteredPoints} columns={pointColumns} rowKey={(r) => r.team} caption={`${title}, ${viewSubtitle}`} initialSort={{ key: "team" }} />
        )
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
              <p className="mb-2 text-xs text-ink-muted lg:hidden">Scroll chart horizontally to see every team, or use the table.</p>
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
      <p className="text-[11px] leading-relaxed text-ink-faint">{CHART_FOOTNOTES[kind]}</p>
    </section>
  );
}
