import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import {
  defaultPeriodForRows,
  ownerSourceForCutoff,
  parseSourceQualifiedPeriodId,
  sourceQualifiedPeriodId,
  type Rating,
} from "./rating-periods.ts";

const WEEK_4_CUTOFF = new Date("2026-09-27T14:15:00.000Z");
const WEEK_3_CUTOFF = new Date("2026-09-22T14:58:00.000Z");
const UNKNOWN_CUTOFF = new Date("2026-10-01T12:00:00.000Z");

function rating(team: string, cutoffUtc: Date, overallRating: number): Rating {
  return {
    team,
    week: 4,
    cutoffUtc,
    offenseRating: overallRating,
    offenseVariance: 0.1,
    defenseRating: overallRating,
    defenseVariance: 0.1,
    overallRating,
    overallVariance: 0.05,
    fallbackReason: null,
  };
}

test("default period derives from served rows: certified cutoff keeps Post-Week label", () => {
  const meta = defaultPeriodForRows([rating("Alabama", WEEK_4_CUTOFF, 1.43)]);
  assert.equal(meta.id, "2026-09-27T14:15:00.000Z");
  assert.equal(meta.label, "Post-Week 4");
  assert.equal(meta.shortLabel, "Week 4");
  assert.equal(meta.postWeek, 4);
  assert.deepEqual(meta.cutoffUtc, WEEK_4_CUTOFF);
});

test("default period derives from served rows: projection-before-selection binds the older label", () => {
  // A newer generation exists in the periods list, but the served rows come
  // from the older selected source. The label must follow the rows.
  const rows = [rating("Alabama", WEEK_3_CUTOFF, 1.37)];
  const meta = defaultPeriodForRows(rows);
  assert.equal(meta.id, "2026-09-22T14:58:00.000Z");
  assert.equal(meta.label, "Post-Week 3");
  assert.notEqual(meta.id, "2026-09-27T14:15:00.000Z");
});

test("default period derives from served rows: unknown cutoff falls back to date label", () => {
  const meta = defaultPeriodForRows([rating("Alabama", UNKNOWN_CUTOFF, 1.4)]);
  assert.equal(meta.id, "2026-10-01T12:00:00.000Z");
  assert.match(meta.label, /As of Oct/);
  assert.equal(meta.postWeek, undefined);
});

test("default period derives from served rows: empty rows yield preseason meta", () => {
  const meta = defaultPeriodForRows([]);
  assert.equal(meta.id, "preseason");
  assert.equal(meta.label, "Preseason");
});

test("default branch pairs the served label with served rows by construction", () => {
  const source = readFileSync(new URL("./v5.ts", import.meta.url), "utf8");
  const defaultBranch = source.slice(source.indexOf("// Default, \"current\""));
  assert.match(defaultBranch, /defaultPeriodForRows\(ratings\)/);
  assert.doesNotMatch(defaultBranch, /generations\[0\]/);
});

test("legacy cutoff links retain their first published source", () => {
  const rows = [
    { sourceManifestSha256: null, createdAt: new Date("2026-09-28T00:00:00Z") },
    { sourceManifestSha256: "sha-B", createdAt: new Date("2026-09-27T15:00:00Z") },
    { sourceManifestSha256: "sha-A", createdAt: new Date("2026-09-27T14:00:00Z") },
  ];
  assert.equal(ownerSourceForCutoff(rows), "sha-A");
});

test("new period links include exact source and cutoff", () => {
  const sha = "a".repeat(64);
  const id = sourceQualifiedPeriodId(sha, WEEK_4_CUTOFF);
  assert.deepEqual(parseSourceQualifiedPeriodId(id), { sourceSha: sha, cutoff: WEEK_4_CUTOFF });
  assert.equal(parseSourceQualifiedPeriodId(WEEK_4_CUTOFF.toISOString()), null);
});

test("owner source resolution: empty or all-null rows yield null (fail closed)", () => {
  assert.equal(ownerSourceForCutoff([]), null);
  assert.equal(
    ownerSourceForCutoff([{ sourceManifestSha256: null, createdAt: new Date() }]),
    null
  );
});

test("frozen backfill is pinned to the cutoff-owning source, null fails closed", () => {
  const source = readFileSync(new URL("./v5.ts", import.meta.url), "utf8");
  assert.match(source, /getPreseasonPriors\(season, ownerSource\)/);
  assert.match(source, /if \(sourceSha === null\) return \[\];/);
});
