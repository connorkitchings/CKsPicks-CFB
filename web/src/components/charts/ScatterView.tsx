"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import Link from "next/link";
import { teamHref } from "@/lib/team-routes";
import { ChartTable, type TableColumn } from "./ChartTable";
import { CHART_REGISTRY, chartSubtitle, exportFilename, groupLabel, type ScatterConfig } from "@/lib/chart-config";
import { domainFor, matchesConference, scatterRanks, type ChartKind, type ScatterData, type ScatterPoint, type Side } from "@/lib/charts";
import { chartSummary } from "@/components/ui/SummaryLine";
import { ChartFrame, EXPORT_CHART_HEIGHT, EXPORT_SIZE, ExportCard, HighlightStatus, type SharedChartProps } from "./ChartFrame";
import { ScatterChart } from "./ScatterChart";
import { useIsPhone } from "@/lib/use-is-phone";

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

/** Phone-fit or desktop-scroll sizing shared by team scatters: `fitRef` goes on the phone wrapper, `view` is the viewBox size. */
export function useScatterViewport() {
  const mobile = useIsPhone();
  const [fitNode, setFitNode] = useState<HTMLDivElement | null>(null);
  const [fitWidth, setFitWidth] = useState(MOBILE_FALLBACK_WIDTH);
  useEffect(() => {
    if (!mobile || !fitNode) return;
    const observer = new ResizeObserver(([entry]) => setFitWidth(Math.round(entry.contentRect.width) || MOBILE_FALLBACK_WIDTH));
    observer.observe(fitNode);
    return () => observer.disconnect();
  }, [mobile, fitNode]);
  return { mobile, fitRef: setFitNode, view: mobile ? mobileView(fitWidth) : SCATTER_VIEW };
}

/** A team scatter in the shared frame: national geometry, conference filter, highlight and export. */
export function ScatterView({ shared, kind, side, data, config, describe, controls, exportMetric, description }: ScatterViewProps) {
  const { mobile, fitRef, view } = useScatterViewport();
  const [detailsContainer, setDetailsContainer] = useState<HTMLDivElement | null>(null);
  const { season, week, roster, filter, highlight, onHighlight, compare, onCompare } = shared;
  const ranks = useMemo(() => scatterRanks(data), [data]);
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
      shortXLabel={config.shortXLabel}
      shortYLabel={config.shortYLabel}
      width={view.width}
      height={view.height}
      cornerCaptions={config.captions}
      averageNames={config.averageNames}
      stateOf={(p) => (p.team === highlight || p.team === compare ? "searched" : "active")}
      describe={describe}
      formatX={config.tickX}
      formatY={config.tickY}
      interactive={interactive}
      detailsContainer={interactive ? detailsContainer : undefined}
      showDetails={false}
      label={`${title}. ${subtitle}`}
    />
  );

  const viewSubtitle = [
    subtitle,
    groupLabel(filter),
    ...(config.metricLabel ? [config.metricLabel] : []),
    `Highlight: ${highlight ?? "None"}${highlight && !highlightAvailable ? " (outside filter or unavailable)" : ""}`,
    ...(compare ? [`Compare: ${compare}`] : []),
  ].join(" | ");

  const comparisonHref = (team: string) => {
    const primary = highlight ?? team;
    const q = new URLSearchParams({ view: "compare", season: String(season), team: primary });
    if (compare && compare !== primary) q.set("compare", compare);
    return `/teams?${q}`;
  };
  const columns: TableColumn<ScatterPoint>[] = [
    { key: "team", label: "Team", value: (p) => p.team, format: (p) => <Link className="text-accent-ink underline underline-offset-4" href={`${teamHref(p.team)}?season=${season}`}>{p.team}</Link> },
    { key: "x", label: config.xLabel, value: (p) => p.x, format: (p) => config.tickX(p.x), numeric: true },
    { key: "xRank", label: `${config.xLabel} rank`, value: (p) => ranks.get(p.team)?.x ?? null, numeric: true },
    { key: "y", label: config.yLabel, value: (p) => p.y, format: (p) => config.tickY(p.y), numeric: true },
    { key: "yRank", label: `${config.yLabel} rank`, value: (p) => ranks.get(p.team)?.y ?? null, numeric: true },
    { key: "xN", label: config.xSample ?? "X exposure", value: (p) => p.xN ?? null, numeric: true },
    { key: "yN", label: config.ySample ?? "Y exposure", value: (p) => p.yN ?? null, numeric: true },
    { key: "select", label: "Explore", value: (p) => p.team, format: (p) => <button className="min-h-11 font-medium text-accent-ink" onClick={() => onHighlight(p.team)}>Select {p.team}</button> },
  ];
  const selectedPoints = [highlight, compare].filter((team): team is string => Boolean(team)).map((team) => data.points.find((p) => p.team === team));
  const details = <div className="space-y-4 p-3 sm:p-4" data-testid="scatter-selection-panel">
    <p className="text-sm text-ink-muted">Coverage: {points.length} of {eligibleRoster.length} teams. Axis ranks use all {data.points.length} eligible FBS teams, regardless of the filter.</p>
    {highlight && !points.some((p) => p.team === highlight) && <p role="status" className="text-sm text-ink-muted">{highlight}: {data.points.some((p) => p.team === highlight) ? "outside the current filter; selection retained." : "no eligible observation in this window."}</p>}
    {compare && !points.some((p) => p.team === compare) && <p className="text-sm text-ink-muted">{compare}: outside the filter or unavailable in this window.</p>}
    {selectedPoints.some(Boolean) ? <div className="grid gap-4 md:grid-cols-2">{selectedPoints.map((point) => point && <article key={point.team} className="rounded-lg border border-line p-4" aria-label={`${point.team} chart details`}>
      <h3 className="font-semibold text-ink">{point.team}</h3>
      <dl className="mt-3 space-y-3 text-sm">
        <div><dt className="text-ink-muted">{config.xLabel}</dt><dd className="font-semibold tabular-nums">{config.tickX(point.x)} · #{ranks.get(point.team)?.x} nationally</dd><dd className="text-xs text-ink-muted">{point.xN === undefined ? "Exposure unavailable" : `${point.xN.toLocaleString("en-US")} ${config.xSample ?? "observations"}`}</dd></div>
        <div><dt className="text-ink-muted">{config.yLabel}</dt><dd className="font-semibold tabular-nums">{config.tickY(point.y)} · #{ranks.get(point.team)?.y} nationally</dd><dd className="text-xs text-ink-muted">{point.yN === undefined ? "Exposure unavailable" : `${point.yN.toLocaleString("en-US")} ${config.ySample ?? "observations"}`}</dd></div>
      </dl>
      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-sm font-medium text-accent-ink">
        <Link className="inline-flex min-h-11 items-center underline underline-offset-4" href={`${teamHref(point.team)}?season=${season}`}>Team profile</Link>
        <Link className="inline-flex min-h-11 items-center underline underline-offset-4" href={comparisonHref(point.team)}>Compare ratings</Link>
        {shared.nextMatchups?.[point.team] && <Link className="inline-flex min-h-11 items-center underline underline-offset-4" href={`/matchup/${shared.nextMatchups[point.team]}`}>Next matchup</Link>}
      </div>
    </article>)}</div> : <p className="text-sm text-ink-muted">Select a team in the chart or table to inspect its values and compare it.</p>}
    {highlight && onCompare && <div className="flex flex-wrap items-center gap-3"><label htmlFor={`compare-${kind}`} className="text-sm font-medium">Compare with</label><select id={`compare-${kind}`} aria-label="Compare with a second team" value={compare ?? ""} onChange={(event) => onCompare(event.target.value || null)} className="min-h-11 max-w-full rounded-lg border border-line bg-surface-card px-3 text-sm"><option value="">Choose a second team</option>{roster.filter((r) => r.team !== highlight).map((r) => <option key={r.team} value={r.team}>{r.team}</option>)}</select>{compare && <button className="min-h-11 text-sm text-accent-ink" onClick={() => onCompare(null)}>Clear comparison</button>}</div>}
  </div>;

  return (
    <ChartFrame
      shared={shared}
      title={title}
      subtitle={subtitle}
      description={description ?? CHART_REGISTRY[kind].description}
      controls={controls}
      summary={chartSummary({ side: CHART_REGISTRY[kind].controls.side ? side : null, week: { n: week, through: CHART_REGISTRY[kind].controls.week === "through-week" }, filter, metric: config.metricLabel })}
      highlightTeams={roster}
      exportSpec={{
        contentKey: JSON.stringify([kind, side, exportMetric, viewSubtitle, data]),
        filename: exportFilename(kind, season, week, side, exportMetric),
        width: EXPORT_SIZE.width,
        height: EXPORT_SIZE.height,
        card: (
          <ExportCard title={title} subtitle={viewSubtitle} footnote={config.footnote}>
            {chart({ width: EXPORT_SIZE.width - 24, height: EXPORT_CHART_HEIGHT }, false)}
          </ExportCard>
        ),
      }}
      status={<HighlightStatus team={highlight} available={data.points.some((p) => p.team === highlight)} week={week} />}
      details={details}
      table={<ChartTable rows={points} columns={columns} rowKey={(point) => point.team} caption={`${title}. ${viewSubtitle}.`} initialSort={{ key: "team" }} />}
      hasData={points.length > 0}
      figure={
        <>
          {mobile ? (
            <div ref={fitRef} data-testid="scatter-fit">{chart(view, true)}</div>
          ) : (
            <>
              <p className="mb-2 text-xs text-ink-muted lg:hidden">Scroll chart horizontally to see every team.</p>
              <div className="overflow-x-auto focus-visible:outline-2 focus-visible:outline-accent" role="region" aria-label="Team scatter chart, horizontally scrollable" tabIndex={0} data-testid="scatter-scroll">
                <div className="min-w-[760px] lg:min-w-0">{chart(view, true)}</div>
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
