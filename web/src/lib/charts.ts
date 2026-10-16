import { teamAbbr } from "./team-logos.ts";

/**
 * Pure transforms for the weekly team charts. Inputs are the rows of the release's
 * `team_season_roster`, `team_game_stats` and `team_adjusted_epa` projections; nothing
 * here reads a database. Everything is a descriptive reconstruction from the release's
 * data, windowed by week only.
 */

export type ChartKind = "net-success" | "efficiency" | "adjusted";
export type Side = "offense" | "defense";

export type RosterRow = { team: string; conference: string | null };

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
};

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

/** Power Four conferences; Notre Dame is included by name (it has no conference). */
export const P4_CONFERENCES = ["ACC", "Big Ten", "Big 12", "SEC"] as const;
export const P4_INDEPENDENTS = ["Notre Dame"] as const;
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
  bars.sort((a, b) => a.value - b.value || a.gameId - b.gameId);
  return { bars, notCharted };
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
 * Cumulative success rate (x) against PPA/play (y) through `throughWeek`, FBS roster
 * teams only. Averages are pooled over all plays of roster teams in the window, so teams
 * with more plays weigh more. Teams with no eligible games or a null metric are listed
 * as unavailable.
 */
export function efficiencyPoints(
  roster: readonly RosterRow[],
  rows: readonly TeamGameRow[],
  throughWeek: number,
  side: Side,
): ScatterData {
  const prefix = side === "offense" ? "off" : "def";
  const sums = new Map<string, { sn: number; ss: number; en: number; es: number }>();
  const rosterNames = new Set(roster.map((r) => r.team));
  for (const row of rows) {
    if (row.week > throughWeek || !rosterNames.has(row.team)) continue;
    const acc = sums.get(row.team) ?? { sn: 0, ss: 0, en: 0, es: 0 };
    acc.sn += prefix === "off" ? row.offSuccessN : row.defSuccessN;
    acc.ss += prefix === "off" ? row.offSuccessSum : row.defSuccessSum;
    acc.en += prefix === "off" ? row.offEpaN : row.defEpaN;
    acc.es += prefix === "off" ? row.offEpaSum : row.defEpaSum;
    sums.set(row.team, acc);
  }
  const points: ScatterPoint[] = [];
  const unavailable: string[] = [];
  const pooled = { sn: 0, ss: 0, en: 0, es: 0 };
  for (const { team, conference } of roster) {
    const acc = sums.get(team);
    if (acc) {
      pooled.sn += acc.sn;
      pooled.ss += acc.ss;
      pooled.en += acc.en;
      pooled.es += acc.es;
    }
    if (!acc || acc.sn === 0 || acc.en === 0) {
      unavailable.push(team);
      continue;
    }
    points.push({ team, conference, x: acc.ss / acc.sn, y: acc.es / acc.en, n: acc.en });
  }
  points.sort(byTeam);
  unavailable.sort();
  const average = pooled.sn > 0 && pooled.en > 0 ? { x: pooled.ss / pooled.sn, y: pooled.es / pooled.en } : null;
  return { points, average, unavailable, invertX: side === "defense", invertY: side === "defense" };
}

export type AdjustedScatter = ScatterData & {
  /** Points carry offense on x and defense allowed on y; net = x - y. */
  netLevels: number[];
};

/**
 * Opponent-adjusted offense (x) against adjusted defense allowed (y, inverted) for one
 * `as_of_week` window. A point needs both an adjusted offense and defense row; averages
 * are play-weighted over plotted teams.
 */
export function adjustedPoints(roster: readonly RosterRow[], rows: readonly AdjustedRow[]): AdjustedScatter {
  const offense = new Map<string, AdjustedRow>();
  const defense = new Map<string, AdjustedRow>();
  for (const row of rows) (row.role === "offense" ? offense : defense).set(row.team, row);
  const points: ScatterPoint[] = [];
  const unavailable: string[] = [];
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
    points.push({ team, conference, x: o.adjustedEpaPerPlay, y: d.adjustedEpaPerPlay, n: o.epaN + d.epaN });
    ox += o.adjustedEpaPerPlay * o.epaN;
    on += o.epaN;
    oy += d.adjustedEpaPerPlay * d.epaN;
    dn += d.epaN;
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
    netLevels: netLevelsFor(points),
  };
}

/** Evenly spaced equal-net levels (x - y) that cover the plotted points. */
export function netLevelsFor(points: readonly ScatterPoint[]): number[] {
  if (!points.length) return [];
  const nets = points.map((p) => p.x - p.y);
  const lo = Math.min(...nets);
  const hi = Math.max(...nets);
  const ticks = niceTicks(lo, hi, 7);
  return ticks.filter((tick) => tick > lo && tick < hi);
}

export type Domain = [number, number];
export type Segment = { net: number; from: [number, number]; to: [number, number] };

/** Diagonal equal-net lines (y = x - net) clipped to the plot rectangle. */
export function isoNetSegments(x: Domain, y: Domain, levels: readonly number[]): Segment[] {
  const segments: Segment[] = [];
  for (const net of levels) {
    // y = x - net, with x in [x0, x1] and y in [y0, y1].
    const lo = Math.max(x[0], y[0] + net);
    const hi = Math.min(x[1], y[1] + net);
    if (lo < hi) segments.push({ net, from: [lo, lo - net], to: [hi, hi - net] });
  }
  return segments;
}

// ---------------------------------------------------------------------------
// Filters
// ---------------------------------------------------------------------------

/** "all", "p4" (Power Four plus Notre Dame) or a conference name from the roster. */
export type ConferenceFilter = string;

export function isP4(team: string, conference: string | null): boolean {
  return (
    (conference !== null && (P4_CONFERENCES as readonly string[]).includes(conference)) ||
    (P4_INDEPENDENTS as readonly string[]).includes(team)
  );
}

export function matchesConference(filter: ConferenceFilter, team: string, conference: string | null): boolean {
  if (filter === "all") return true;
  if (filter === "p4") return isP4(team, conference);
  return conference === filter;
}

/** Conferences present in the published roster, ascending. */
export function conferenceOptions(roster: readonly RosterRow[]): string[] {
  return [...new Set(roster.flatMap((r) => (r.conference ? [r.conference] : [])))].sort();
}

/** Case-insensitive match on the team name or its abbreviation. */
export function matchesSearch(query: string, team: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return false;
  return team.toLowerCase().includes(q) || teamAbbr(team).toLowerCase() === q;
}

/** National per-axis competition ranks, computed from the full plotted population. */
export function scatterRanks(data: ScatterData): Map<string, { x: number; y: number }> {
  const rankAxis = (axis: "x" | "y", lowerBetter: boolean) => {
    const sorted = [...data.points].sort((a, b) => lowerBetter ? a[axis] - b[axis] : b[axis] - a[axis]);
    const ranks = new Map<string, number>();
    let rank = 1;
    sorted.forEach((point, index) => {
      if (index === 0 || point[axis] !== sorted[index - 1][axis]) rank = index + 1;
      ranks.set(point.team, rank);
    });
    return ranks;
  };
  const x = rankAxis("x", data.invertX);
  const y = rankAxis("y", data.invertY);
  return new Map(data.points.map((point) => [point.team, { x: x.get(point.team)!, y: y.get(point.team)! }]));
}

/** Filter actual rows; a game qualifies when either participant belongs to the group. */
export function filterNetSuccessBars(bars: readonly NetSuccessBar[], roster: readonly RosterRow[], filter: ConferenceFilter): NetSuccessBar[] {
  const conferences = new Map(roster.map((row) => [row.team, row.conference]));
  return bars.filter((bar) => matchesConference(filter, bar.winner, conferences.get(bar.winner) ?? null) || matchesConference(filter, bar.loser, conferences.get(bar.loser) ?? null));
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

export const CHART_TITLES: Record<ChartKind, string> = {
  "net-success": "Did We Really Get Beat That Bad?",
  efficiency: "Efficiency and PPA/play",
  adjusted: "Opponent-adjusted PPA/play",
};

export const CHART_TAB_LABELS: Record<ChartKind, string> = {
  "net-success": "Net success rate",
  efficiency: "Efficiency",
  adjusted: "Adjusted PPA/play",
};

export function chartSubtitle(kind: ChartKind, season: number, week: number, side: Side): string {
  const base = `${season} | FBS vs FBS`;
  if (kind === "net-success") return `Week ${week} | ${base}`;
  const through = `Through Week ${week}`;
  if (kind === "efficiency") return `${side === "offense" ? "Offense" : "Defense"} | ${base} | ${through}`;
  return `${base} | ${through}`;
}

export const CHART_FOOTNOTES: Record<ChartKind, string> = {
  "net-success":
    "Bar = winner's offensive success-rate advantage/disadvantage in percentage points, on eligible plays (regulation only; garbage time and special teams excluded). Label = winner and final score. Reconstructed from this release's data.",
  efficiency:
    "Cumulative success rate and CFBD Predicted Points Added/play (valid PPA only) on eligible plays (regulation only; garbage time and special teams excluded), FBS vs FBS games. Dashed lines are FBS averages. On defense, axes are inverted so up and right is better. Reconstructed from this release's data.",
  adjusted:
    "PPA/play adjusted for opponent strength and home-field venue using the V5 iterative adjuster, FBS vs FBS games. Dashed lines are play-weighted FBS averages; diagonals mark equal net (offense minus defense allowed). Reconstructed from this release's data.",
};

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
