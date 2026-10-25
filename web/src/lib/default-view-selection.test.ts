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

// Résumé facts as `resumeFactsByPeriod` derives them from the release's rows.
const RESUME_FACTS = new Map([
  [WEEK_4_CUTOFF.toISOString(), { postWeek: 4, games: 215 }],
  [WEEK_3_CUTOFF.toISOString(), { postWeek: 3, games: 157 }],
]);
const NO_RESUME_FACTS = new Map<string, { postWeek: number; games: number }>();

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

test("default period labels from résumé facts: certified cutoff gets Post-Week label and game count", () => {
  const meta = defaultPeriodForRows([rating("Alabama", WEEK_4_CUTOFF, 1.43)], RESUME_FACTS);
  assert.equal(meta.id, "2026-09-27T14:15:00.000Z");
  assert.equal(meta.label, "Post-Week 4");
  assert.equal(meta.shortLabel, "Week 4");
  assert.equal(meta.postWeek, 4);
  assert.equal(
    meta.description,
    "Frozen ratings after Week 4 games finalized (215 FBS games, weeks 0–4) (active model state).",
  );
  assert.deepEqual(meta.cutoffUtc, WEEK_4_CUTOFF);
});

test("default period labels from résumé facts: week 0 names its single week", () => {
  const cutoff = new Date("2026-09-03T04:00:00.000Z");
  const facts = new Map([[cutoff.toISOString(), { postWeek: 0, games: 8 }]]);
  const meta = defaultPeriodForRows([rating("Alabama", cutoff, 1.1)], facts);
  assert.equal(meta.label, "Post-Week 0");
  assert.match(meta.description, /\(8 FBS games, week 0\)/);
});

test("default period labels from résumé facts: projection-before-selection binds the older label", () => {
  // A newer generation exists in the periods list, but the served rows come
  // from the older selected source. The label must follow the rows.
  const rows = [rating("Alabama", WEEK_3_CUTOFF, 1.37)];
  const meta = defaultPeriodForRows(rows, RESUME_FACTS);
  assert.equal(meta.id, "2026-09-22T14:58:00.000Z");
  assert.equal(meta.label, "Post-Week 3");
  assert.notEqual(meta.id, "2026-09-27T14:15:00.000Z");
});

test("default period labels from résumé facts: qualified id is looked up by source and cutoff", () => {
  const sha = "a".repeat(64);
  const id = sourceQualifiedPeriodId(sha, WEEK_4_CUTOFF);
  const row = { ...rating("Alabama", WEEK_4_CUTOFF, 1.43), sourceManifestSha256: sha };
  const meta = defaultPeriodForRows([row], new Map([[id, { postWeek: 4, games: 215 }]]));
  assert.equal(meta.id, id);
  assert.equal(meta.label, "Post-Week 4");
  assert.equal(meta.sourceManifestSha256, sha);
});

test("default period labels from cutoff date when no résumé facts exist", () => {
  // No table (migration 0028 not applied), no release rows, or a rollback target all
  // arrive as an empty map: the label is the cutoff date and nothing throws.
  const meta = defaultPeriodForRows([rating("Alabama", WEEK_4_CUTOFF, 1.43)], NO_RESUME_FACTS);
  assert.equal(meta.id, "2026-09-27T14:15:00.000Z");
  assert.equal(meta.label, "As of Sep 27, 2026");
  assert.equal(meta.shortLabel, "Sep 27");
  // The label is the Eastern calendar date: 03:00Z is still the evening before.
  assert.equal(defaultPeriodForRows([rating("Alabama", new Date("2026-10-20T03:00:00Z"), 1.4)], NO_RESUME_FACTS).label, "As of Oct 19, 2026");
  assert.equal(meta.postWeek, undefined);
  assert.equal(meta.description, "Frozen team ratings from all evidence available at cutoff (active model state).");
});

test("default period labels from cutoff date for a cutoff with no résumé facts", () => {
  const meta = defaultPeriodForRows([rating("Alabama", UNKNOWN_CUTOFF, 1.4)], RESUME_FACTS);
  assert.equal(meta.id, "2026-10-01T12:00:00.000Z");
  assert.equal(meta.label, "As of Oct 1, 2026");
  assert.equal(meta.postWeek, undefined);
});

test("default period labels: empty rows yield preseason meta", () => {
  const meta = defaultPeriodForRows([], RESUME_FACTS);
  assert.equal(meta.id, "preseason");
  assert.equal(meta.label, "Preseason");
});

test("default branch pairs the served label with served rows by construction", () => {
  const source = readFileSync(new URL("./v5.ts", import.meta.url), "utf8");
  const defaultBranch = source.slice(source.indexOf("// Default, \"current\""));
  assert.match(defaultBranch, /defaultPeriodForRows\(ratings, await readResumePeriodFacts\(season\)\)/);
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
