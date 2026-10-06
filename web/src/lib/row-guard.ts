/**
 * Runtime guards for rows read from the database.
 *
 * Typed `select()` calls and `sql<T>` casts promise a shape but do not check it, so
 * a null, NaN or out-of-domain value would otherwise flow into the page and render
 * as a wrong number (or silently as zero). A guard checks the rows once, at the
 * loader boundary, and throws `RowContractError` on a violation. Pages already turn a
 * thrown loader error into an explicit "temporarily unavailable" state.
 *
 * Guards never coerce or repair a value: valid rows are returned unchanged.
 * Dependency-free so it runs under `node --test` like the other pure helpers.
 */

export type Kind =
  | "int"
  | "number"
  | "string"
  | "boolean"
  | "date"
  | { enum: readonly string[] };

export interface Field {
  kind: Kind;
  nullable?: boolean;
}

export type RowSpec = Record<string, Field>;

export interface Violation {
  index: number;
  field: string;
  reason: string;
}

export class RowContractError extends Error {
  readonly label: string;
  readonly violations: Violation[];
  constructor(label: string, violations: Violation[], total: number) {
    const first = violations
      .slice(0, 3)
      .map((v) => `row ${v.index} ${v.field}: ${v.reason}`)
      .join("; ");
    super(`${label}: ${total} contract violation(s): ${first}`);
    this.name = "RowContractError";
    this.label = label;
    this.violations = violations;
  }
}

const MAX_REPORTED = 20;

function kindProblem(value: unknown, kind: Kind): string | null {
  if (typeof kind === "object") {
    return typeof value === "string" && kind.enum.includes(value)
      ? null
      : `not one of ${kind.enum.join("|")}`;
  }
  switch (kind) {
    case "int":
      return typeof value === "number" && Number.isInteger(value) ? null : "not an integer";
    case "number":
      return typeof value === "number" && Number.isFinite(value) ? null : "not a finite number";
    case "string":
      return typeof value === "string" && value.length > 0 ? null : "not a non-empty string";
    case "boolean":
      return typeof value === "boolean" ? null : "not a boolean";
    case "date":
      return value instanceof Date && !Number.isNaN(value.getTime()) ? null : "not a valid date";
  }
}

/** Return every violation of `spec` (and the optional cross-field `rules`) in `rows`. */
export function checkRows(
  rows: readonly unknown[],
  spec: RowSpec,
  rules: ReadonlyArray<(row: Record<string, unknown>) => string | null> = [],
): { violations: Violation[]; total: number } {
  const violations: Violation[] = [];
  let total = 0;
  const add = (index: number, field: string, reason: string) => {
    total += 1;
    if (violations.length < MAX_REPORTED) violations.push({ index, field, reason });
  };
  rows.forEach((raw, index) => {
    const row = (raw ?? {}) as Record<string, unknown>;
    for (const [field, { kind, nullable }] of Object.entries(spec)) {
      const value = row[field];
      if (value === undefined) {
        add(index, field, "missing");
      } else if (value === null) {
        if (!nullable) add(index, field, "null in a required field");
      } else {
        const problem = kindProblem(value, kind);
        if (problem) add(index, field, problem);
      }
    }
    for (const rule of rules) {
      const problem = rule(row);
      if (problem) add(index, "(row)", problem);
    }
  });
  return { violations, total };
}

/** Throw `RowContractError` when any row breaks the contract; otherwise return `rows`. */
export function guardRows<T>(
  label: string,
  rows: T[],
  spec: RowSpec,
  rules: ReadonlyArray<(row: Record<string, unknown>) => string | null> = [],
): T[] {
  const { violations, total } = checkRows(rows, spec, rules);
  if (total > 0) {
    const error = new RowContractError(label, violations, total);
    console.error(error.message);
    throw error;
  }
  return rows;
}

// ---------------------------------------------------------------------------
// Contracts for the rows the public pages depend on.
// ---------------------------------------------------------------------------

const ROLE = { enum: ["offense", "defense"] } as const;
const GRADE = { enum: ["win", "loss", "push"] } as const;
const SPREAD_LEAN = { enum: ["home", "away"] } as const;
const TOTAL_LEAN = { enum: ["over", "under"] } as const;

/** Rank must be a positive position within its cohort. */
const rankWithinCohort = (row: Record<string, unknown>): string | null => {
  const { rank, cohortSize } = row as { rank: number | null; cohortSize: number | null };
  if (rank === null || rank === undefined) return null;
  if (rank < 1) return "rank below 1";
  if (cohortSize === null || cohortSize === undefined) return "rank without a cohort size";
  return rank > cohortSize ? "rank above the cohort size" : null;
};

export const TEAM_STAT_SPEC: RowSpec = {
  team: { kind: "string" },
  role: { kind: ROLE },
  metric: { kind: "string" },
  value: { kind: "number", nullable: true },
  n: { kind: "number" },
  games: { kind: "int" },
  rank: { kind: "int", nullable: true },
  cohortSize: { kind: "int", nullable: true },
};
export const TEAM_STAT_RULES = [rankWithinCohort];

export const RATING_SPEC: RowSpec = {
  team: { kind: "string" },
  week: { kind: "int" },
  cutoffUtc: { kind: "date" },
  offenseRating: { kind: "number" },
  offenseVariance: { kind: "number" },
  defenseRating: { kind: "number" },
  defenseVariance: { kind: "number" },
  overallRating: { kind: "number" },
  overallVariance: { kind: "number" },
};

const OPTIONAL_NUMBER: Field = { kind: "number", nullable: true };

export const PREDICTION_GAME_SPEC: RowSpec = {
  gameId: { kind: "int" },
  week: { kind: "int" },
  startDate: { kind: "date" },
  homeTeam: { kind: "string" },
  awayTeam: { kind: "string" },
  homeTeamSpreadLine: OPTIONAL_NUMBER,
  totalLine: OPTIONAL_NUMBER,
  predictedSpread: OPTIONAL_NUMBER,
  predictedTotal: OPTIONAL_NUMBER,
  spreadLean: { kind: SPREAD_LEAN, nullable: true },
  totalLean: { kind: TOTAL_LEAN, nullable: true },
  edgeSpread: OPTIONAL_NUMBER,
  edgeTotal: OPTIONAL_NUMBER,
  highConfidence: { kind: "boolean" },
  spreadResult: { kind: GRADE, nullable: true },
  totalResult: { kind: GRADE, nullable: true },
};

export const PERFORMANCE_DETAIL_SPEC: RowSpec = {
  evidenceClass: { kind: { enum: ["replay", "live"] } },
  week: { kind: "int" },
  gameId: { kind: "int" },
  runId: { kind: "string" },
  startDate: { kind: "date" },
  homeTeam: { kind: "string" },
  awayTeam: { kind: "string" },
  predictedSpread: OPTIONAL_NUMBER,
  predictedTotal: OPTIONAL_NUMBER,
  predictedSpreadStdDev: OPTIONAL_NUMBER,
  predictedTotalStdDev: OPTIONAL_NUMBER,
  spreadLean: { kind: SPREAD_LEAN, nullable: true },
  totalLean: { kind: TOTAL_LEAN, nullable: true },
  spreadResult: { kind: GRADE, nullable: true },
  totalResult: { kind: GRADE, nullable: true },
  highConfidence: { kind: "boolean" },
};
