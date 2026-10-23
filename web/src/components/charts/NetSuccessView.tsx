"use client";

import { CHART_REGISTRY, chartSubtitle, exportFilename, groupLabel } from "@/lib/chart-config";
import {
  filterNetSuccessBars,
  formatPercent,
  outplayedWinners,
  type NetSuccessBar,
  type NotCharted,
} from "@/lib/charts";
import { chartSummary } from "@/components/ui/SummaryLine";
import { ChartFrame, EXPORT_CHART_HEIGHT, EXPORT_SIZE, ExportCard, type SharedChartProps } from "./ChartFrame";
import { NetSuccessChart } from "./NetSuccessChart";
import { useIsPhone } from "@/lib/use-is-phone";

// The net-success width max(1000, 70 + 15 n) exports at 2x as max(2000, 140 + 30 n) px.
const netSuccessWidth = (games: number) => Math.max(1000, 70 + 15 * games);

function describeBar(b: NetSuccessBar): string {
  return `${b.winner} beat ${b.loser} ${b.winnerPoints}-${b.loserPoints}: offensive success rate ${formatPercent(b.winnerSuccessRate)} to ${formatPercent(b.loserSuccessRate)}, winner's success-rate ${b.value >= 0 ? "advantage" : "disadvantage"} ${Math.abs(b.value * 100).toFixed(1)} percentage points`;
}

/** One bar per game of the week: the winner's success-rate edge, in team colors. No team finder. */
export function NetSuccessView({ shared, bars, notCharted }: { shared: SharedChartProps; bars: NetSuccessBar[]; notCharted: NotCharted[] }) {
  const narrow = useIsPhone();
  const { season, week, roster, filter } = shared;
  const { title, credit, footnote } = CHART_REGISTRY["net-success"];
  const subtitle = chartSubtitle("net-success", season, week, "offense");
  // `bars` arrive in success-gap order (netSuccessBars) and filtering keeps it.
  const shown = filterNetSuccessBars(bars, roster, filter);
  const { outplayed, total } = outplayedWinners(shown);
  const viewSubtitle = `${subtitle} | ${groupLabel(filter)}`;
  const label = `${title}. ${subtitle}`;
  const exportWidth = netSuccessWidth(shown.length);

  return (
    <ChartFrame
      shared={shared}
      title={title}
      subtitle={subtitle}
      summary={chartSummary({ week: { n: week, through: false }, filter })}
      description={CHART_REGISTRY["net-success"].description}
      credit={credit}
      exportSpec={{
        filename: exportFilename("net-success", season, week, "offense"),
        width: exportWidth,
        height: EXPORT_SIZE.height,
        card: (
          <ExportCard title={title} subtitle={viewSubtitle} credit={credit} footnote={footnote}>
            <NetSuccessChart bars={shown} stateOf={() => "active"} describe={describeBar} width={exportWidth - 24} height={EXPORT_CHART_HEIGHT} interactive={false} label={label} />
          </ExportCard>
        ),
      }}
      headerControls={total > 0 && (
        <p className="text-xs text-ink-muted sm:self-start sm:text-[13px]" data-testid="net-success-summary">
          <span className="text-lg font-bold tracking-tight text-ink tabular-nums">{outplayed} of {total}</span> winners had the lower success rate.
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
          height={narrow ? 56 + 48 * shown.length : 640}
          label={label}
        />
      }
      notCharted={notCharted}
      footnote={footnote}
    />
  );
}
