import assert from "node:assert/strict";
import test from "node:test";
import { matchupLineage, type MatchupLineageEvidence } from "./matchup-lineage.ts";

const evidence: MatchupLineageEvidence = {
  forecastRunId: "run-1",
  forecastRatingManifestSha256: "rating-a",
  ratingManifestSha256: "rating-a",
  statRatingManifestSha256: "rating-a",
  statMeasurementManifestSha256: "measurement-a",
  publishedMeasurementManifestSha256: "measurement-a",
  requiredStatRows: 4,
  presentStatRows: 4,
  statsUnavailable: false,
};

test("matchup lineage is ready when selected forecast, ratings, and stats agree", () => {
  assert.equal(matchupLineage(evidence).status, "ready");
});

test("missing stat coverage is updating and does not authorize model sections", () => {
  assert.equal(matchupLineage({ ...evidence, presentStatRows: 2 }).status, "updating");
});

test("mismatched publication provenance is unavailable", () => {
  assert.equal(matchupLineage({ ...evidence, statRatingManifestSha256: "rating-old" }).status, "unavailable");
  assert.equal(matchupLineage({ ...evidence, forecastRunId: null }).status, "unavailable");
});
