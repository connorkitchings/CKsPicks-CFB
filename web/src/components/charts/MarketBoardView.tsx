"use client";

import { useMemo, useState } from "react";
import { CHART_REGISTRY, chartSubtitle, exportFilename } from "@/lib/chart-config";
import {
  domainFor,
  marketBoardPoints,
  type MarketBoardMetric,
  type SlateMarketGameRow,
} from "@/lib/charts";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { chartSummary } from "@/components/ui/SummaryLine";
import { useIsPhone } from "@/lib/use-is-phone";
import { ChartFrame, EXPORT_CHART_HEIGHT, EXPORT_SIZE, ExportCard, type SharedChartProps } from "./ChartFrame";
import { MarketBoardChart } from "./MarketBoardChart";

export type MarketBoardViewProps = {
  shared: SharedChartProps;
  games: SlateMarketGameRow[];
  initialMetric: MarketBoardMetric;
};

const METRIC_OPTIONS: { value: MarketBoardMetric; label: string }[] = [
  { value: "spread", label: "Spread" },
  { value: "total", label: "Total" },
];

export function MarketBoardView({ shared, games, initialMetric }: MarketBoardViewProps) {
  const [metric, setMetric] = useState<MarketBoardMetric>(initialMetric);
  const [selectedGameId, setSelectedGameId] = useState<number | null>(null);
  const mobile = useIsPhone();

  const data = useMemo(() => marketBoardPoints(games, metric), [games, metric]);

  const allX = data.points.map((p) => p.x);
  const allY = data.points.map((p) => p.y);
  const xDomain = domainFor(allX.length ? allX : [0, 1], 0.1);
  const yDomain = domainFor(allY.length ? allY : [0, 1], 0.1);

  // Harmonize domains so the diagonal y = x is symmetrical
  const unifiedMin = Math.min(xDomain[0], yDomain[0]);
  const unifiedMax = Math.max(xDomain[1], yDomain[1]);
  const unifiedDomain: [number, number] = [unifiedMin, unifiedMax];

  const title = CHART_REGISTRY["market-board"].title;
  const subtitle = chartSubtitle("market-board", shared.season, shared.week, "offense");

  const chart = (view: { width: number; height: number }, interactive: boolean) => (
    <MarketBoardChart
      points={data.points}
      metric={metric}
      xDomain={unifiedDomain}
      yDomain={unifiedDomain}
      width={view.width}
      height={view.height}
      selectedGameId={selectedGameId}
      onSelectGame={setSelectedGameId}
      interactive={interactive}
      label={`${title}. ${subtitle}`}
    />
  );

  return (
    <ChartFrame
      shared={shared}
      title={title}
      subtitle={subtitle}
      description={CHART_REGISTRY["market-board"].description}
      controls={
        <SegmentedControl
          size="sm"
          label="Market board metric"
          options={METRIC_OPTIONS}
          value={metric}
          onChange={setMetric}
          testId="market-board-metric-switcher"
        />
      }
      summary={chartSummary({
        side: null,
        week: { n: shared.week, through: false },
        filter: shared.filter,
        metric: metric === "spread" ? "Spread" : "Total",
      })}
      highlightTeams={[]}
      exportSpec={{
        filename: exportFilename("market-board", shared.season, shared.week, "offense", metric),
        width: EXPORT_SIZE.width,
        height: EXPORT_SIZE.height,
        card: (
          <ExportCard
            title={title}
            subtitle={`${subtitle} | ${metric === "spread" ? "Spread" : "Total"}`}
            footnote={CHART_REGISTRY["market-board"].footnote}
          >
            {chart({ width: EXPORT_SIZE.width - 24, height: EXPORT_CHART_HEIGHT }, false)}
          </ExportCard>
        ),
      }}
      hasData={data.points.length > 0}
      footnote={CHART_REGISTRY["market-board"].footnote}
      figure={
        <div className="w-full max-w-4xl mx-auto py-2">
          {data.points.length === 0 ? (
            <div className="text-center py-12 text-sm text-ink-muted">
              No market lines or model forecasts available for Week {shared.week}.
            </div>
          ) : (
            chart({ width: mobile ? 360 : 800, height: mobile ? 500 : 540 }, true)
          )}
        </div>
      }
    />
  );
}
