"use client";

import { useMemo, useState } from "react";
import {
  CHART_REGISTRY,
  GAME_LOG_METRICS,
  describeGameLogGame,
  gameLogFootnote,
  gameLogMetrics,
  groupLabel,
  rankText,
} from "@/lib/chart-config";
import {
  defaultGameLogTeam,
  gameLogDomains,
  matchesConference,
  teamGameLog,
  type AdjustedRow,
  type Domain,
  type GameLogGame,
  type GameLogMetric,
  type Side,
  type TeamGameLog,
  type TeamGameRow,
} from "@/lib/charts";
import { ChartFrame, EXPORT_CHART_HEIGHT, EXPORT_SIZE, ExportCard, type SharedChartProps } from "./ChartFrame";
import { SegmentedControl } from "@/components/ui/SegmentedControl";
import { GameLogChart } from "./GameLogChart";

const GAME_LOG_VIEW = { width: 1000, height: 560 };
const SCOPE_NOTE = "FBS opponents only";

export type GameLogViewProps = {
  shared: SharedChartProps;
  rows: TeamGameRow[];
  /** Adjusted rows of the latest stored window; they pick the default team. */
  adjusted: AdjustedRow[];
  initialMetric: GameLogMetric;
  /** The release serves yardage (`charts_v2`): offer the 20+ yard play rate. */
  explosiveness: boolean;
};

function SeasonStat({ side, log }: { side: Side; log: TeamGameLog }) {
  const { value, rank, ranked, average } = log.season[side];
  const format = GAME_LOG_METRICS[log.metric].value;
  return (
    <div className="flex flex-col" data-testid={`game-log-season-${side}`}>
      <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-faint">{side === "offense" ? "Offense" : "Defense allowed"}</span>
      <span className="text-lg font-bold tabular-nums text-ink">{value === null ? "n/a" : format(value)}</span>
      <span className="text-xs tabular-nums text-ink-muted" data-testid={`game-log-rank-${side}`}>{rank === null ? "Unranked" : `${rankText(rank, ranked)} nationally`}</span>
      {average !== null && <span className="text-xs tabular-nums text-ink-faint" data-testid={`game-log-average-${side}`}>FBS avg {format(average)}</span>}
    </div>
  );
}

/** Every game of one team: offense and defense-allowed bars against each week's FBS average. */
export function GameLogView({ shared, rows, adjusted, initialMetric, explosiveness }: GameLogViewProps) {
  const [metric, setMetric] = useState<GameLogMetric>(initialMetric);
  const { season, roster, filter, highlight } = shared;
  const team = highlight ?? defaultGameLogTeam(roster, rows, adjusted, filter);
  const log = useMemo(() => (team ? teamGameLog(roster, rows, team, metric) : null), [roster, rows, team, metric]);
  const { title: baseTitle, description } = CHART_REGISTRY["game-log"];
  const footnote = gameLogFootnote(metric);
  const title = team ? `${team} ${baseTitle.toLowerCase()}` : baseTitle;
  const metricText = GAME_LOG_METRICS[metric];
  const through = log?.throughWeek;
  const subtitle = [team ?? "No team", `${season}`, SCOPE_NOTE, ...(through === null || through === undefined ? [] : [`Through Week ${through}`])].join(" | ");
  const viewSubtitle = `${subtitle} | ${metricText.label} | ${groupLabel(filter)}`;
  const label = `${title}. ${subtitle}. ${metricText.label}`;
  const games = log?.games ?? [];
  const domains = log ? gameLogDomains(log) : { offense: [0, 1] as Domain, defense: [0, 1] as Domain };
  const describe = (game: GameLogGame) => describeGameLogGame(log!.team, game, metric);
  const slug = (team ?? "team").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

  const chart = (view: { width: number; height: number }, interactive: boolean) =>
    log && <GameLogChart log={log} domains={domains} formatTick={metricText.tick} formatValue={metricText.value} describe={describe} width={view.width} height={view.height} interactive={interactive} label={label} />;

  return (
    <ChartFrame
      // The picker shows the charted team, including the default one.
      shared={{ ...shared, highlight: team }}
      title={title}
      subtitle={subtitle}
      description={description}
      controls={
        <SegmentedControl
          size="sm"
          label="Game log metric"
          options={gameLogMetrics(explosiveness).map((option) => ({ value: option, label: GAME_LOG_METRICS[option].label, testId: `game-log-metric-${option.replaceAll("_", "-")}` }))}
          value={metric}
          onChange={setMetric}
          testId="game-log-metric-switcher"
        />
      }
      highlightTeams={roster.filter((r) => matchesConference(filter, r.team, r.conference))}
      exportSpec={{
        filename: `ckspicks-game-log-${slug}-${season}.png`,
        width: EXPORT_SIZE.width,
        height: EXPORT_SIZE.height,
        card: (
          <ExportCard title={title} subtitle={viewSubtitle} footnote={footnote}>
            {chart({ width: EXPORT_SIZE.width - 24, height: EXPORT_CHART_HEIGHT }, false)}
          </ExportCard>
        ),
      }}
      status={log && log.games.length > 0 && (
        <div className="space-y-2" data-testid="game-log-header">
          <p className="text-xs font-semibold text-ink-muted">{metricText.label}{through === null ? "" : `, through Week ${through}`}</p>
          <div className="flex flex-wrap items-start gap-x-10 gap-y-2">
            <SeasonStat side="offense" log={log} />
            <SeasonStat side="defense" log={log} />
          </div>
        </div>
      )}
      hasData={games.length > 0}
      emptyText={team ? `${team} has no FBS games in this release yet.` : "No team can be charted yet."}
      figure={
        <>
          <div className="overflow-x-auto focus-visible:outline-2 focus-visible:outline-accent" role="region" aria-label="Team game log chart, horizontally scrollable" tabIndex={0} data-testid="game-log-scroll">
            <div className="min-w-[640px] lg:min-w-0">{chart(GAME_LOG_VIEW, true)}</div>
          </div>
        </>
      }
      footnote={footnote}
    />
  );
}
