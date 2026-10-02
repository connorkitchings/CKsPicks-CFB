/** Pure helpers for the pre-game team stats shown on matchup pages (contract 10). */

export type StatRole = "offense" | "defense";

export interface TeamStatRow {
  team: string;
  role: StatRole;
  metric: string;
  value: number | null;
  n: number;
  games: number;
  rank: number | null;
  cohortSize: number | null;
  /** Another team in the same cohort shares this rank (the publisher ranks ties by minimum rank). */
  tied: boolean;
}

/** Which side of a row holds the statistical edge, and how big it is. */
export interface RowEdge {
  side: "offense" | "defense" | "even";
  /** null when the sides are even. */
  strength: "slight" | "strong" | null;
}

export interface UnitMatchupRow {
  key: string;
  name: string;
  offenseValue: string;
  offenseRank: number | null;
  /** Teams ranked on this metric/role (early weeks rank fewer than 138). */
  offenseCohort: number | null;
  offenseTied: boolean;
  defenseValue: string;
  defenseRank: number | null;
  defenseCohort: number | null;
  defenseTied: boolean;
  /** Offense rank against the opposing defense's rank; null when either is unranked. */
  edge: RowEdge | null;
  section: MetricSection;
}

type Format = "epa" | "pct" | "pts" | "field";

/** Matchup table sections, in display order. */
export type MetricSection = "possession" | "situational" | "drive";

export const SECTION_LABELS: Record<MetricSection, string> = {
  possession: "Core possession efficiency",
  situational: "Situational / down and distance",
  drive: "Drive context",
};

/**
 * Display order, grouped into sections so the table stays readable on a phone.
 * Defense values describe what that defense allowed. The possession metrics are
 * the raw (not opponent-adjusted) measures behind the V5 ratings, from
 * `team_possession_stats`; the rest come from `team_season_stats`.
 */
export const UNIT_METRICS: {
  key: string;
  label: string;
  format: Format;
  section: MetricSection;
}[] = [
  { key: "ppp", label: "Points/possession", format: "pts", section: "possession" },
  { key: "epa_per_possession", label: "EPA/possession", format: "epa", section: "possession" },
  { key: "epa_per_play", label: "EPA/play", format: "epa", section: "possession" },
  { key: "success_rate", label: "Success rate", format: "pct", section: "situational" },
  { key: "explosive_rate", label: "Explosive plays (20+)", format: "pct", section: "situational" },
  { key: "conv_rate_3rd_4th", label: "3rd/4th down conv.", format: "pct", section: "situational" },
  { key: "early_down_epa", label: "Early-down EPA", format: "epa", section: "situational" },
  { key: "epa_pass", label: "Pass EPA/play", format: "epa", section: "situational" },
  { key: "epa_rush", label: "Rush EPA/play", format: "epa", section: "situational" },
  { key: "scoring_opp_rate", label: "Scoring opps/drive", format: "pct", section: "drive" },
  { key: "pts_per_scoring_opp", label: "Pts/scoring opp", format: "pts", section: "drive" },
  { key: "avg_start_field_pos", label: "Avg start", format: "field", section: "drive" },
];

export function formatMetric(format: Format, value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  switch (format) {
    case "epa":
      return `${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(2)}`;
    case "pct":
      return `${(value * 100).toFixed(1)}%`;
    case "pts":
      return value.toFixed(2);
    case "field":
      return `Own ${value.toFixed(1)}`;
  }
}

/** A model rating with its sign, e.g. "+0.41" or "−0.37" (a true minus sign); "—" when missing. */
export function formatSignedRating(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return `${value >= 0 ? "+" : "−"}${Math.abs(value).toFixed(2)}`;
}

/** Rank text: "#75", "T-75" for a tie, "—" when unranked. */
export function rankLabel(rank: number | null, tied: boolean): string {
  if (rank === null) return "—";
  return tied ? `T-${rank}` : `#${rank}`;
}

/** Tooltip for a rank badge. */
export function rankTitle(rank: number | null, tied: boolean, cohort: number | null): string {
  if (rank === null) return "Not ranked";
  const of = cohort ? ` of ${cohort}` : "";
  return tied ? `Tied for #${rank}${of}` : `National rank #${rank}${of}`;
}

/** Gap in rank percentile (0 to 1) below which a row counts as even / above which it is strong. */
export const EDGE_EVEN_GAP = 0.1;
export const EDGE_STRONG_GAP = 0.3;

function percentile(rank: number, cohort: number): number {
  return cohort > 1 ? 1 - (rank - 1) / (cohort - 1) : 1; // 1 = best in the nation
}

/**
 * Which side of the row has the edge: the offense when its national rank beats
 * the opposing defense's by more than the even band, the defense when it is
 * ahead. Null when either side is unranked (no sample, a zero, or early weeks).
 */
export function rowEdge(
  offenseRank: number | null,
  offenseCohort: number | null,
  defenseRank: number | null,
  defenseCohort: number | null,
): RowEdge | null {
  if (offenseRank === null || defenseRank === null) return null;
  const gap =
    percentile(offenseRank, offenseCohort ?? 138) - percentile(defenseRank, defenseCohort ?? 138);
  const size = Math.abs(gap);
  if (size < EDGE_EVEN_GAP) return { side: "even", strength: null };
  return {
    side: gap > 0 ? "offense" : "defense",
    strength: size >= EDGE_STRONG_GAP ? "strong" : "slight",
  };
}

/** Row counts per side, for the summary above each table. */
export function edgeSummary(rows: UnitMatchupRow[]): { offense: number; defense: number; even: number } {
  const out = { offense: 0, defense: 0, even: 0 };
  for (const row of rows) if (row.edge) out[row.edge.side] += 1;
  return out;
}

function find(rows: TeamStatRow[], team: string, role: StatRole, metric: string) {
  return rows.find((r) => r.team === team && r.role === role && r.metric === metric) ?? null;
}

/** Offense of `offenseTeam` against the defense of `defenseTeam`; missing data shows "—". */
export function buildUnitRows(
  rows: TeamStatRow[],
  offenseTeam: string,
  defenseTeam: string,
): UnitMatchupRow[] {
  return UNIT_METRICS.map(({ key, label, format, section }) => {
    const off = find(rows, offenseTeam, "offense", key);
    const def = find(rows, defenseTeam, "defense", key);
    // An exact zero is no ranking signal (many teams share it): show the value, not a rank.
    const offRank = off?.value === 0 ? null : (off?.rank ?? null);
    const defRank = def?.value === 0 ? null : (def?.rank ?? null);
    return {
      key,
      name: label,
      offenseValue: formatMetric(format, off?.value ?? null),
      offenseRank: offRank,
      offenseCohort: offRank === null ? null : (off?.cohortSize ?? null),
      offenseTied: offRank !== null && Boolean(off?.tied),
      defenseValue: formatMetric(format, def?.value ?? null),
      defenseRank: defRank,
      defenseCohort: defRank === null ? null : (def?.cohortSize ?? null),
      defenseTied: defRank !== null && Boolean(def?.tied),
      edge: rowEdge(offRank, off?.cohortSize ?? null, defRank, def?.cohortSize ?? null),
      section,
    };
  });
}

/** Completed FBS games behind a team's snapshot (0 when it has no rows). */
export function gamesBehind(rows: TeamStatRow[], team: string): number {
  return rows.reduce((max, r) => (r.team === team ? Math.max(max, r.games) : max), 0);
}

/** Rows grouped by section, preserving the display order. */
export function groupUnitRows(
  rows: UnitMatchupRow[],
): { section: MetricSection; label: string; rows: UnitMatchupRow[] }[] {
  const groups: { section: MetricSection; label: string; rows: UnitMatchupRow[] }[] = [];
  for (const row of rows) {
    const last = groups[groups.length - 1];
    if (last && last.section === row.section) last.rows.push(row);
    else groups.push({ section: row.section, label: SECTION_LABELS[row.section], rows: [row] });
  }
  return groups;
}

export function cohortSizeOf(rows: TeamStatRow[]): number | null {
  const sizes = rows.map((r) => r.cohortSize).filter((n): n is number => n !== null);
  return sizes.length ? Math.max(...sizes) : null;
}

/** Tiers are percentiles of the ranked pool: top 20%, next 25%, next 30%, rest. */
export function getRankBadgeClass(rank: number | null, cohortSize: number | null = null): string {
  if (rank === null) return "bg-surface-inset text-ink-faint border border-line font-medium";
  const pct = rank / Math.max(cohortSize ?? 138, rank);
  if (pct <= 0.2) return "bg-accent/15 text-accent-ink border border-accent/30 font-bold";
  if (pct <= 0.45) {
    return "bg-cyan-500/10 text-cyan-700 dark:text-cyan-300 border border-cyan-500/20 font-semibold";
  }
  if (pct <= 0.75) return "bg-surface-inset text-ink-muted border border-line font-medium";
  return "bg-loss-soft text-loss border border-loss/20 font-medium";
}

export interface MatchupStats {
  /** Snapshot covers FBS-vs-FBS games completed before this week's slate. */
  asOfWeek: number;
  awayGames: number;
  homeGames: number;
  cohortSize: number | null;
  awayOffVsHomeDef: UnitMatchupRow[];
  homeOffVsAwayDef: UnitMatchupRow[];
}

/** Build the stats block from raw rows; null when nothing was published. */
export function buildMatchupStats(
  rows: TeamStatRow[],
  week: number,
  awayTeam: string,
  homeTeam: string,
): MatchupStats | null {
  if (rows.length === 0) return null;
  return {
    asOfWeek: week,
    awayGames: gamesBehind(rows, awayTeam),
    homeGames: gamesBehind(rows, homeTeam),
    cohortSize: cohortSizeOf(rows),
    awayOffVsHomeDef: buildUnitRows(rows, awayTeam, homeTeam),
    homeOffVsAwayDef: buildUnitRows(rows, homeTeam, awayTeam),
  };
}
