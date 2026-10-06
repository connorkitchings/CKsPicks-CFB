export type MatchupLineageStatus = "ready" | "updating" | "unavailable";

export interface MatchupLineageEvidence {
  forecastRunId: string | null;
  forecastRatingManifestSha256: string | null;
  ratingManifestSha256: string | null;
  statRatingManifestSha256: string | null;
  statMeasurementManifestSha256: string | null;
  publishedMeasurementManifestSha256: string | null;
  requiredStatRows: number;
  presentStatRows: number;
  statsUnavailable: boolean;
}

export function matchupLineage(evidence: MatchupLineageEvidence): {
  status: MatchupLineageStatus;
  reason: string;
} {
  if (!evidence.forecastRunId || !evidence.forecastRatingManifestSha256) {
    return { status: "unavailable", reason: "Selected forecast provenance is missing." };
  }
  if (evidence.ratingManifestSha256 !== evidence.forecastRatingManifestSha256) {
    return { status: "unavailable", reason: "Forecast and rating snapshots use different published lineages." };
  }
  if (evidence.statsUnavailable) {
    return { status: "unavailable", reason: "Published team statistics failed their data contract." };
  }
  if (evidence.presentStatRows < evidence.requiredStatRows || !evidence.statRatingManifestSha256) {
    return { status: "updating", reason: "Published matchup statistics are still updating." };
  }
  if (
    evidence.statRatingManifestSha256 !== evidence.forecastRatingManifestSha256 ||
    !evidence.statMeasurementManifestSha256 ||
    evidence.statMeasurementManifestSha256 !== evidence.publishedMeasurementManifestSha256
  ) {
    return { status: "unavailable", reason: "Forecast, ratings, and statistics do not share published provenance." };
  }
  return { status: "ready", reason: "Forecast, ratings, and statistics share published provenance." };
}
