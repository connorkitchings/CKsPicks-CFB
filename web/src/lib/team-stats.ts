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
}

export interface UnitMatchupRow {
  key: string;
  name: string;
  offenseValue: string;
  offenseRank: number | null;
  /** Teams ranked on this metric/role (early weeks rank fewer than 138). */
  offenseCohort: number | null;
  defenseValue: string;
  defenseRank: number | null;
  defenseCohort: number | null;
}

type Format = "epa" | "pct" | "pts" | "field";

/** Display order. Defense values describe what that defense allowed. */
export const UNIT_METRICS: { key: string; label: string; format: Format }[] = [
  { key: "epa_pass", label: "Pass EPA/play", format: "epa" },
  { key: "epa_rush", label: "Rush EPA/play", format: "epa" },
  { key: "early_down_epa", label: "Early-down EPA", format: "epa" },
  { key: "success_rate", label: "Success rate", format: "pct" },
  { key: "explosive_rate", label: "Explosive plays (20+)", format: "pct" },
  { key: "scoring_opp_rate", label: "Scoring opps/drive", format: "pct" },
  { key: "pts_per_scoring_opp", label: "Pts/scoring opp", format: "pts" },
  { key: "avg_start_field_pos", label: "Avg start", format: "field" },
  { key: "conv_rate_3rd_4th", label: "3rd/4th down conv.", format: "pct" },
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

function find(rows: TeamStatRow[], team: string, role: StatRole, metric: string) {
  return rows.find((r) => r.team === team && r.role === role && r.metric === metric) ?? null;
}

/** Offense of `offenseTeam` against the defense of `defenseTeam`; missing data shows "—". */
export function buildUnitRows(
  rows: TeamStatRow[],
  offenseTeam: string,
  defenseTeam: string,
): UnitMatchupRow[] {
  return UNIT_METRICS.map(({ key, label, format }) => {
    const off = find(rows, offenseTeam, "offense", key);
    const def = find(rows, defenseTeam, "defense", key);
    return {
      key,
      name: label,
      offenseValue: formatMetric(format, off?.value ?? null),
      offenseRank: off?.rank ?? null,
      offenseCohort: off?.cohortSize ?? null,
      defenseValue: formatMetric(format, def?.value ?? null),
      defenseRank: def?.rank ?? null,
      defenseCohort: def?.cohortSize ?? null,
    };
  });
}

/** Completed FBS games behind a team's snapshot (0 when it has no rows). */
export function gamesBehind(rows: TeamStatRow[], team: string): number {
  return rows.reduce((max, r) => (r.team === team ? Math.max(max, r.games) : max), 0);
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
