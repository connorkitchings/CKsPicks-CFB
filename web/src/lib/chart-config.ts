import {
  formatEpa,
  formatPercent,
  type AdjustedRow,
  type AdjustedScatter,
  type ChartKind,
  type ConferenceFilter,
  type EfficiencyMetric,
  type RosterRow,
  type ScatterPoint,
  type Side,
  type TrajectoryMetric,
} from "./charts.ts";
import { scheduleReading, type ScheduleRow } from "./charts.ts";
import type { GameLogGame, GameLogMetric } from "./charts.ts";

/**
 * Registry of the team charts: one entry per chart kind with its picker group, labels,
 * URL controls and footnote, plus the per-side/per-metric axis text of the scatters.
 * Views and the page read everything chart-specific from here.
 */

export type { ChartKind };

// ---------------------------------------------------------------------------
// Chart registry
// ---------------------------------------------------------------------------

export type ChartGroup = "games" | "teams" | "one-team";

/** Picker groups, in display order. */
export const CHART_GROUPS: readonly { id: ChartGroup; label: string }[] = [
  { id: "games", label: "Games" },
  { id: "teams", label: "Teams" },
  { id: "one-team", label: "One team" },
];

export type ChartDefinition = {
  group: ChartGroup;
  /** Picker link text. */
  tabLabel: string;
  /** Section heading and export title. */
  title: string;
  controls: {
    /** Reads `side=offense|defense`. */
    side: boolean;
    /** `week=N` meaning: a single week, a "Through Week N" window, or no week selector. */
    week: "week" | "through-week" | null;
    /** Seeds and persists the highlighted team from `team=`. */
    team: boolean;
  };
  /** Default footnote (a scatter metric may override it via its `ScatterConfig`). */
  footnote: string;
  /**
   * False until the chart's view ships: the kind is hidden from the picker and a URL
   * naming it falls back to the default chart.
   */
  ready: boolean;
};

const RELEASE_NOTE = "Reconstructed from this release's data.";

/** Picker order within each group follows key order. */
export const CHART_REGISTRY: Record<ChartKind, ChartDefinition> = {
  "net-success": {
    group: "games",
    tabLabel: "Net success rate",
    title: "Did We Really Get Beat That Bad?",
    controls: { side: false, week: "week", team: false },
    footnote: `Bar = winner's offensive success-rate advantage/disadvantage in percentage points, on eligible plays (regulation only; garbage time and special teams excluded). Label = winner and final score. ${RELEASE_NOTE}`,
    ready: true,
  },
  efficiency: {
    group: "teams",
    tabLabel: "Efficiency",
    title: "Efficiency vs Explosiveness",
    controls: { side: true, week: "through-week", team: true },
    footnote: efficiencyFootnote("PPA/play"),
    ready: true,
  },
  adjusted: {
    group: "teams",
    tabLabel: "Adjusted PPA/play",
    title: "Opponent-adjusted PPA/play",
    controls: { side: false, week: "through-week", team: true },
    footnote: `PPA/play adjusted for opponent strength and home-field venue using the V5 iterative adjuster, FBS vs FBS games. Dashed lines are play-weighted FBS averages; diagonals mark equal net (offense minus defense allowed). ${RELEASE_NOTE}`,
    ready: true,
  },
  schedule: {
    group: "teams",
    tabLabel: "Schedule adjustment",
    title: "Schedule adjustment",
    controls: { side: true, week: "through-week", team: true },
    footnote: `Each row runs from venue-neutral PPA/play (raw minus the home-field venue correction; hollow dot) to opponent-adjusted PPA/play from the V5 iterative adjuster (filled dot), FBS vs FBS games. Schedule effect is in better-is-positive units: positive means raw understated: tougher opponents than average; negative means raw inflated: weaker opponents. On defense, values are PPA/play allowed and the axis is inverted so better is right. ${RELEASE_NOTE}`,
    ready: true,
  },
  trajectory: {
    group: "teams",
    tabLabel: "Trajectory",
    title: "Team trajectory",
    controls: { side: false, week: null, team: true },
    footnote: `Opponent- and venue-adjusted PPA/play (V5 iterative adjuster, FBS vs FBS games) for every stored Through Week window; net is offense minus defense allowed. The dashed line is each window's play-weighted FBS average. A gap means the team has no adjusted value in that window (for net, either role); a lone window is a dot. ${RELEASE_NOTE}`,
    ready: true,
  },
  "game-log": {
    group: "one-team",
    tabLabel: "Game log",
    title: "Team game log",
    controls: { side: false, week: null, team: true },
    footnote: `Bars = the team's value in each game on eligible plays (regulation only; garbage time and special teams excluded), FBS opponents only. Dashed marks = that week's FBS average, pooled over every FBS team-game. Defense shows values allowed, axis inverted so up is better; n/a = no eligible plays for the metric. Season values and national ranks match Efficiency for the latest week. ${RELEASE_NOTE}`,
    ready: true,
  },
};

export const DEFAULT_CHART: ChartKind = "net-success";

/** Kinds whose views ship, in picker order. */
export function readyKinds(): ChartKind[] {
  return (Object.keys(CHART_REGISTRY) as ChartKind[]).filter((kind) => CHART_REGISTRY[kind].ready);
}

/** Picker groups with their ready kinds; a group without one is omitted. */
export function pickerGroups(): { id: ChartGroup; label: string; kinds: ChartKind[] }[] {
  const ready = readyKinds();
  return CHART_GROUPS.map((group) => ({ ...group, kinds: ready.filter((kind) => CHART_REGISTRY[kind].group === group.id) }))
    .filter((group) => group.kinds.length > 0);
}

// ---------------------------------------------------------------------------
// URL params
// ---------------------------------------------------------------------------

type RawParam = string | string[] | undefined | null;

/** A ready chart kind, else the default chart. */
export function parseChartKind(raw: RawParam): ChartKind {
  return typeof raw === "string" && readyKinds().includes(raw as ChartKind) ? (raw as ChartKind) : DEFAULT_CHART;
}

export function parseSide(raw: RawParam): Side {
  return raw === "defense" ? "defense" : "offense";
}

/** Trajectory `metric=net|offense|defense`; net by default. */
export function parseTrajectoryMetric(raw: RawParam): TrajectoryMetric {
  return raw === "offense" || raw === "defense" ? raw : "net";
}

/** Trajectory metric switcher text and y-axis label, in toggle order. */
export const TRAJECTORY_METRICS: Record<TrajectoryMetric, { label: string; yLabel: string }> = {
  net: { label: "Net", yLabel: "Adjusted net PPA/play (offense − defense allowed)" },
  offense: { label: "Offense", yLabel: "Adjusted offense PPA/play" },
  defense: { label: "Defense", yLabel: "Adjusted defense PPA/play allowed" },
};

/**
 * The roster team named by `team=`, or null when the param is missing, repeated or not a
 * roster team. Matching ignores case and surrounding space; the roster spelling is returned.
 */
export function parseTeamParam(raw: RawParam, roster: readonly RosterRow[]): string | null {
  if (typeof raw !== "string") return null;
  const wanted = raw.trim().toLowerCase();
  if (!wanted) return null;
  return roster.find((row) => row.team.toLowerCase() === wanted)?.team ?? null;
}

/**
 * `/charts` URL of `kind`. Only the params the chart reads are written, except `team`,
 * which is always carried so the highlight persists across charts.
 */
export function chartHref(kind: ChartKind, options: { side?: Side; week?: number | null; team?: string | null } = {}): string {
  const { controls } = CHART_REGISTRY[kind];
  const q = new URLSearchParams({ chart: kind });
  if (controls.side) q.set("side", options.side ?? "offense");
  if (controls.week && options.week !== null && options.week !== undefined) q.set("week", String(options.week));
  if (options.team) q.set("team", options.team);
  return `/charts?${q.toString()}`;
}

/** `href` with `team` set (or removed when null), keeping every other param. */
export function withTeamParam(href: string, team: string | null): string {
  const [path, query = ""] = href.split("?");
  const q = new URLSearchParams(query);
  if (team) q.set("team", team);
  else q.delete("team");
  const text = q.toString();
  return text ? `${path}?${text}` : path;
}

// ---------------------------------------------------------------------------
// Text
// ---------------------------------------------------------------------------

/** `as_of_week = N + 1` is shown as "Through Week N". */
export function chartSubtitle(kind: ChartKind, season: number, week: number, side: Side): string {
  const base = `${season} | FBS vs FBS`;
  const { controls } = CHART_REGISTRY[kind];
  if (controls.week === "week") return `Week ${week} | ${base}`;
  const sideText = controls.side ? `${side === "offense" ? "Offense" : "Defense"} | ` : "";
  return controls.week === "through-week" ? `${sideText}${base} | Through Week ${week}` : `${sideText}${base}`;
}

export function groupLabel(filter: ConferenceFilter): string {
  return filter === "all" ? "All FBS" : filter === "p4" ? "Power Four + Notre Dame" : filter;
}

export function exportFilename(kind: ChartKind, season: number, week: number, side: Side): string {
  const { controls } = CHART_REGISTRY[kind];
  const sideText = controls.side ? `-${side}` : "";
  const weekText = controls.week === "week" ? `-week-${week}` : controls.week === "through-week" ? `-through-week-${week}` : "";
  return `ckspicks-${kind}${sideText}-${season}${weekText}.png`;
}

export function conferenceLabel(conference: string | null): string {
  return conference ?? "Independent";
}

// ---------------------------------------------------------------------------
// Scatter axes, per kind / side / metric
// ---------------------------------------------------------------------------

export type CornerCaptions = {
  topLeft: string;
  topRight: string;
  bottomLeft: string;
  bottomRight: string;
  note: string;
};

export type ScatterConfig = {
  xLabel: string;
  yLabel: string;
  /** Axis tick text. */
  tickX: (value: number) => string;
  tickY: (value: number) => string;
  /** Table and tooltip value text. */
  valueX: (value: number) => string;
  valueY: (value: number) => string;
  /** Short metric name shown in the export subtitle; empty when the chart has one metric. */
  metricLabel: string;
  captions: CornerCaptions;
  footnote: string;
};

const AVERAGES_NOTE = "Relative to play-weighted FBS averages";
/** Percent tick: whole when the tick is a whole percent, else one decimal (`7.5%`), so ticks never repeat. */
export function percentTick(value: number): string {
  const tenths = Math.round(value * 1000);
  return tenths % 10 === 0 ? `${tenths / 10}%` : `${(tenths / 10).toFixed(1)}%`;
}

function efficiencyFootnote(metric: string): string {
  return `Cumulative success rate and ${metric} on eligible plays (regulation only; garbage time and special teams excluded), FBS vs FBS games. Dashed lines are FBS averages. On defense, axes are inverted so up and right is better. ${RELEASE_NOTE}`;
}

type EfficiencyMetricText = {
  /** Toggle button and export subtitle. */
  label: string;
  yLabel: Record<Side, string>;
  /** Corner caption term. */
  caption: string;
  /** Footnote term. */
  footnote: string;
  /** Tooltip term. */
  describe: string;
  tick: (value: number) => string;
  value: (value: number) => string;
};

export const EFFICIENCY_METRICS: Record<EfficiencyMetric, EfficiencyMetricText> = {
  ppa: {
    label: "PPA/play",
    yLabel: { offense: "PPA/play", defense: "PPA/play" },
    caption: "PPA",
    footnote: "PPA/play",
    describe: "PPA/play",
    tick: formatEpa,
    value: formatEpa,
  },
  explosive_rate: {
    label: "20+ Yard Rate",
    yLabel: { offense: "20+ Yard Play Rate", defense: "20+ Yard Play Rate Allowed" },
    caption: "20+ rate",
    footnote: "20+ yard play rate",
    describe: "20+ yard rate",
    tick: percentTick,
    value: formatPercent,
  },
  yards_per_success: {
    label: "Yards / Success",
    yLabel: { offense: "Yards / Successful Play", defense: "Yards / Success Allowed" },
    caption: "yards/success",
    footnote: "yards per successful play",
    describe: "yards/success",
    tick: (value) => `${Math.round(value)} yds`,
    value: (value) => `${value.toFixed(2)} yds`,
  },
};

/** Explosiveness metrics, in toggle order; the first is the default when yardage is served. */
export const EXPLOSIVENESS_METRICS: readonly EfficiencyMetric[] = ["explosive_rate", "yards_per_success"];

export function parseEfficiencyMetric(raw: RawParam, explosiveness: boolean): EfficiencyMetric {
  if (!explosiveness) return "ppa";
  return raw === "yards_per_success" || raw === "yards-per-success" ? "yards_per_success" : "explosive_rate";
}

export function efficiencyConfig(side: Side, metric: EfficiencyMetric): ScatterConfig {
  const text = EFFICIENCY_METRICS[metric];
  const m = text.caption;
  const captions: CornerCaptions = side === "defense"
    ? {
        topLeft: `Higher allowed success / Lower allowed ${m}`,
        topRight: `Lower allowed success / Lower allowed ${m}`,
        bottomLeft: `Higher allowed success / Higher allowed ${m}`,
        bottomRight: `Lower allowed success / Higher allowed ${m}`,
        note: AVERAGES_NOTE,
      }
    : {
        topLeft: `Lower success / Higher ${m}`,
        topRight: `Higher success / Higher ${m}`,
        bottomLeft: `Lower success / Lower ${m}`,
        bottomRight: `Higher success / Lower ${m}`,
        note: AVERAGES_NOTE,
      };
  return {
    xLabel: "Success Rate",
    yLabel: text.yLabel[side],
    tickX: percentTick,
    tickY: text.tick,
    valueX: formatPercent,
    valueY: text.value,
    metricLabel: text.label,
    captions,
    footnote: efficiencyFootnote(text.footnote),
  };
}

export function describeEfficiencyPoint(point: ScatterPoint, metric: EfficiencyMetric): string {
  const text = EFFICIENCY_METRICS[metric];
  return `${point.team} (${conferenceLabel(point.conference)}): success rate ${formatPercent(point.x)}, ${text.describe} ${text.value(point.y)}, ${point.n} plays`;
}

/** Two-decimal signed PPA for axis ticks (`+0.10`). */
export function formatEpaTick(value: number): string {
  const text = value.toFixed(2);
  return Number(text) > 0 ? `+${text}` : Number(text) === 0 ? "0.00" : text;
}

export const ADJUSTED_CONFIG: ScatterConfig = {
  xLabel: "Adjusted offense PPA/play",
  yLabel: "Adjusted defense PPA/play allowed",
  tickX: formatEpaTick,
  tickY: formatEpaTick,
  valueX: formatEpa,
  valueY: formatEpa,
  metricLabel: "",
  captions: {
    topLeft: "Lower offense / Better defense",
    topRight: "Better offense / Better defense",
    bottomLeft: "Lower offense / Higher defense allowed",
    bottomRight: "Better offense / Higher defense allowed",
    note: `${AVERAGES_NOTE}; diagonals: equal net PPA (offense − defense allowed)`,
  },
  footnote: CHART_REGISTRY.adjusted.footnote,
};

function describeRole(name: string, row: AdjustedRow): string {
  return `${name} adjusted ${formatEpa(row.adjustedEpaPerPlay)} (raw ${formatEpa(row.rawEpaPerPlay)}, venue correction ${formatEpa(row.venueCorrection)}, opponent adjustment ${formatEpa(row.opponentAdjustment)}), rank ${row.adjustedRank} of ${row.cohortSize}`;
}

/** Tooltip text of one adjusted point, with the stored decomposition of both roles. */
export function describeAdjustedPoint(point: ScatterPoint, roles: AdjustedScatter["roles"]): string {
  const head = `${point.team} (${conferenceLabel(point.conference)})`;
  const role = roles[point.team];
  if (!role) return `${head}: adjusted offense ${formatEpa(point.x)}, adjusted defense allowed ${formatEpa(point.y)} PPA/play`;
  return `${head}: ${describeRole("offense", role.offense)}; ${describeRole("defense allowed", role.defense)} PPA/play`;
}

// ---------------------------------------------------------------------------
// Schedule adjustment
// ---------------------------------------------------------------------------

export function scheduleAxisLabel(side: Side): string {
  return side === "defense"
    ? "Defense PPA/play allowed (axis inverted: better is right)"
    : "Offense PPA/play";
}

/** Tooltip and accessible text of one schedule row, with the full decomposition. */
export function describeScheduleRow(row: ScheduleRow, side: Side): string {
  const unit = side === "defense" ? "PPA/play allowed" : "PPA/play";
  const reading = scheduleReading(row.effect);
  return `${row.team} (${conferenceLabel(row.conference)}): raw ${formatEpa(row.raw)}, venue correction ${formatEpa(row.venueCorrection)}, venue-neutral ${formatEpa(row.neutral)}, adjusted ${formatEpa(row.adjusted)} ${unit}; schedule effect ${formatEpa(row.effect)}${reading ? ` (${reading})` : ""}, ${row.epaN} plays`;
}

// ---------------------------------------------------------------------------
// Team game log
// ---------------------------------------------------------------------------

export const GAME_LOG_METRICS: Record<GameLogMetric, { label: string; tick: (value: number) => string; value: (value: number) => string }> = {
  success: { label: "Success rate", tick: percentTick, value: formatPercent },
  ppa: { label: "PPA/play", tick: formatEpaTick, value: formatEpa },
  explosive_rate: { label: "20+ yard play rate", tick: percentTick, value: formatPercent },
};

/** Game-log metrics in toggle order; the explosive rate needs served yardage (`charts_v2`). */
export function gameLogMetrics(explosiveness: boolean): GameLogMetric[] {
  return explosiveness ? ["success", "ppa", "explosive_rate"] : ["success", "ppa"];
}

/** An offered game-log metric, else success rate. */
export function parseGameLogMetric(raw: RawParam, explosiveness: boolean): GameLogMetric {
  return gameLogMetrics(explosiveness).find((metric) => metric === raw) ?? "success";
}

const ordinal = (n: number) => {
  const tens = n % 100;
  const suffix = tens >= 11 && tens <= 13 ? "th" : ["th", "st", "nd", "rd"][n % 10] ?? "th";
  return `${n}${suffix}`;
};

/** `12th of 133`, or empty when unranked. */
export function rankText(rank: number | null, ranked: number): string {
  return rank === null ? "" : `${ordinal(rank)} of ${ranked}`;
}

/** Tooltip and accessible text of one game-log game. */
export function describeGameLogGame(team: string, game: GameLogGame, metric: GameLogMetric): string {
  const { label, value } = GAME_LOG_METRICS[metric];
  const where = game.site === "away" ? "at" : "vs";
  const site = game.site === "neutral" ? " (neutral site)" : "";
  const side = (name: string, own: number | null, average: number | null) =>
    `${name} ${own === null ? "n/a" : value(own)}${average === null ? "" : ` (FBS week average ${value(average)})`}`;
  return `Week ${game.week}: ${team} ${where} ${game.opponent}${site}, ${game.result}. ${label}: ${side("offense", game.offense, game.average.offense)}; ${side("defense allowed", game.defense, game.average.defense)}`;
}
