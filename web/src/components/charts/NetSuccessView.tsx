"use client";

import { useState, useSyncExternalStore } from "react";
import { CHART_REGISTRY, chartSubtitle, exportFilename, groupLabel } from "@/lib/chart-config";
import {
  filterNetSuccessBars,
  formatPercent,
  outplayedWinners,
  sortNetSuccessBars,
  type NetSuccessBar,
  type NetSuccessSort,
  type NotCharted,
} from "@/lib/charts";
import { ChartFrame, EXPORT_CHART_HEIGHT, EXPORT_SIZE, ExportCard, SegmentedControl, type SharedChartProps } from "./ChartFrame";
import { ChartTable, type TableColumn } from "./ChartTable";
import { NetSuccessChart } from "./NetSuccessChart";

// The net-success width max(1000, 70 + 15 n) exports at 2x as max(2000, 140 + 30 n) px.
const netSuccessWidth = (games: number) => Math.max(1000, 70 + 15 * games);

const subscribeNarrow = (callback: () => void) => {
  const query = window.matchMedia("(max-width: 639px)");
  query.addEventListener("change", callback);
  return () => query.removeEventListener("change", callback);
};
const isNarrow = () => window.matchMedia("(max-width: 639px)").matches;
const serverWide = () => false;

const SORTS: readonly { value: NetSuccessSort; label: string; testId: string }[] = [
  { value: "gap", label: "Success gap", testId: "sort-success-gap" },
  { value: "margin", label: "Final margin", testId: "sort-final-margin" },
];

function describeBar(b: NetSuccessBar): string {
  return `${b.winner} beat ${b.loser} ${b.winnerPoints}-${b.loserPoints}: offensive success rate ${formatPercent(b.winnerSuccessRate)} to ${formatPercent(b.loserSuccessRate)}, winner's success-rate ${b.value >= 0 ? "advantage" : "disadvantage"} ${Math.abs(b.value * 100).toFixed(1)} percentage points`;
}

const columns: TableColumn<NetSuccessBar>[] = [
  { key: "winner", label: "Winner", value: (r) => r.winner },
  { key: "loser", label: "Loser", value: (r) => r.loser },
  { key: "score", label: "Score", value: (r) => r.winnerPoints - r.loserPoints, format: (r) => `${r.winnerPoints}-${r.loserPoints}`, numeric: true },
  { key: "winnerRate", label: "Winner success", value: (r) => r.winnerSuccessRate, format: (r) => formatPercent(r.winnerSuccessRate), numeric: true },
  { key: "loserRate", label: "Loser success", value: (r) => r.loserSuccessRate, format: (r) => formatPercent(r.loserSuccessRate), numeric: true },
  { key: "value", label: "Difference (percentage points)", value: (r) => r.value, format: (r) => (r.value * 100).toFixed(1), numeric: true },
];

/** One bar per game of the week: the winner's success-rate edge, in team colors. No team finder. */
export function NetSuccessView({ shared, bars, notCharted }: { shared: SharedChartProps; bars: NetSuccessBar[]; notCharted: NotCharted[] }) {
  const [sort, setSort] = useState<NetSuccessSort>("gap");
  const narrow = useSyncExternalStore(subscribeNarrow, isNarrow, serverWide);
  const { season, week, roster, filter } = shared;
  const title = CHART_REGISTRY["net-success"].title;
  const footnote = CHART_REGISTRY["net-success"].footnote;
  const subtitle = chartSubtitle("net-success", season, week, "offense");
  const shown = sortNetSuccessBars(filterNetSuccessBars(bars, roster, filter), sort);
  const { outplayed, total } = outplayedWinners(shown);
  const viewSubtitle = `${subtitle} | ${groupLabel(filter)}`;
  const label = `${title}. ${subtitle}`;
  const exportWidth = netSuccessWidth(shown.length);

  return (
    <ChartFrame
      shared={shared}
      title={title}
      subtitle={subtitle}
      controls={<SegmentedControl label="Sort" showLabel options={SORTS} value={sort} onChange={setSort} testId="net-success-sort" />}
      exportSpec={{
        filename: exportFilename("net-success", season, week, "offense"),
        width: exportWidth,
        height: EXPORT_SIZE.height,
        card: (
          <ExportCard title={title} subtitle={viewSubtitle} footnote={footnote}>
            <NetSuccessChart bars={shown} stateOf={() => "active"} describe={describeBar} width={exportWidth - 24} height={EXPORT_CHART_HEIGHT} interactive={false} label={label} />
          </ExportCard>
        ),
      }}
      status={total > 0 && (
        <p className="text-sm text-ink" data-testid="net-success-summary">
          <span className="font-semibold tabular-nums">{outplayed} of {total}</span> winners had the lower success rate.
        </p>
      )}
      hasData={shown.length > 0}
      figure={
        <NetSuccessChart
          bars={shown}
          stateOf={() => "active"}
          describe={describeBar}
          orientation={narrow ? "horizontal" : "vertical"}
          width={narrow ? 420 : netSuccessWidth(shown.length)}
          height={narrow ? 56 + 36 * shown.length : 640}
          label={label}
        />
      }
      table={<ChartTable key={sort} rows={shown} columns={columns} rowKey={(r) => String(r.gameId)} caption={`${title}, ${viewSubtitle}`} initialSort={{ key: sort === "gap" ? "value" : "score" }} />}
      notCharted={notCharted}
      footnote={footnote}
    />
  );
}
