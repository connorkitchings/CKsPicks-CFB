import {
  formatEpa,
  formatPercent,
  type AdjustedRow,
  type AdjustedScatter,
  type ChartKind,
  type ConferenceFilter,
  type EfficiencyMetric,
  type MarketBoardMetric,
  type PossessionMetric,
  type PossessionRow,
  type PossessionScatter,
  type RatingMetric,
  type RatingTrajectoryData,
  type RatingTrajectorySeries,
  type RosterRow,
  type ScatterPoint,
  type Side,
} from "./charts.ts";
import type { GameLogGame, GameLogMetric } from "./charts.ts";
import { EXPORT_PREFIX } from "./brand.ts";

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

/** Picker groups, in display order; `label` is the heading shown above each group's tabs. */
export const CHART_GROUPS: readonly { id: ChartGroup; label: string }[] = [
  { id: "games", label: "Games" },
  { id: "teams", label: "Teams" },
  { id: "one-team", label: "One team" },
];

/** How a play counts as successful, in the words the charts print under their titles. */
export const SUCCESS_RATE_DEFINITION =
  "Success rate is the share of plays that gain 50% of the yards to go on 1st down, 70% on 2nd, and all of it on 3rd or 4th.";

const PPA_DEFINITION = "PPA/play is the average predicted points added per play.";
const EXPLOSIVE_DEFINITION = "20+ yard rate is the share of plays that gain 20 or more yards.";

/** The game log footnote without its metric definition (scope and axis notes live on the chart itself). */
const GAME_LOG_NOTE = "Bars = the team's value in each game on eligible plays (regulation only; garbage time and special teams excluded). Dashed marks = that week's FBS average, pooled over every FBS team-game. n/a = no eligible plays for the metric. Season values and national ranks match Efficiency for the latest week.";

export type ChartDefinition = {
  group: ChartGroup;
  /** Picker link text. */
  tabLabel: string;
  /** Section heading and export title. */
  title: string;
  /** One plain sentence under the title on the page; the PNG export carries the full metadata line instead. */
  description: string;
  /** Attribution shown under the header subtitle and in the PNG export. */
  credit?: string;
  /** Who and which games the chart covers, shown in the subtitle and the page eyebrow. */
  population: string;
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
   * False while the chart is not shown (view not shipped, or hidden by decision): the kind
   * is hidden from the picker and a URL naming it falls back to the default chart.
   */
  ready: boolean;
};

/** Charts built from FBS-vs-FBS games only. */
const FBS_GAMES = "FBS vs FBS";

/** Picker order within each group follows key order. */
export const CHART_REGISTRY: Record<ChartKind, ChartDefinition> = {
  "net-success": {
    group: "games",
    tabLabel: "Net success rate",
    title: "Net success rate",
    description: "Each game's winner minus loser success rate, in percentage points.",
    credit: "Inspired by Parker Fleming: “Did We Really Get Beat That Bad?”",
    population: FBS_GAMES,
    controls: { side: false, week: "week", team: false },
    footnote: `Bar = winner's offensive success-rate advantage/disadvantage in percentage points, on eligible plays (regulation only; garbage time and special teams excluded). Label = winner and final score. ${SUCCESS_RATE_DEFINITION}`,
    ready: true,
  },
  efficiency: {
    group: "teams",
    tabLabel: "Efficiency vs explosiveness",
    title: "Efficiency vs explosiveness",
    description: "Each team's success rate against its explosiveness.",
    population: FBS_GAMES,
    controls: { side: true, week: "through-week", team: true },
    footnote: efficiencyFootnote("PPA/play", PPA_DEFINITION),
    ready: true,
  },
  adjusted: {
    group: "teams",
    tabLabel: "Adjusted PPA/play",
    title: "Adjusted PPA/play",
    description: "Offense against defense allowed, each adjusted for opponent strength.",
    population: FBS_GAMES,
    controls: { side: false, week: "through-week", team: true },
    footnote: `PPA/play adjusted for opponent strength and home-field venue using the V5 iterative adjuster, FBS vs FBS games. ${PPA_DEFINITION} Dashed lines are play-weighted FBS averages; quadrant names are relative to them.`,
    ready: true,
  },
  "rating-trajectory": {
    group: "teams",
    tabLabel: "V5 ratings",
    title: "V5 rating trajectory",
    description: "V5 model ratings after each week's games.",
    population: "FBS teams",
    controls: { side: false, week: null, team: true },
    footnote: `V5 model ratings after each week's games (Through Week 0 onward), on the rating scale, not PPA/play. Higher is better for every component, defense included; overall is the mean of offense and defense. Ratings are not centered at zero: the dashed line is each week's unweighted mean over FBS roster teams. A gap means the team has no snapshot that week; a lone week is a dot. From this release's V5 rating snapshots.`,
    // Hidden from /stats by owner decision on 2026-10-18 (reserved for the Ratings tab); view code retained.
    ready: false,
  },
  possession: {
    group: "teams",
    tabLabel: "Possession efficiency",
    title: "Possession efficiency",
    description: "Offense against defense allowed, adjusted for opponent strength, per possession.",
    population: "FBS teams, all games",
    controls: { side: false, week: "through-week", team: true },
    footnote: possessionFootnote("points per possession"),
    ready: true,
  },
  "game-log": {
    group: "one-team",
    tabLabel: "Game log",
    title: "Game log",
    description: "Every game this season against that week's FBS average.",
    population: FBS_GAMES,
    controls: { side: false, week: null, team: true },
    footnote: `${GAME_LOG_NOTE} ${SUCCESS_RATE_DEFINITION}`,
    ready: true,
  },
  downs: {
    group: "teams",
    tabLabel: "Situational downs",
    title: "Situational downs",
    description: "Early down EPA against 3rd and 4th down conversion rate.",
    population: FBS_GAMES,
    controls: { side: true, week: "through-week", team: true },
    footnote: downsFootnote(),
    ready: true,
  },
  "finishing-drives": {
    group: "teams",
    tabLabel: "Finishing drives",
    title: "Finishing drives",
    description: "Scoring opportunities per drive against points per scoring opportunity.",
    population: FBS_GAMES,
    controls: { side: true, week: "through-week", team: true },
    footnote: finishingDrivesFootnote(),
    ready: true,
  },
  "resume-quality": {
    group: "teams",
    tabLabel: "Resume vs dominance",
    title: "Resume vs dominance",
    description: "V5 model rating dominance against strength of record (SOR).",
    population: "FBS teams",
    controls: { side: false, week: "through-week", team: true },
    footnote: resumeQualityFootnote(),
    ready: false,
  },
  "market-board": {
    group: "games",
    tabLabel: "Slate market board",
    title: "Slate market board",
    description: "Market betting line against V5 model forecast across the weekly slate.",
    population: "Weekly slate",
    controls: { side: false, week: "week", team: false },
    footnote: marketBoardFootnote(),
    ready: false,
  },
};

export const DEFAULT_CHART: ChartKind = "net-success";

/** Kinds whose views ship, in picker order. */
export function readyKinds(): ChartKind[] {
  return (Object.keys(CHART_REGISTRY) as ChartKind[]).filter((kind) => CHART_REGISTRY[kind].ready);
}

/** A footnote as one entry per sentence, so each can sit on its own line. */
export function footnoteLines(footnote: string): string[] {
  return footnote.split(/(?<=[.!?])\s+(?=[A-Z0-9])/).filter(Boolean);
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

/** V5 rating trajectory `metric=overall|offense|defense`; overall by default. */
export function parseRatingMetric(raw: RawParam): RatingMetric {
  return raw === "offense" || raw === "defense" ? raw : "overall";
}

/** V5 rating metric switcher text and y-axis label, in toggle order. Every axis is higher-is-better. */
export const RATING_METRICS: Record<RatingMetric, { label: string; yLabel: string }> = {
  overall: { label: "Overall", yLabel: "V5 overall rating" },
  offense: { label: "Offense", yLabel: "V5 offense rating" },
  defense: { label: "Defense", yLabel: "V5 defense rating" },
};

/** Possession `metric=ppp|epa_per_possession` (also `epa-per-possession`, `ppa_per_possession`, `ppa-per-possession`); points per possession by default. */
export function parsePossessionMetric(raw: RawParam): PossessionMetric {
  return typeof raw === "string" && /^(epa|ppa)[_-]per[_-]possession$/.test(raw) ? "epa_per_possession" : "ppp";
}

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
 * `/stats` URL of `kind`. Only the params the chart reads are written, except `team`,
 * which is always carried so the highlight persists across charts.
 */
export function chartHref(kind: ChartKind, options: { side?: Side; week?: number | null; team?: string | null } = {}): string {
  const { controls } = CHART_REGISTRY[kind];
  const q = new URLSearchParams({ chart: kind });
  if (controls.side) q.set("side", options.side ?? "offense");
  if (controls.week && options.week !== null && options.week !== undefined) q.set("week", String(options.week));
  if (options.team) q.set("team", options.team);
  return `/stats?${q.toString()}`;
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
  const base = `${season} | ${CHART_REGISTRY[kind].population}`;
  const { controls } = CHART_REGISTRY[kind];
  if (controls.week === "week") return `Week ${week} | ${base}`;
  const sideText = controls.side ? `${side === "offense" ? "Offense" : "Defense"} | ` : "";
  return controls.week === "through-week" ? `${sideText}${base} | Through Week ${week}` : `${sideText}${base}`;
}

/** Id of the empty slot in the sticky phone chart bar that receives the settings trigger. */
export const SETTINGS_SLOT_ID = "chart-settings-slot";

export function groupLabel(filter: ConferenceFilter): string {
  return filter === "all" ? "All FBS" : filter === "p4" ? "Power Four + Notre Dame" : filter;
}

/** PNG name; `metric` (a slug) follows the kind when the chart has a metric switcher. */
export function exportFilename(kind: ChartKind, season: number, week: number, side: Side, metric?: string): string {
  const { controls } = CHART_REGISTRY[kind];
  const metricText = metric ? `-${metric}` : "";
  const sideText = controls.side ? `-${side}` : "";
  const weekText = controls.week === "week" ? `-week-${week}` : controls.week === "through-week" ? `-through-week-${week}` : "";
  return `${EXPORT_PREFIX}-${kind}${metricText}${sideText}-${season}${weekText}.png`;
}

export function conferenceLabel(conference: string | null): string {
  return conference ?? "Independent";
}

// ---------------------------------------------------------------------------
// Scatter axes, per kind / side / metric
// ---------------------------------------------------------------------------

export type Corners = {
  topLeft: string;
  topRight: string;
  bottomLeft: string;
  bottomRight: string;
};

/** Each quadrant's precise meaning, plus a short name for the kind of team that lands there. */
export type CornerCaptions = Corners & { names: Corners };

const OFFENSE_QUADRANTS: Corners = {
  topLeft: "Boom or bust",
  topRight: "Efficient and explosive",
  bottomLeft: "Struggling",
  bottomRight: "Methodical",
};
const DEFENSE_QUADRANTS: Corners = {
  topLeft: "Bend, don't break",
  topRight: "Shutdown",
  bottomLeft: "Struggling",
  bottomRight: "Big-play risk",
};
const TEAM_QUADRANTS: Corners = {
  topLeft: "Defense-led",
  topRight: "Complete",
  bottomLeft: "Struggling",
  bottomRight: "Offense-led",
};

export type ScatterConfig = {
  xLabel: string;
  yLabel: string;
  /** Y title on phones, where the rotated full title would not fit the plot height. */
  shortYLabel: string;
  /** Axis tick text. */
  tickX: (value: number) => string;
  tickY: (value: number) => string;
  /** Short metric name shown in the export subtitle; empty when the chart has one metric. */
  metricLabel: string;
  captions: CornerCaptions;
  /** Names of the two dashed average lines ("Avg offense"), printed with their values. */
  averageNames: { x: string; y: string };
  footnote: string;
};

/** Percent tick: whole when the tick is a whole percent, else one decimal (`7.5%`), so ticks never repeat. */
export function percentTick(value: number): string {
  const tenths = Math.round(value * 1000);
  return tenths % 10 === 0 ? `${tenths / 10}%` : `${(tenths / 10).toFixed(1)}%`;
}

function efficiencyFootnote(metric: string, definition: string): string {
  return `Cumulative success rate and ${metric} on eligible plays (regulation only; garbage time and special teams excluded), FBS vs FBS games. ${SUCCESS_RATE_DEFINITION} ${definition} Dashed lines are play-weighted FBS averages; quadrant names are relative to them. On defense, axes are inverted so up and right is better.`;
}

type EfficiencyMetricText = {
  /** Toggle button and export subtitle. */
  label: string;
  yLabel: Record<Side, string>;
  /** Phone y title. */
  shortYLabel: Record<Side, string>;
  /** Corner caption term. */
  caption: string;
  /** Footnote term. */
  footnote: string;
  /** Tooltip term. */
  describe: string;
  /** One sentence defining the y-axis metric, printed under the chart title. */
  definition: string;
  tick: (value: number) => string;
  value: (value: number) => string;
};

export const EFFICIENCY_METRICS: Record<EfficiencyMetric, EfficiencyMetricText> = {
  ppa: {
    label: "PPA/play",
    yLabel: { offense: "PPA/play", defense: "PPA/play" },
    shortYLabel: { offense: "PPA/play", defense: "Def PPA/play allowed" },
    caption: "PPA",
    footnote: "PPA/play",
    describe: "PPA/play",
    definition: PPA_DEFINITION,
    tick: formatEpa,
    value: formatEpa,
  },
  explosive_rate: {
    label: "20+ Yard Rate",
    yLabel: { offense: "20+ Yard Play Rate", defense: "20+ Yard Play Rate Allowed" },
    shortYLabel: { offense: "20+ yard rate", defense: "20+ yard rate allowed" },
    caption: "20+ rate",
    footnote: "20+ yard play rate",
    describe: "20+ yard rate",
    definition: EXPLOSIVE_DEFINITION,
    tick: percentTick,
    value: formatPercent,
  },
  yards_per_success: {
    label: "Yards / Success",
    yLabel: { offense: "Yards / Successful Play", defense: "Yards / Success Allowed" },
    shortYLabel: { offense: "Yds / success", defense: "Yds / success allowed" },
    caption: "yards/success",
    footnote: "yards per successful play",
    describe: "yards/success",
    definition: "Yards per successful play is the average yardage on plays that count as successful.",
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
        names: DEFENSE_QUADRANTS,
      }
    : {
        topLeft: `Lower success / Higher ${m}`,
        topRight: `Higher success / Higher ${m}`,
        bottomLeft: `Lower success / Lower ${m}`,
        bottomRight: `Higher success / Lower ${m}`,
        names: OFFENSE_QUADRANTS,
      };
  return {
    xLabel: "Success Rate",
    yLabel: text.yLabel[side],
    shortYLabel: text.shortYLabel[side],
    tickX: percentTick,
    tickY: text.tick,
    metricLabel: text.label,
    captions,
    averageNames: {
      x: side === "defense" ? "Avg success allowed" : "Avg success rate",
      y: `Avg ${text.caption}${side === "defense" ? " allowed" : ""}`,
    },
    footnote: efficiencyFootnote(text.footnote, text.definition),
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
  shortYLabel: "Def PPA/play allowed",
  tickX: formatEpaTick,
  tickY: formatEpaTick,
  metricLabel: "",
  averageNames: { x: "Avg offense", y: "Avg defense allowed" },
  captions: {
    topLeft: "Lower offense / Better defense",
    topRight: "Better offense / Better defense",
    bottomLeft: "Lower offense / Higher defense allowed",
    bottomRight: "Better offense / Higher defense allowed",
    names: TEAM_QUADRANTS,
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
// Possession efficiency
// ---------------------------------------------------------------------------

function possessionFootnote(measurement: string): string {
  return `Adjusted ${measurement}: opponent-adjusted V5 possession measurements of FBS teams for each Through Week window, every game counted (FCS opponents included, as in the V5 ratings). Defense is the value allowed, axis inverted so up and right is better. Dashed lines are possession-weighted averages over the plotted teams; quadrant names are relative to them. Teams missing either role are not plotted. From this release's V5 possession measurements.`;
}

export const POSSESSION_METRICS: Record<PossessionMetric, {
  /** Toggle button and export subtitle. */
  label: string;
  /** Axis and tooltip unit. */
  unit: string;
  /** PNG filename term. */
  slug: string;
  tick: (value: number) => string;
  value: (value: number) => string;
}> = {
  ppp: { label: "Points", unit: "points per possession", slug: "ppp", tick: (value) => value.toFixed(2), value: (value) => value.toFixed(2) },
  // The site says PPA, as everywhere else; `epa_per_possession` stays the stored measurement id.
  epa_per_possession: { label: "PPA", unit: "PPA per possession", slug: "ppa-per-possession", tick: formatEpaTick, value: formatEpaTick },
};

/** Scatter axis text of the possession chart for `metric`. */
export function possessionConfig(metric: PossessionMetric): ScatterConfig {
  const text = POSSESSION_METRICS[metric];
  return {
    xLabel: `Adjusted offense ${text.unit}`,
    yLabel: `Adjusted defense ${text.unit} allowed`,
    shortYLabel: metric === "ppp" ? "Def pts/poss allowed" : "Def PPA/poss allowed",
    tickX: text.tick,
    tickY: text.tick,
    metricLabel: text.unit.charAt(0).toUpperCase() + text.unit.slice(1),
    averageNames: { x: "Avg offense", y: "Avg defense allowed" },
    captions: {
      topLeft: "Lower offense / Better defense",
      topRight: "Better offense / Better defense",
      bottomLeft: "Lower offense / Higher defense allowed",
      bottomRight: "Better offense / Higher defense allowed",
      names: TEAM_QUADRANTS,
    },
    footnote: possessionFootnote(text.unit),
  };
}

/** Tooltip text of one possession point: raw, adjusted, opponent adjustment, games and both ranks. */
export function describePossessionPoint(point: ScatterPoint, scatter: Pick<PossessionScatter, "roles" | "ranks" | "points">, metric: PossessionMetric): string {
  const { unit, value } = POSSESSION_METRICS[metric];
  const text = (v: number | null) => (v === null ? "n/a" : value(v));
  const head = `${point.team} (${conferenceLabel(point.conference)})`;
  const role = scatter.roles[point.team];
  const rank = scatter.ranks[point.team];
  if (!role || !rank) return `${head}: adjusted offense ${value(point.x)}, adjusted defense allowed ${value(point.y)} ${unit}`;
  const describe = (name: string, row: PossessionRow, r: number) =>
    `${name} adjusted ${text(row.adjustedValue)} (raw ${text(row.rawValue)}, opponent adjustment ${text(row.opponentAdjustment)}, ${row.games} games), ${rankText(r, scatter.points.length)}`;
  return `${head}, ${unit}: ${describe("offense", role.offense, rank.offense)}; ${describe("defense allowed", role.defense, rank.defense)}`;
}

// ---------------------------------------------------------------------------
// V5 rating trajectory
// ---------------------------------------------------------------------------

/** Two-decimal rating (`1.23`, `-0.40`); ratings are not centered at zero, so no `+`. */
export function formatRating(value: number): string {
  return value.toFixed(2);
}

/** Tooltip text of one team-week: rating ± one standard deviation and the weekly rank. */
export function describeRatingPoint(data: RatingTrajectoryData, series: RatingTrajectorySeries, index: number, metric: RatingMetric): string {
  const head = `${series.team} (${conferenceLabel(series.conference)}), Through Week ${data.weeks[index]}`;
  const value = series.values[index];
  if (value === null) return `${head}: no ${RATING_METRICS[metric].yLabel}`;
  const sd = series.sd[index];
  const spread = sd === null ? "" : ` ± ${formatRating(sd)}`;
  const rank = series.ranks[index];
  return `${head}: ${RATING_METRICS[metric].yLabel} ${formatRating(value)}${spread}${rank === null ? "" : `, ${rankText(rank, data.ranked[index])}`}`;
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

/** The game log footnote for `metric`: the shared note, then what that metric means. */
export function gameLogFootnote(metric: GameLogMetric): string {
  const definition = metric === "success" ? SUCCESS_RATE_DEFINITION : metric === "ppa" ? PPA_DEFINITION : EXPLOSIVE_DEFINITION;
  return `${GAME_LOG_NOTE} ${definition}`;
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

// ---------------------------------------------------------------------------
// Situational downs, Finishing drives, Resume quality, and Market board
// ---------------------------------------------------------------------------

export function downsFootnote(): string {
  return "Cumulative early down EPA/play (1st & 2nd down) and 3rd/4th down conversion rate on eligible plays, regulation play only, FBS vs FBS games. On defense, axes are inverted so up and right is better. Dashed lines are play-weighted FBS averages.";
}

export function downsConfig(side: Side): ScatterConfig {
  const isOffense = side === "offense";
  return {
    xLabel: isOffense ? "Early Down PPA/play (1st & 2nd)" : "Early Down PPA/play Allowed",
    yLabel: isOffense ? "3rd & 4th Down Conv. Rate" : "3rd & 4th Down Conv. Rate Allowed",
    shortYLabel: isOffense ? "3rd/4th Conv Rate" : "3rd/4th Conv Allowed",
    tickX: formatEpaTick,
    tickY: percentTick,
    metricLabel: "",
    captions: isOffense
      ? {
          topLeft: "Lower early EPA / Higher conversion",
          topRight: "Higher early EPA / Higher conversion",
          bottomLeft: "Lower early EPA / Lower conversion",
          bottomRight: "Higher early EPA / Lower conversion",
          names: {
            topLeft: "Late-Down Bailouts",
            topRight: "Unstoppable Engine",
            bottomLeft: "Struggling",
            bottomRight: "On-Schedule Only",
          },
        }
      : {
          topLeft: "Higher early EPA allowed / Lower conversion allowed",
          topRight: "Lower early EPA allowed / Lower conversion allowed",
          bottomLeft: "Higher early EPA allowed / Higher conversion allowed",
          bottomRight: "Lower early EPA allowed / Higher conversion allowed",
          names: {
            topLeft: "Bend, Don't Break",
            topRight: "Suffocating Defense",
            bottomLeft: "Vulnerable",
            bottomRight: "Stingy Early, Leaky Late",
          },
        },
    averageNames: {
      x: isOffense ? "Avg early EPA" : "Avg early EPA allowed",
      y: isOffense ? "Avg conv rate" : "Avg conv rate allowed",
    },
    footnote: downsFootnote(),
  };
}

export function describeDownsPoint(point: ScatterPoint, side: Side): string {
  const head = `${point.team} (${conferenceLabel(point.conference)})`;
  const isOffense = side === "offense";
  return `${head}: ${isOffense ? "Early-down EPA" : "Early-down EPA allowed"} ${formatEpa(point.x)}, ${isOffense ? "3rd/4th down conv" : "3rd/4th conv allowed"} ${formatPercent(point.y)}`;
}

export function finishingDrivesFootnote(): string {
  return "Scoring opportunity rate (Eckel rate: share of drives reaching the opponent 40-yard line) against points scored per scoring opportunity, FBS vs FBS games. On defense, axes are inverted so up and right is better. Dashed lines are drive-weighted FBS averages.";
}

export function finishingDrivesConfig(side: Side): ScatterConfig {
  const isOffense = side === "offense";
  return {
    xLabel: isOffense ? "Scoring Opportunity Rate (Drives to Opponent 40)" : "Scoring Opportunity Rate Allowed",
    yLabel: isOffense ? "Points per Scoring Opportunity" : "Points Allowed per Scoring Opportunity",
    shortYLabel: isOffense ? "Points per Scoring Opportunity" : "Points Allowed per Scoring Opportunity",
    tickX: percentTick,
    tickY: (v) => v.toFixed(2),
    metricLabel: "",
    captions: isOffense
      ? {
          topLeft: "Lower opportunity rate / Higher points per opportunity",
          topRight: "Higher opportunity rate / Higher points per opportunity",
          bottomLeft: "Lower opportunity rate / Lower points per opportunity",
          bottomRight: "Higher opportunity rate / Lower points per opportunity",
          names: {
            topLeft: "Low Volume, High TD Rate",
            topRight: "Elite Finishers",
            bottomLeft: "Struggling Finishers",
            bottomRight: "Drive Stallers / FG Settlers",
          },
        }
      : {
          topLeft: "Higher opportunity rate allowed / Fewer points allowed per opportunity",
          topRight: "Lower opportunity rate allowed / Fewer points allowed per opportunity",
          bottomLeft: "Higher opportunity rate allowed / More points allowed per opportunity",
          bottomRight: "Lower opportunity rate allowed / More points allowed per opportunity",
          names: {
            topLeft: "Red-Zone Wall",
            topRight: "Lockdown Defense",
            bottomLeft: "Generous Defense",
            bottomRight: "Stingy Early, Leaky Inside",
          },
        },
    averageNames: {
      x: "Avg opp rate",
      y: "Avg pts/opp",
    },
    footnote: finishingDrivesFootnote(),
  };
}

export function describeFinishingDrivesPoint(point: ScatterPoint, side: Side): string {
  const head = `${point.team} (${conferenceLabel(point.conference)})`;
  const isOffense = side === "offense";
  return `${head}: ${isOffense ? "Scoring opportunity rate" : "Scoring opportunity rate allowed"} ${formatPercent(point.x)}, ${isOffense ? "points per scoring opportunity" : "points allowed per scoring opportunity"} ${point.y.toFixed(2)}`;
}

export function resumeQualityFootnote(): string {
  return "V5 model rating dominance (points per possession above average) against Strength of Record (SOR) Rank (where #1 is the national best). Up and right is better. Dashed lines are FBS averages.";
}

export const RESUME_QUALITY_CONFIG: ScatterConfig = {
  xLabel: "V5 Overall Rating (Points Above Average)",
  yLabel: "Strength of Record (SOR) Rank",
  shortYLabel: "SOR Rank",
  tickX: (v) => (v >= 0 ? `+${v.toFixed(1)}` : v.toFixed(1)),
  tickY: (v) => `#${Math.round(v)}`,
  metricLabel: "",
  captions: {
    topLeft: "Lower rating / Top resume rank",
    topRight: "Championship Contenders",
    bottomLeft: "Rebuilding",
    bottomRight: "Unlucky / Untested Giants",
    names: {
      topLeft: "Resume Overachievers",
      topRight: "Championship Contenders",
      bottomLeft: "Rebuilding",
      bottomRight: "Unlucky / Untested Giants",
    },
  },
  averageNames: {
    x: "Avg rating",
    y: "Avg SOR rank",
  },
  footnote: resumeQualityFootnote(),
};

export function describeResumePoint(point: ScatterPoint): string {
  const head = `${point.team} (${conferenceLabel(point.conference)})`;
  const ratingStr = point.x >= 0 ? `+${point.x.toFixed(2)}` : point.x.toFixed(2);
  return `${head}: V5 Rating ${ratingStr}, Strength of Record #${Math.round(point.y)}`;
}

export function marketBoardFootnote(): string {
  return "Weekly market betting consensus against V5 model predictions. The diagonal dashed line represents the consensus line (market = model). Dots highlighted with an edge badge indicate actionable edges of 3.0 or more points.";
}

export function parseMarketBoardMetric(raw: RawParam): MarketBoardMetric {
  return raw === "total" ? "total" : "spread";
}
