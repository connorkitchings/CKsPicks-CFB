import { teamAbbr } from "./team-logos.ts";
import { homeSpreadFromMargin } from "./betting-format.ts";
export {
  P4_CONFERENCES,
  P4_INDEPENDENTS,
  buildConferenceMap,
  conferenceOptions,
  isP4,
  matchesConference,
  matchesTeamConference,
  type ConferenceFilter,
  type RosterRow,
} from "./conferences.ts";
import { matchesConference, type ConferenceFilter, type RosterRow } from "./conferences.ts";

/**
 * Pure transforms for the weekly team charts. Inputs are the rows of the release's
 * `team_season_roster`, `team_game_stats`, `team_adjusted_epa`, (for `charts_v2`)
 * `team_game_yardage`, and the core `v5_rating_snapshots` and `team_possession_adjusted`
 * projections; nothing
 * here reads a database. Everything is a descriptive reconstruction from the release's
 * data, windowed by week only.
 */

export type ChartKind =
  | "net-success"
  | "efficiency"
  | "adjusted"
  | "rating-trajectory"
  | "possession"
  | "game-log"
  | "downs"
  | "finishing-drives"
  | "resume-quality"
  | "market-board";
export type Side = "offense" | "defense";
export type EfficiencyMetric = "ppa" | "explosive_rate" | "yards_per_success";


export type TeamGameRow = {
  week: number;
  gameId: number;
  team: string;
  opponent: string;
  site: "home" | "away" | "neutral";
  pointsFor: number;
  pointsAgainst: number;
  offPlays: number;
  offSuccessN: number;
  offSuccessSum: number;
  offEpaN: number;
  offEpaSum: number;
  defPlays: number;
  defSuccessN: number;
  defSuccessSum: number;
  defEpaN: number;
  defEpaSum: number;
} & Partial<Omit<TeamGameYardageRow, "gameId" | "team">>;

/** Yardage counts of one team-game (`team_game_yardage`, `charts_v2` releases only). */
export type TeamGameYardageRow = {
  gameId: number;
  team: string;
  /** Eligible plays with finite yardage. */
  offYardsN: number;
  /** Of those, plays gaining 20 or more yards. */
  offExplosiveN: number;
  /** Successful plays with finite yardage, and their yards. */
  offSuccessYardsN: number;
  offSuccessYardsSum: number;
  defYardsN: number;
  defExplosiveN: number;
  defSuccessYardsN: number;
  defSuccessYardsSum: number;
};

/**
 * Join yardage onto team-game rows by `(gameId, team)`. The release guarantees the two
 * projections share one key set, so any missing or extra key is a data error.
 */
export function withYardage(rows: readonly TeamGameRow[], yardage: readonly TeamGameYardageRow[]): TeamGameRow[] {
  const key = (gameId: number, team: string) => `${gameId}:${team}`;
  const byKey = new Map(yardage.map((entry) => [key(entry.gameId, entry.team), entry]));
  if (byKey.size !== yardage.length || byKey.size !== rows.length) throw new Error("team_game_yardage keys differ from team_game_stats");
  return rows.map((row) => {
    const entry = byKey.get(key(row.gameId, row.team));
    if (!entry) throw new Error("team_game_yardage keys differ from team_game_stats");
    return { ...row, ...entry };
  });
}

export type AdjustedRow = {
  asOfWeek: number;
  team: string;
  role: Side;
  rawEpaPerPlay: number;
  venueCorrection: number;
  opponentAdjustment: number;
  adjustedEpaPerPlay: number;
  epaN: number;
  games: number;
  adjustedRank: number;
  cohortSize: number;
};

export const FIRST_SCATTER_THROUGH_WEEK = 2;

// ---------------------------------------------------------------------------
// Weeks
// ---------------------------------------------------------------------------

/** Weeks (0-based) with at least one charted game, ascending. */
export function netSuccessWeeks(rows: readonly TeamGameRow[]): number[] {
  return [...new Set(rows.map((row) => row.week))].sort((a, b) => a - b);
}

/** "Through Week N" values offered for the cumulative efficiency scatter. */
export function efficiencyThroughWeeks(rows: readonly TeamGameRow[]): number[] {
  const weeks = netSuccessWeeks(rows);
  const last = weeks.length ? weeks[weeks.length - 1] : -1;
  const through: number[] = [];
  for (let week = FIRST_SCATTER_THROUGH_WEEK; week <= last; week++) through.push(week);
  return through;
}

/** "Through Week N" values of the adjusted scatter, from the stored `as_of_week` windows. */
export function adjustedThroughWeeks(asOfWeeks: readonly number[]): number[] {
  return [...new Set(asOfWeeks)]
    .map((asOf) => asOf - 1)
    .filter((through) => through >= FIRST_SCATTER_THROUGH_WEEK)
    .sort((a, b) => a - b);
}

/**
 * The week to show when `requested` may not exist for the selected chart (for example
 * after switching from net-success Week 0 to the efficiency scatter): the nearest
 * available week (the later one on a tie), or the latest when nothing valid was requested.
 */
export function coerceWeek(requested: number | null | undefined, available: readonly number[]): number | null {
  if (!available.length) return null;
  const latest = available[available.length - 1];
  if (requested === null || requested === undefined || !Number.isInteger(requested)) return latest;
  if (available.includes(requested)) return requested;
  return available.reduce((best, week) => {
    const gap = Math.abs(week - requested);
    const bestGap = Math.abs(best - requested);
    return gap < bestGap || (gap === bestGap && week > best) ? week : best;
  });
}

// ---------------------------------------------------------------------------
// Net success rate bars
// ---------------------------------------------------------------------------

export type NetSuccessBar = {
  gameId: number;
  winner: string;
  loser: string;
  winnerPoints: number;
  loserPoints: number;
  winnerSuccessRate: number;
  loserSuccessRate: number;
  /** Winner offensive success rate minus loser offensive success rate. */
  value: number;
  /** Axis label: winner abbreviation and final score, e.g. `UGA 31-10`. */
  label: string;
};
export type NotCharted = { gameId: number; reason: string };

function successRate(n: number, sum: number): number | null {
  return n > 0 ? sum / n : null;
}

/**
 * One bar per game of `week`. Winner = higher points; equal points and games where either
 * offense has no valid success observation are listed as not charted. Sorted by value
 * ascending, then game id.
 */
export function netSuccessBars(
  rows: readonly TeamGameRow[],
  week: number,
): { bars: NetSuccessBar[]; notCharted: NotCharted[] } {
  const games = new Map<number, TeamGameRow[]>();
  for (const row of rows) {
    if (row.week !== week) continue;
    games.set(row.gameId, [...(games.get(row.gameId) ?? []), row]);
  }
  const bars: NetSuccessBar[] = [];
  const notCharted: NotCharted[] = [];
  for (const [gameId, pair] of [...games].sort((a, b) => a[0] - b[0])) {
    if (pair.length !== 2) {
      notCharted.push({ gameId, reason: "incomplete game rows" });
      continue;
    }
    const [a, b] = pair;
    if (a.pointsFor === b.pointsFor) {
      notCharted.push({ gameId, reason: "tied points" });
      continue;
    }
    const [winner, loser] = a.pointsFor > b.pointsFor ? [a, b] : [b, a];
    const winnerRate = successRate(winner.offSuccessN, winner.offSuccessSum);
    const loserRate = successRate(loser.offSuccessN, loser.offSuccessSum);
    if (winnerRate === null || loserRate === null) {
      notCharted.push({ gameId, reason: "success rate unavailable" });
      continue;
    }
    bars.push({
      gameId,
      winner: winner.team,
      loser: loser.team,
      winnerPoints: winner.pointsFor,
      loserPoints: loser.pointsFor,
      winnerSuccessRate: winnerRate,
      loserSuccessRate: loserRate,
      value: winnerRate - loserRate,
      label: `${teamAbbr(winner.team)} ${winner.pointsFor}-${loser.pointsFor}`,
    });
  }
  return { bars: sortNetSuccessBars(bars, "gap"), notCharted };
}

/** "gap": success-rate gap ascending; "margin": final scoreboard margin ascending. Ties by game id. */
export type NetSuccessSort = "gap" | "margin";

export function sortNetSuccessBars(bars: readonly NetSuccessBar[], sort: NetSuccessSort): NetSuccessBar[] {
  const key = (bar: NetSuccessBar) => (sort === "gap" ? bar.value : bar.winnerPoints - bar.loserPoints);
  return [...bars].sort((a, b) => key(a) - key(b) || a.gameId - b.gameId);
}

/** Winners whose offense had the strictly lower success rate, out of the charted games. */
export function outplayedWinners(bars: readonly NetSuccessBar[]): { outplayed: number; total: number } {
  return { outplayed: bars.filter((bar) => bar.value < 0).length, total: bars.length };
}

// ---------------------------------------------------------------------------
// Scatter points
// ---------------------------------------------------------------------------

export type ScatterPoint = {
  team: string;
  conference: string | null;
  x: number;
  y: number;
  /** Plays behind the point (eligible PPA observations). */
  n: number;
};
export type ScatterData = {
  points: ScatterPoint[];
  /** FBS averages (dashed lines). */
  average: { x: number; y: number } | null;
  /** Roster teams that could not be plotted (no eligible games or no valid observation). */
  unavailable: string[];
  /** Defense axes are inverted so that good is up and to the right. */
  invertX: boolean;
  invertY: boolean;
};

function byTeam<T extends { team: string }>(a: T, b: T): number {
  return a.team < b.team ? -1 : a.team > b.team ? 1 : 0;
}

/**
 * Cumulative success rate (x) against `metric` (y: PPA/play, 20+ yard rate or
 * yards/success) through `throughWeek`, FBS roster teams only, from the release's window
 * sums. Averages are pooled over all plays of roster teams in the window, so teams with
 * more plays weigh more. Teams with no eligible games or a null metric are listed as
 * unavailable. The explosiveness metrics need rows joined with `withYardage`.
 */
export function efficiencyPoints(
  roster: readonly RosterRow[],
  rows: readonly TeamGameRow[],
  throughWeek: number,
  side: Side,
  metric: EfficiencyMetric = "ppa",
): ScatterData {
  const sums = new Map<string, WindowSums>();
  const rosterNames = new Set(roster.map((r) => r.team));
  for (const row of rows) {
    if (row.week > throughWeek || !rosterNames.has(row.team)) continue;
    const acc = sums.get(row.team) ?? emptySums();
    addSums(acc, sideTerms(row, side, metric));
    sums.set(row.team, acc);
  }
  const points: ScatterPoint[] = [];
  const unavailable: string[] = [];
  const pooled = emptySums();
  for (const { team, conference } of roster) {
    const acc = sums.get(team);
    if (acc) addSums(pooled, acc);
    // A zero denominator is a missing observation, never zero.
    if (!acc || acc.successN === 0 || acc.yDen === 0) {
      unavailable.push(team);
      continue;
    }
    points.push({ team, conference, x: acc.successSum / acc.successN, y: acc.yNum / acc.yDen, n: acc.n });
  }
  points.sort(byTeam);
  unavailable.sort();
  const average = pooled.successN > 0 && pooled.yDen > 0
    ? { x: pooled.successSum / pooled.successN, y: pooled.yNum / pooled.yDen }
    : null;
  return { points, average, unavailable, invertX: side === "defense", invertY: side === "defense" };
}

/** Window sums behind one efficiency point: success rate and the y metric's ratio. */
type WindowSums = { successN: number; successSum: number; yNum: number; yDen: number; n: number };
const emptySums = (): WindowSums => ({ successN: 0, successSum: 0, yNum: 0, yDen: 0, n: 0 });
function addSums(into: WindowSums, from: WindowSums) {
  into.successN += from.successN;
  into.successSum += from.successSum;
  into.yNum += from.yNum;
  into.yDen += from.yDen;
  into.n += from.n;
}

/**
 * One team-game side's terms. PPA/play is `epa_sum / epa_n` over `epa_n` plays; 20+ rate
 * is `explosive_n / yards_n` and yards/success `success_yards_sum / success_yards_n`, both
 * over `yards_n` plays. A row without yardage (a `charts_v1` release) has no exposure.
 */
function sideTerms(row: TeamGameRow, side: Side, metric: EfficiencyMetric): WindowSums {
  const off = side === "offense";
  const successN = off ? row.offSuccessN : row.defSuccessN;
  const successSum = off ? row.offSuccessSum : row.defSuccessSum;
  if (metric === "ppa") {
    const epaN = off ? row.offEpaN : row.defEpaN;
    return { successN, successSum, yNum: off ? row.offEpaSum : row.defEpaSum, yDen: epaN, n: epaN };
  }
  const yardsN = (off ? row.offYardsN : row.defYardsN) ?? 0;
  const [yNum, yDen] = metric === "explosive_rate"
    ? [off ? row.offExplosiveN : row.defExplosiveN, yardsN]
    : [off ? row.offSuccessYardsSum : row.defSuccessYardsSum, off ? row.offSuccessYardsN : row.defSuccessYardsN];
  return { successN, successSum, yNum: yNum ?? 0, yDen: yDen ?? 0, n: yardsN };
}

/** Points carry offense on x and defense allowed on y. */
export type AdjustedScatter = ScatterData & {
  /** The stored decomposition behind each plotted team, by role. */
  roles: Record<string, { offense: AdjustedRow; defense: AdjustedRow }>;
};

/**
 * Opponent-adjusted offense (x) against adjusted defense allowed (y, inverted) for one
 * `as_of_week` window. A point needs both an adjusted offense and defense row; averages
 * are play-weighted over plotted teams.
 */
export function adjustedPoints(roster: readonly RosterRow[], rows: readonly AdjustedRow[]): AdjustedScatter {
  return roleScatter(roster, rows, (row) => row.adjustedEpaPerPlay, (row) => row.epaN);
}

/**
 * Offense (x) against defense allowed (y, inverted) for roster teams with both roles.
 * `n` is the two roles' summed weight; averages are weighted per role over plotted teams
 * and null when either role has no weight.
 */
function roleScatter<R extends { team: string; role: Side }>(
  roster: readonly RosterRow[],
  rows: readonly R[],
  value: (row: R) => number,
  weight: (row: R) => number,
): ScatterData & { roles: Record<string, { offense: R; defense: R }> } {
  const offense = new Map<string, R>();
  const defense = new Map<string, R>();
  for (const row of rows) (row.role === "offense" ? offense : defense).set(row.team, row);
  const points: ScatterPoint[] = [];
  const unavailable: string[] = [];
  const roles: Record<string, { offense: R; defense: R }> = {};
  let ox = 0;
  let oy = 0;
  let on = 0;
  let dn = 0;
  for (const { team, conference } of roster) {
    const o = offense.get(team);
    const d = defense.get(team);
    if (!o || !d) {
      unavailable.push(team);
      continue;
    }
    points.push({ team, conference, x: value(o), y: value(d), n: weight(o) + weight(d) });
    roles[team] = { offense: o, defense: d };
    ox += value(o) * weight(o);
    on += weight(o);
    oy += value(d) * weight(d);
    dn += weight(d);
  }
  points.sort(byTeam);
  unavailable.sort();
  const average = on > 0 && dn > 0 ? { x: ox / on, y: oy / dn } : null;
  return {
    points,
    average,
    unavailable,
    invertX: false,
    invertY: true,
    roles,
  };
}

// ---------------------------------------------------------------------------
// Possession efficiency
// ---------------------------------------------------------------------------

/** Points per possession, or PPA per possession (stored under the measurement id `epa_per_possession`). */
export type PossessionMetric = "ppp" | "epa_per_possession";

/** One `team_possession_adjusted` row (one window, team, role and measurement). */
export type PossessionRow = {
  asOfWeek: number;
  team: string;
  role: Side;
  measurementId: PossessionMetric;
  rawValue: number | null;
  /** Opponent-adjusted value; for defense, the value allowed. Null means no adjusted value. */
  adjustedValue: number | null;
  opponentAdjustment: number | null;
  adjustedRank: number | null;
  cohortSize: number | null;
  /** Possessions behind the value; the pooled-average weight. */
  primaryExposure: number | null;
  games: number;
};

/** Points carry adjusted offense on x and adjusted defense allowed on y. */
export type PossessionScatter = ScatterData & {
  /** The stored rows behind each plotted team, by role. */
  roles: Record<string, { offense: PossessionRow; defense: PossessionRow }>;
  /**
   * Competition ranks among the plotted teams (offense higher first, defense allowed
   * lower first; ties share a rank, 1, 1, 3). They equal the stored `adjusted_rank`
   * whenever every ranked team is plotted, and are recomputed for the plotted population
   * when some team lacks a role.
   */
  ranks: Record<string, { offense: number; defense: number }>;
};

/**
 * Opponent-adjusted offense (x) against adjusted defense allowed (y, inverted so up and
 * right is better) of `metric` for one `as_of_week` window. A roster team needs both roles
 * with an adjusted value; the rest are `unavailable`. Pooled averages are weighted by
 * `primary_exposure` (possessions) per role over the plotted teams; a missing exposure
 * weighs zero, and `n` is the team's summed possessions.
 */
export function possessionPoints(roster: readonly RosterRow[], rows: readonly PossessionRow[], metric: PossessionMetric): PossessionScatter {
  const usable = rows.filter((row) => row.measurementId === metric && row.adjustedValue !== null);
  const scatter = roleScatter(roster, usable, (row) => row.adjustedValue!, (row) => row.primaryExposure ?? 0);
  const ranks: PossessionScatter["ranks"] = {};
  for (const [team, rank] of scatterRanks(scatter)) ranks[team] = { offense: rank.x, defense: rank.y };
  return { ...scatter, ranks };
}

export type Domain = [number, number];

// ---------------------------------------------------------------------------
// Trajectory series (shared by the V5 rating trajectory)
// ---------------------------------------------------------------------------

export type TrajectoryPoint = { week: number; value: number };
export type TrajectorySeries = {
  team: string;
  conference: string | null;
  /** One value per `TrajectoryData.weeks` entry; null where the team lacks the window. */
  values: (number | null)[];
  /** Runs of consecutive windows with a value; a one-point run is drawn as a dot. */
  segments: TrajectoryPoint[][];
};
export type TrajectoryData = {
  /** "Through Week N" of every charted window, ascending. */
  weeks: number[];
  /** Roster teams with a value in at least one window, by name. */
  series: TrajectorySeries[];
  /** Dashed reference of each window, null when none: the unweighted roster mean for V5 ratings. */
  average: (number | null)[];
  /** Roster teams with no value in any window. */
  unavailable: string[];
  /** Defense allowed is inverted so that up is better. */
  invertY: boolean;
};

/** Runs of consecutive non-null values; gaps are never interpolated. */
function trajectorySegments(weeks: readonly number[], values: readonly (number | null)[]): TrajectoryPoint[][] {
  const segments: TrajectoryPoint[][] = [];
  let run: TrajectoryPoint[] = [];
  values.forEach((value, index) => {
    if (value === null) {
      if (run.length) segments.push(run);
      run = [];
    } else run.push({ week: weeks[index], value });
  });
  if (run.length) segments.push(run);
  return segments;
}

// ---------------------------------------------------------------------------
// V5 rating trajectory
// ---------------------------------------------------------------------------

/** V5 model rating component; every one is higher-is-better (defense included). */
export type RatingMetric = "overall" | "offense" | "defense";

/** One `current`-class `v5_rating_snapshots` row: the rating after week `week`'s games. */
export type RatingSnapshotRow = {
  week: number;
  team: string;
  offenseRating: number;
  offenseVariance: number;
  defenseRating: number;
  defenseVariance: number;
  overallRating: number;
  overallVariance: number;
};

export type RatingTrajectorySeries = TrajectorySeries & {
  /** Standard deviation (`sqrt(variance)`) per week; null where the team has no snapshot. */
  sd: (number | null)[];
  /** Competition rank among roster teams with a snapshot that week (ties share a rank). */
  ranks: (number | null)[];
};

/** Assignable to `TrajectoryData`, so the trajectory chart draws it unchanged. */
export type RatingTrajectoryData = Omit<TrajectoryData, "series"> & {
  series: RatingTrajectorySeries[];
  /** Roster teams ranked in each week (the rank denominator). */
  ranked: number[];
};

const RATING_FIELDS = {
  overall: ["overallRating", "overallVariance"],
  offense: ["offenseRating", "offenseVariance"],
  defense: ["defenseRating", "defenseVariance"],
} as const satisfies Record<RatingMetric, readonly [keyof RatingSnapshotRow, keyof RatingSnapshotRow]>;

/**
 * `metric` of every roster team for each stored snapshot week (x = Through Week `week`),
 * ascending. A missing team-week is a gap, never interpolated. `average` is the weekly
 * unweighted mean over all roster teams with a snapshot (the ratings are not centered at
 * zero); like the ranks it ignores any group filter, which the view applies afterwards.
 * Every metric is higher-is-better, so `invertY` is false. Throws on a duplicate
 * team-week, which the release forbids.
 */
export function ratingTrajectorySeries(roster: readonly RosterRow[], rows: readonly RatingSnapshotRow[], metric: RatingMetric): RatingTrajectoryData {
  const [ratingKey, varianceKey] = RATING_FIELDS[metric];
  const rosterNames = new Set(roster.map((r) => r.team));
  const byKey = new Map<string, RatingSnapshotRow>();
  for (const row of rows) {
    if (!rosterNames.has(row.team)) continue;
    const key = `${row.week}:${row.team}`;
    if (byKey.has(key)) throw new Error(`v5_rating_snapshots has more than one current row for ${row.team} in week ${row.week}`);
    byKey.set(key, row);
  }
  const weeks = [...new Set([...byKey.values()].map((row) => row.week))].sort((a, b) => a - b);
  const columns = weeks.map((week) => {
    const present = roster.flatMap(({ team }) => {
      const row = byKey.get(`${week}:${team}`);
      return row ? [{ team, value: row[ratingKey] }] : [];
    });
    const average = present.length ? present.reduce((sum, entry) => sum + entry.value, 0) / present.length : null;
    return { average, ranks: competitionRanks(present, false), ranked: present.length };
  });
  const series: RatingTrajectorySeries[] = [];
  const unavailable: string[] = [];
  for (const { team, conference } of roster) {
    const snapshots = weeks.map((week) => byKey.get(`${week}:${team}`) ?? null);
    if (snapshots.every((row) => row === null)) {
      unavailable.push(team);
      continue;
    }
    const values = snapshots.map((row) => (row ? row[ratingKey] : null));
    series.push({
      team,
      conference,
      values,
      segments: trajectorySegments(weeks, values),
      sd: snapshots.map((row) => (row ? Math.sqrt(row[varianceKey]) : null)),
      ranks: columns.map((column) => column.ranks.get(team) ?? null),
    });
  }
  series.sort(byTeam);
  unavailable.sort();
  return {
    weeks,
    series,
    average: columns.map((column) => column.average),
    ranked: columns.map((column) => column.ranked),
    unavailable,
    invertY: false,
  };
}

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

/** Case-insensitive match on the team name or its abbreviation. */
export function matchesSearch(query: string, team: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return false;
  return team.toLowerCase().includes(q) || teamAbbr(team).toLowerCase() === q;
}

/** National per-axis competition ranks, computed from the full plotted population. */
export function scatterRanks(data: ScatterData): Map<string, { x: number; y: number }> {
  const x = competitionRanks(data.points.map((p) => ({ team: p.team, value: p.x })), data.invertX);
  const y = competitionRanks(data.points.map((p) => ({ team: p.team, value: p.y })), data.invertY);
  return new Map(data.points.map((point) => [point.team, { x: x.get(point.team)!, y: y.get(point.team)! }]));
}

/** Competition ranks, best first; ties share the minimum rank (1, 1, 3). */
function competitionRanks(entries: readonly { team: string; value: number }[], lowerBetter: boolean): Map<string, number> {
  const sorted = [...entries].sort((a, b) => (lowerBetter ? a.value - b.value : b.value - a.value));
  const ranks = new Map<string, number>();
  let rank = 1;
  sorted.forEach((entry, index) => {
    if (index === 0 || entry.value !== sorted[index - 1].value) rank = index + 1;
    ranks.set(entry.team, rank);
  });
  return ranks;
}

/** Filter actual rows; a game qualifies when either participant belongs to the group. */
export function filterNetSuccessBars(bars: readonly NetSuccessBar[], roster: readonly RosterRow[], filter: ConferenceFilter): NetSuccessBar[] {
  const conferences = new Map(roster.map((row) => [row.team, row.conference]));
  return bars.filter((bar) => matchesConference(filter, bar.winner, conferences.get(bar.winner) ?? null) || matchesConference(filter, bar.loser, conferences.get(bar.loser) ?? null));
}

// ---------------------------------------------------------------------------
// Team game log
// ---------------------------------------------------------------------------

export type GameLogMetric = "success" | "ppa" | "explosive_rate";

export type GameLogGame = {
  gameId: number;
  week: number;
  opponent: string;
  site: TeamGameRow["site"];
  pointsFor: number;
  pointsAgainst: number;
  /** `W 31-10` / `L 10-31` (`T` on equal points), the team's score first. */
  result: string;
  /** The team's value per side; null when the metric's denominator is zero ("n/a"). */
  offense: number | null;
  defense: number | null;
  /** FBS average of the game's week, pooled over every FBS team-game of that week. */
  average: Record<Side, number | null>;
};

/** A season-to-date value with its national competition rank among `ranked` roster teams. */
export type GameLogSeason = { value: number | null; rank: number | null; ranked: number; /** Pooled FBS average of the same window, for reference. */ average: number | null };

export type TeamGameLog = {
  team: string;
  metric: GameLogMetric;
  /** Every team-game of the team, by week then game id. */
  games: GameLogGame[];
  /** The latest charted week of the release, or null when nothing is charted. */
  throughWeek: number | null;
  season: Record<Side, GameLogSeason>;
};

/** Numerator and denominator of one team-game side for a game-log metric. */
function gameLogTerms(row: TeamGameRow, side: Side, metric: GameLogMetric): [number, number] {
  if (metric === "success") return side === "offense" ? [row.offSuccessSum, row.offSuccessN] : [row.defSuccessSum, row.defSuccessN];
  const terms = sideTerms(row, side, metric);
  return [terms.yNum, terms.yDen];
}

const ratioOrNull = ([num, den]: [number, number]): number | null => (den > 0 ? num / den : null);

/**
 * Every release team-game of `team` with its per-game offense and defense-allowed value of
 * `metric`, the pooled FBS average of each game's week, and a season-to-date header through
 * the latest charted week. The header uses `efficiencyPoints` and `scatterRanks` exactly as
 * the Efficiency chart does for that window (success rate is its x axis, the other metrics
 * its y axis), so values and ranks match it. The explosive rate needs `withYardage` rows.
 */
export function teamGameLog(roster: readonly RosterRow[], rows: readonly TeamGameRow[], team: string, metric: GameLogMetric): TeamGameLog {
  const sides: readonly Side[] = ["offense", "defense"];
  const weekly = new Map<number, Record<Side, [number, number]>>();
  for (const row of rows) {
    const acc = weekly.get(row.week) ?? { offense: [0, 0], defense: [0, 0] };
    for (const side of sides) {
      const [num, den] = gameLogTerms(row, side, metric);
      acc[side] = [acc[side][0] + num, acc[side][1] + den];
    }
    weekly.set(row.week, acc);
  }
  const games = rows
    .filter((row) => row.team === team)
    .sort((a, b) => a.week - b.week || a.gameId - b.gameId)
    .map((row): GameLogGame => {
      const week = weekly.get(row.week)!;
      const outcome = row.pointsFor > row.pointsAgainst ? "W" : row.pointsFor < row.pointsAgainst ? "L" : "T";
      return {
        gameId: row.gameId,
        week: row.week,
        opponent: row.opponent,
        site: row.site,
        pointsFor: row.pointsFor,
        pointsAgainst: row.pointsAgainst,
        result: `${outcome} ${row.pointsFor}-${row.pointsAgainst}`,
        offense: ratioOrNull(gameLogTerms(row, "offense", metric)),
        defense: ratioOrNull(gameLogTerms(row, "defense", metric)),
        average: { offense: ratioOrNull(week.offense), defense: ratioOrNull(week.defense) },
      };
    });
  const weeks = netSuccessWeeks(rows);
  const throughWeek = weeks.length ? weeks[weeks.length - 1] : null;
  const seasonFor = (side: Side): GameLogSeason => {
    if (throughWeek === null) return { value: null, rank: null, ranked: 0, average: null };
    const data = efficiencyPoints(roster, rows, throughWeek, side, metric === "success" ? "ppa" : metric);
    const axis = metric === "success" ? "x" : "y";
    const point = data.points.find((p) => p.team === team);
    const rank = scatterRanks(data).get(team);
    return { value: point ? point[axis] : null, rank: rank ? rank[axis] : null, ranked: data.points.length, average: data.average ? data.average[axis] : null };
  };
  return { team, metric, games, throughWeek, season: { offense: seasonFor("offense"), defense: seasonFor("defense") } };
}

/**
 * The game log's team when `team=` names none: the top adjusted-net team (offense minus
 * defense allowed) of the latest stored window among the group's roster teams, ties by
 * name; without adjusted rows, the first group team by name with a game; else null.
 */
export function defaultGameLogTeam(
  roster: readonly RosterRow[],
  rows: readonly TeamGameRow[],
  adjusted: readonly AdjustedRow[],
  filter: ConferenceFilter = "all",
): string | null {
  const group = roster.filter((r) => matchesConference(filter, r.team, r.conference));
  const latest = Math.max(...adjusted.map((row) => row.asOfWeek));
  const best = adjustedPoints(group, adjusted.filter((row) => row.asOfWeek === latest))
    .points.map((p) => ({ team: p.team, net: p.x - p.y }))
    .sort((a, b) => b.net - a.net || byTeam(a, b))[0];
  if (best) return best.team;
  const playing = new Set(rows.map((row) => row.team));
  return group.map((r) => r.team).filter((team) => playing.has(team)).sort()[0] ?? null;
}

// ---------------------------------------------------------------------------
// Ticks and domains
// ---------------------------------------------------------------------------

/** "Nice" tick values covering [min, max] with about `count` ticks. */
export function niceTicks(min: number, max: number, count = 6): number[] {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [];
  if (min === max) return [min];
  const span = max - min;
  const rough = span / Math.max(1, count);
  const magnitude = 10 ** Math.floor(Math.log10(rough));
  const residual = rough / magnitude;
  const step = (residual >= 5 ? 5 : residual >= 2 ? 2 : 1) * magnitude;
  const start = Math.ceil(min / step) * step;
  const ticks: number[] = [];
  for (let value = start; value <= max + step * 1e-9; value += step) {
    ticks.push(Number(value.toFixed(10)));
  }
  return ticks;
}

/**
 * The value window of each game-log panel, fitted to that panel's own bars and dashed
 * averages (zero always included). Rates, which never go below zero, start at zero; a
 * signed metric (PPA) gets headroom at both ends for the value labels. The chart draws
 * both windows at one pixels-per-unit scale (heights proportional to each window's span),
 * so a bar's length means the same amount in either panel.
 */
export function gameLogDomains(log: TeamGameLog, headroom = 0.14): Record<Side, Domain> {
  const windowFor = (side: Side): Domain => {
    const values = log.games.flatMap((game) => [game[side], game.average[side]]).filter((v): v is number => v !== null);
    const low = Math.min(0, ...values);
    const high = Math.max(0, ...values);
    if (high === low) return [0, 1];
    const margin = (high - low) * headroom;
    return [low < 0 ? low - margin : 0, high + margin];
  };
  return { offense: windowFor("offense"), defense: windowFor("defense") };
}

/**
 * Axis domain for the net-success bars, sized to the values shown rather than mirrored
 * around zero: it spans the lowest and highest bar plus the pixel room the logos need
 * (`tipPx` beyond a bar's tip for the winner, `crossPx` across zero for the loser), so a
 * slate whose bars are mostly positive does not reserve an equally tall negative half.
 * Returns the [low, high] value range mapped onto `spanPx` pixels.
 */
export function netSuccessDomain(
  values: readonly number[],
  spanPx: number,
  tipPx: number,
  crossPx: number,
): Domain {
  if (!values.length) return [-0.05, 0.05];
  const hasUp = values.some((v) => v >= 0);
  const hasDown = values.some((v) => v < 0);
  const high = Math.max(0, ...values);
  const low = Math.min(0, ...values);
  const padHigh = hasUp ? tipPx : crossPx;
  const padLow = hasDown ? tipPx : crossPx;
  const range = Math.max(high - low, 0.01);
  const plotPx = spanPx - padHigh - padLow;
  if (plotPx <= 0) return [low - range * 0.1, high + range * 0.1];
  const perPx = range / plotPx;
  return [low - padLow * perPx, high + padHigh * perPx];
}

/**
 * Baseline `y` for a bar's value label. Outside the tip by default, on the side away from
 * the zero line (a bar that rises from zero gets its label above the tip, one that hangs
 * gets it below, whichever panel it is in); when the dashed average line would run through
 * that spot, the label goes just inside the tip instead, if the bar is tall enough.
 */
export function valueLabelY(tipY: number, zeroY: number, averageY: number | null, clearance = 11): number {
  const up = tipY < zeroY;
  const outside = up ? tipY - 6 : tipY + 13;
  const inside = up ? tipY + 14 : tipY - 5;
  const touchesAverage = (y: number) => averageY !== null && averageY > y - clearance + 1 && averageY < y + 4;
  if (!touchesAverage(outside)) return outside;
  return Math.abs(tipY - zeroY) >= 22 && !touchesAverage(inside) ? inside : outside;
}

export type Box = { x: number; y: number; w: number; h: number };

const overlaps = (a: Box, b: Box) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

/**
 * Index of the candidate box that covers the fewest obstacles (the first one wins a tie, so
 * candidates are listed in order of preference). A candidate outside `bounds` never wins
 * over one inside it.
 */
export function leastCrowdedSpot(candidates: readonly Box[], obstacles: readonly Box[], bounds: Box): number {
  let best = -1;
  let bestScore = Infinity;
  candidates.forEach((candidate, index) => {
    const inside = candidate.x >= bounds.x && candidate.y >= bounds.y
      && candidate.x + candidate.w <= bounds.x + bounds.w && candidate.y + candidate.h <= bounds.y + bounds.h;
    const score = (inside ? 0 : 1000) + obstacles.filter((box) => overlaps(candidate, box)).length;
    if (score < bestScore) {
      best = index;
      bestScore = score;
    }
  });
  return best;
}

/** Padded [min, max] of `values` (a fixed fallback when empty or constant). */
export function domainFor(values: readonly number[], pad = 0.06): Domain {
  if (!values.length) return [0, 1];
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  if (lo === hi) return [lo - 0.5, hi + 0.5];
  const margin = (hi - lo) * pad;
  return [lo - margin, hi + margin];
}

// ---------------------------------------------------------------------------
// Text and color helpers
// ---------------------------------------------------------------------------

/** WCAG relative luminance of a `#rrggbb` color (0 = black, 1 = white). */
export function relativeLuminance(hex: string): number {
  const channel = (offset: number) => {
    const value = parseInt(hex.slice(offset, offset + 2), 16) / 255;
    return value <= 0.03928 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(1) + 0.7152 * channel(3) + 0.0722 * channel(5);
}

/**
 * A bar color that stays visible on both the light and dark chart backgrounds: the
 * team's primary color, else its alternate, else the fallback, requiring a mid-range
 * luminance (near-white and near-black team colors vanish on one of the themes).
 */
export function chartColor(primary: string, alt: string | null, fallback: string): string {
  const visible = (hex: string) => {
    const luminance = relativeLuminance(hex);
    return luminance >= 0.06 && luminance <= 0.7;
  };
  if (/^#[0-9a-f]{6}$/i.test(primary) && visible(primary)) return primary;
  if (alt && /^#[0-9a-f]{6}$/i.test(alt) && visible(alt)) return alt;
  return fallback;
}

export function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

export function formatEpa(value: number): string {
  const text = value.toFixed(3);
  return value > 0 ? `+${text}` : text;
}

// ---------------------------------------------------------------------------
// Advanced Visualization Suite: Downs, Finishing Drives, Resume, Market Board
// ---------------------------------------------------------------------------

export type TeamSeasonStatRow = {
  season: number;
  asOfWeek: number;
  team: string;
  role: Side;
  metric: string;
  value: number | null;
  n: number;
  games: number;
  rank: number | null;
  cohortSize: number | null;
};

export type TeamResumeChartRow = {
  periodId: string;
  postWeek: number | null;
  team: string;
  overallRank: number;
  completedGames: number;
  scheduledGames: number;
  wins: number;
  losses: number;
  sor: number | null;
  sorRank: number | null;
  sosPlayedElite: number | null;
};

export type SlateMarketGameRow = {
  gameId: number;
  season: number;
  week: number;
  startDate: Date;
  homeTeam: string;
  awayTeam: string;
  homeTeamSpreadLine: number | null;
  totalLine: number | null;
  predictedSpread: number | null;
  predictedTotal: number | null;
  edgeSpread: number | null;
  edgeTotal: number | null;
  spreadLean: "home" | "away" | null;
  totalLean: "over" | "under" | null;
};

export type DownsScatterPoint = ScatterPoint & {
  earlyDownEpa: number;
  convRate3rd4th: number;
};

export type FinishingDrivesScatterPoint = ScatterPoint & {
  scoringOppRate: number;
  ptsPerScoringOpp: number;
};

export type ResumeScatterPoint = ScatterPoint & {
  overallRating: number;
  sor: number;
  sorRank: number | null;
  wins: number;
  losses: number;
};

export type MarketBoardMetric = "spread" | "total";

export type MarketBoardPoint = {
  gameId: number;
  homeTeam: string;
  awayTeam: string;
  startDate: Date;
  marketLine: number;
  modelLine: number;
  edge: number;
  lean: string | null;
  highEdge: boolean;
  x: number;
  y: number;
};

export type MarketBoardData = {
  points: MarketBoardPoint[];
  unavailable: { homeTeam: string; awayTeam: string; reason: string }[];
  metric: MarketBoardMetric;
};

export function downsThroughWeeks(rows: readonly TeamSeasonStatRow[]): number[] {
  const weeks = new Set<number>();
  for (const r of rows) {
    if (r.metric === "early_down_epa" || r.metric === "conv_rate_3rd_4th") {
      weeks.add(r.asOfWeek);
    }
  }
  return [...weeks].sort((a, b) => a - b);
}

export function downsScatterPoints(
  roster: readonly RosterRow[],
  statsRows: readonly TeamSeasonStatRow[],
  side: Side,
): ScatterData {
  const points: ScatterPoint[] = [];
  const unavailable: string[] = [];

  const byTeamMap = new Map<string, { epa?: number; conv?: number; n: number }>();
  for (const r of statsRows) {
    if (r.role !== side || r.value === null || !Number.isFinite(r.value)) continue;
    const entry = byTeamMap.get(r.team) ?? { n: 0 };
    if (r.metric === "early_down_epa") {
      entry.epa = r.value;
      entry.n = Math.max(entry.n, r.n);
    } else if (r.metric === "conv_rate_3rd_4th") {
      entry.conv = r.value;
      entry.n = Math.max(entry.n, r.n);
    }
    byTeamMap.set(r.team, entry);
  }

  const rosterByTeam = new Map(roster.map((r) => [r.team, r]));
  for (const [team, r] of rosterByTeam) {
    const entry = byTeamMap.get(team);
    if (entry && entry.epa !== undefined && entry.conv !== undefined) {
      points.push({
        team,
        conference: r.conference,
        x: entry.epa,
        y: entry.conv,
        n: entry.n,
      });
    } else {
      unavailable.push(team);
    }
  }
  points.sort(byTeam);

  let average: { x: number; y: number } | null = null;
  if (points.length > 0) {
    const totalN = points.reduce((s, p) => s + (p.n > 0 ? p.n : 1), 0);
    const avgX = points.reduce((s, p) => s + p.x * (p.n > 0 ? p.n : 1), 0) / totalN;
    const avgY = points.reduce((s, p) => s + p.y * (p.n > 0 ? p.n : 1), 0) / totalN;
    average = { x: avgX, y: avgY };
  }

  const isDefense = side === "defense";
  return {
    points,
    average,
    unavailable,
    invertX: isDefense,
    invertY: isDefense,
  };
}

export function finishingDrivesThroughWeeks(rows: readonly TeamSeasonStatRow[]): number[] {
  const weeks = new Set<number>();
  for (const r of rows) {
    if (r.metric === "scoring_opp_rate" || r.metric === "pts_per_scoring_opp") {
      weeks.add(r.asOfWeek);
    }
  }
  return [...weeks].sort((a, b) => a - b);
}

export function finishingDrivesScatterPoints(
  roster: readonly RosterRow[],
  statsRows: readonly TeamSeasonStatRow[],
  side: Side,
): ScatterData {
  const points: ScatterPoint[] = [];
  const unavailable: string[] = [];

  const byTeamMap = new Map<string, { oppRate?: number; ptsPerOpp?: number; n: number }>();
  for (const r of statsRows) {
    if (r.role !== side || r.value === null || !Number.isFinite(r.value)) continue;
    const entry = byTeamMap.get(r.team) ?? { n: 0 };
    if (r.metric === "scoring_opp_rate") {
      entry.oppRate = r.value;
      entry.n = Math.max(entry.n, r.n);
    } else if (r.metric === "pts_per_scoring_opp") {
      entry.ptsPerOpp = r.value;
      entry.n = Math.max(entry.n, r.n);
    }
    byTeamMap.set(r.team, entry);
  }

  const rosterByTeam = new Map(roster.map((r) => [r.team, r]));
  for (const [team, r] of rosterByTeam) {
    const entry = byTeamMap.get(team);
    if (entry && entry.oppRate !== undefined && entry.ptsPerOpp !== undefined) {
      points.push({
        team,
        conference: r.conference,
        x: entry.oppRate,
        y: entry.ptsPerOpp,
        n: entry.n,
      });
    } else {
      unavailable.push(team);
    }
  }
  points.sort(byTeam);

  let average: { x: number; y: number } | null = null;
  if (points.length > 0) {
    const totalN = points.reduce((s, p) => s + (p.n > 0 ? p.n : 1), 0);
    const avgX = points.reduce((s, p) => s + p.x * (p.n > 0 ? p.n : 1), 0) / totalN;
    const avgY = points.reduce((s, p) => s + p.y * (p.n > 0 ? p.n : 1), 0) / totalN;
    average = { x: avgX, y: avgY };
  }

  const isDefense = side === "defense";
  return {
    points,
    average,
    unavailable,
    invertX: isDefense,
    invertY: isDefense,
  };
}

export function resumeQualityScatterPoints(
  roster: readonly RosterRow[],
  ratingRows: readonly RatingSnapshotRow[],
  resumeRows: readonly TeamResumeChartRow[],
): ScatterData {
  const points: ScatterPoint[] = [];
  const unavailable: string[] = [];

  const ratingsByTeam = new Map(ratingRows.map((r) => [r.team, r]));
  const resumeByTeam = new Map(resumeRows.map((r) => [r.team, r]));
  const rosterByTeam = new Map(roster.map((r) => [r.team, r]));

  for (const [team, r] of rosterByTeam) {
    const rating = ratingsByTeam.get(team);
    const resume = resumeByTeam.get(team);
    if (
      rating &&
      Number.isFinite(rating.overallRating) &&
      resume &&
      resume.sor !== null &&
      Number.isFinite(resume.sor)
    ) {
      points.push({
        team,
        conference: r.conference,
        x: rating.overallRating,
        y: resume.sor,
        n: resume.completedGames,
      });
    } else {
      unavailable.push(team);
    }
  }
  points.sort(byTeam);

  let average: { x: number; y: number } | null = null;
  if (points.length > 0) {
    const avgX = points.reduce((s, p) => s + p.x, 0) / points.length;
    const avgY = points.reduce((s, p) => s + p.y, 0) / points.length;
    average = { x: avgX, y: avgY };
  }

  return {
    points,
    average,
    unavailable,
    invertX: false,
    invertY: false,
  };
}

export function marketBoardWeeks(games: readonly SlateMarketGameRow[]): number[] {
  const weeks = new Set<number>();
  for (const g of games) {
    weeks.add(g.week);
  }
  return [...weeks].sort((a, b) => a - b);
}

export function marketBoardPoints(
  games: readonly SlateMarketGameRow[],
  metric: MarketBoardMetric,
): MarketBoardData {
  const points: MarketBoardPoint[] = [];
  const unavailable: { homeTeam: string; awayTeam: string; reason: string }[] = [];

  for (const g of games) {
    if (metric === "spread") {
      const market = g.homeTeamSpreadLine;
      const model = homeSpreadFromMargin(g.predictedSpread);
      if (market === null || model === null || !Number.isFinite(market) || !Number.isFinite(model)) {
        unavailable.push({ homeTeam: g.homeTeam, awayTeam: g.awayTeam, reason: "Missing spread line or model projection" });
        continue;
      }
      const edge = g.edgeSpread ?? Math.abs(model - market);
      points.push({
        gameId: g.gameId,
        homeTeam: g.homeTeam,
        awayTeam: g.awayTeam,
        startDate: g.startDate,
        marketLine: market,
        modelLine: model,
        edge,
        lean: g.spreadLean,
        highEdge: Math.abs(edge) >= 3.0,
        x: market,
        y: model,
      });
    } else {
      const market = g.totalLine;
      const model = g.predictedTotal;
      if (market === null || model === null || !Number.isFinite(market) || !Number.isFinite(model)) {
        unavailable.push({ homeTeam: g.homeTeam, awayTeam: g.awayTeam, reason: "Missing total line or model projection" });
        continue;
      }
      const edge = g.edgeTotal ?? Math.abs(model - market);
      points.push({
        gameId: g.gameId,
        homeTeam: g.homeTeam,
        awayTeam: g.awayTeam,
        startDate: g.startDate,
        marketLine: market,
        modelLine: model,
        edge,
        lean: g.totalLean,
        highEdge: Math.abs(edge) >= 3.0,
        x: market,
        y: model,
      });
    }
  }

  return {
    points,
    unavailable,
    metric,
  };
}
