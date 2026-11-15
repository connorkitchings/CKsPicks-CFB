import type { PeriodMeta, Rating } from "./rating-periods.ts";
import { competitionRanks } from "./sos-rank.ts";

export type RatingMetric = "overall" | "offense" | "defense";
export const ratingField = { overall: "overallRating", offense: "offenseRating", defense: "defenseRating" } as const;
export type AnalysisRating = Pick<Rating, "team" | "overallRating" | "offenseRating" | "defenseRating" | "wins" | "losses" | "completedGames" | "waa" | "sor" | "sorRank" | "sosPlayedAverage" | "sosRemainingAverage" | "sosFullAverage">;
export interface RatingHistoryPeriod {
  period: Pick<PeriodMeta, "id" | "label" | "postWeek" | "sourceManifestSha256"> & { cutoffUtc?: string };
  ratings: AnalysisRating[];
}
export interface RatingMovement { change: number; rankChange: number }

export function nationalRanks(rows: readonly AnalysisRating[], metric: RatingMetric): Map<string, number> {
  const ranks = competitionRanks(rows.map((row) => row[ratingField[metric]]));
  return new Map(rows.flatMap((row, index) => ranks[index] === null ? [] : [[row.team, ranks[index]!] as const]));
}

/** A weekly change is meaningful only across consecutive certified periods of the same source. */
export function weeklyMovement(current: RatingHistoryPeriod, history: readonly RatingHistoryPeriod[], metric: RatingMetric = "overall"): Map<string, RatingMovement> {
  const week = current.period.postWeek;
  if (week === undefined || week === 0 || !current.period.sourceManifestSha256) return new Map();
  const candidates = history.filter(({ period }) => period.postWeek === week - 1
    && period.sourceManifestSha256 === current.period.sourceManifestSha256
    && period.cutoffUtc && current.period.cutoffUtc && period.cutoffUtc < current.period.cutoffUtc);
  // Ambiguous generations are not resolved by an arbitrary row or source choice.
  if (candidates.length !== 1) return new Map();
  const previous = candidates[0];
  const currentRanks = nationalRanks(current.ratings, metric);
  const previousRanks = nationalRanks(previous.ratings, metric);
  const previousRows = new Map(previous.ratings.map((row) => [row.team, row]));
  return new Map(current.ratings.flatMap((row) => {
    const prior = previousRows.get(row.team);
    const rank = currentRanks.get(row.team);
    const priorRank = previousRanks.get(row.team);
    return prior && rank !== undefined && priorRank !== undefined ? [[row.team, {
      change: row[ratingField[metric]] - prior[ratingField[metric]], rankChange: priorRank - rank,
    }] as const] : [];
  }));
}

/** Prevent future/different-source history from entering a selected-period presentation. */
export function boundedRatingHistory(history: readonly RatingHistoryPeriod[], selected: RatingHistoryPeriod): RatingHistoryPeriod[] {
  if (selected.period.id === "preseason") return [selected];
  const source = selected.period.sourceManifestSha256;
  const cutoff = selected.period.cutoffUtc;
  if (!source || !cutoff) return [selected];
  const byId = new Map(history.filter(({ period }) => period.sourceManifestSha256 === source
    && period.cutoffUtc && period.cutoffUtc <= cutoff).map((item) => [item.period.id, item]));
  byId.set(selected.period.id, selected);
  return [...byId.values()].sort((a, b) => (a.period.cutoffUtc ?? "").localeCompare(b.period.cutoffUtc ?? ""));
}

export function analysisRating(row: Rating): AnalysisRating {
  const { team, overallRating, offenseRating, defenseRating, wins, losses, completedGames, waa, sor, sorRank, sosPlayedAverage, sosRemainingAverage, sosFullAverage } = row;
  return { team, overallRating, offenseRating, defenseRating, wins, losses, completedGames, waa, sor, sorRank, sosPlayedAverage, sosRemainingAverage, sosFullAverage };
}

export function analysisPeriod(meta: PeriodMeta, rows: Rating[]): RatingHistoryPeriod {
  return { period: { id: meta.id, label: meta.postWeek === undefined ? meta.label : `Through Week ${meta.postWeek}`, postWeek: meta.postWeek, sourceManifestSha256: meta.sourceManifestSha256 ?? rows[0]?.sourceManifestSha256, cutoffUtc: meta.cutoffUtc?.toISOString() ?? rows[0]?.cutoffUtc.toISOString() }, ratings: rows.map(analysisRating) };
}
