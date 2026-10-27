import { edgeSummary, type RowEdge, type UnitMatchupRow } from "./team-stats.ts";

export type FactorKey = "efficiency" | "explosiveness" | "finishing" | "passing_downs" | "field_position";

export type FactorDef = {
  key: FactorKey;
  label: string;
  metricKey: string;
  description: string;
};

/** Turnovers are not part of the published unit stats yet, so this is not Connelly's full Five Factors. */
export const KEY_FACTORS: FactorDef[] = [
  {
    key: "efficiency",
    label: "Overall Efficiency",
    metricKey: "success_rate",
    description: "Success rate (% of plays gaining necessary yardage)",
  },
  {
    key: "explosiveness",
    label: "Explosiveness",
    metricKey: "explosive_rate",
    description: "20+ yard play rate across all plays",
  },
  {
    key: "finishing",
    label: "Finishing Drives",
    metricKey: "pts_per_scoring_opp",
    description: "Points per scoring opportunity (inside the 40)",
  },
  {
    key: "passing_downs",
    label: "Late-Down Conversions",
    metricKey: "conv_rate_3rd_4th",
    description: "3rd & 4th down conversion rate",
  },
  {
    key: "field_position",
    label: "Starting Field Position",
    metricKey: "avg_start_field_pos",
    description: "Average offensive starting yardline",
  },
];

const DEFAULT_COHORT = 138;
const MIN_BAR = 0.05;

/** Bar fill (0.05 to 1) for a rank within its own cohort; null when unranked. */
export function barFraction(rank: number | null, cohort: number | null): number | null {
  if (rank === null) return null;
  const size = Math.max(cohort ?? DEFAULT_COHORT, rank);
  const pct = size > 1 ? 1 - (rank - 1) / (size - 1) : 1;
  return Math.max(MIN_BAR, Math.min(1, pct));
}

export type TapeRow = {
  factor: FactorDef;
  offenseValue: string;
  defenseValue: string;
  offenseRank: number | null;
  defenseRank: number | null;
  offenseCohort: number | null;
  defenseCohort: number | null;
  offenseTied: boolean;
  defenseTied: boolean;
  /** Bar fractions; both null when the row cannot be compared (a rank is missing). */
  offenseBar: number | null;
  defenseBar: number | null;
  /** null when the row is not comparable. */
  edge: RowEdge | null;
};

export function buildTapeRows(rows: UnitMatchupRow[]): TapeRow[] {
  return KEY_FACTORS.map((factor) => {
    const row = rows.find((r) => r.key === factor.metricKey) ?? null;
    const edge = row?.edge ?? null;
    return {
      factor,
      offenseValue: row?.offenseValue ?? "—",
      defenseValue: row?.defenseValue ?? "—",
      offenseRank: row?.offenseRank ?? null,
      defenseRank: row?.defenseRank ?? null,
      offenseCohort: row?.offenseCohort ?? null,
      defenseCohort: row?.defenseCohort ?? null,
      offenseTied: row?.offenseTied ?? false,
      defenseTied: row?.defenseTied ?? false,
      offenseBar: edge && row ? barFraction(row.offenseRank, row.offenseCohort) : null,
      defenseBar: edge && row ? barFraction(row.defenseRank, row.defenseCohort) : null,
      edge,
    };
  });
}

export type TapeVerdict =
  | { kind: "none" }
  | { kind: "offense" | "defense"; count: number; compared: number }
  | { kind: "split"; compared: number };

/** Counts only rows that could be compared; "even" rows count toward the total. */
export function tapeVerdict(rows: TapeRow[]): TapeVerdict {
  const tally = edgeSummary(
    rows.flatMap((r) => (r.edge ? [{ edge: r.edge } as UnitMatchupRow] : [])),
  );
  const compared = tally.offense + tally.defense + tally.even;
  if (compared === 0) return { kind: "none" };
  if (tally.offense > tally.defense) return { kind: "offense", count: tally.offense, compared };
  if (tally.defense > tally.offense) return { kind: "defense", count: tally.defense, compared };
  return { kind: "split", compared };
}
