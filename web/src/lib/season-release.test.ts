import assert from "node:assert/strict";
import test from "node:test";
import { eq, getTableName, sql } from "drizzle-orm";
import { drizzle } from "drizzle-orm/neon-http";
import * as schema from "./schema.ts";
import { seasonReleaseDb, RELEASE_TABLES } from "./season-release-query.ts";
import { createReleaseContextResolver, loadReleaseContext, releaseEnvironment } from "./season-release-context.ts";

const db = drizzle.mock({ schema });
const release = { release_id: "release-a", environment: "preview", season: 2026, active_week: 7, activated_at: "2026-10-14T00:00:00Z" };
const executor = (responses: unknown[]) => async () => {
  assert.ok(responses.length, "unexpected database query");
  return responses.shift();
};

test("all serving relations and immutable run membership use a bound fixed release", () => {
  const identity = "release-'injection";
  const query = seasonReleaseDb(db, identity).select({ gameId: schema.games.gameId })
    .from(schema.games).where(eq(schema.games.season, 2026)).toSQL();
  for (const table of RELEASE_TABLES) {
    const name = getTableName(schema[table]);
    assert.ok(query.sql.includes(`"${name}" as (`), name);
    assert.ok(query.sql.includes(`"season_release_${name}"`), name);
  }
  assert.equal(query.sql.includes(identity), false);
  assert.equal(query.params.filter((value) => value === identity).length, RELEASE_TABLES.length + 1);
  assert.match(query.sql, /public\.prediction_runs/);
  assert.match(query.sql, /SELECT run_id FROM season_release_site_week_selections WHERE release_id = \$/);
});

test("grade and rating correlated subqueries resolve the release CTEs", () => {
  const query = seasonReleaseDb(db, "release-a").select({
    team: schema.v5RatingSnapshots.team,
    grade: sql`(SELECT result FROM prediction_grades pg WHERE pg.run_id = predictions.run_id LIMIT 1)`,
  }).from(schema.v5RatingSnapshots).toSQL();
  assert.match(query.sql, /"prediction_grades" as \(/);
  assert.match(query.sql, /"v5_rating_snapshots" as \(/);
  assert.ok(query.params.every((value) => value === "release-a"));
});

test("legacy query remains unchanged before cutover", () => {
  assert.deepEqual(seasonReleaseDb(db, null).select().from(schema.games).toSQL(), db.select().from(schema.games).toSQL());
});

test("schema absence and no active release are the only legacy fallback conditions", async () => {
  assert.equal(await loadReleaseContext(executor([{ rows: [{ exists: false }] }]), 2026, "preview"), null);
  assert.equal(await loadReleaseContext(executor([{ rows: [{ exists: true }] }, { rows: [] }]), 2026, "preview"), null);
  await assert.rejects(loadReleaseContext(executor([{ rows: [{ exists: true }] }, { rows: [release] }, { rows: [{ name: "season_release_games" }] }]), 2026, "preview"), /missing serving projections/);
  await assert.rejects(loadReleaseContext(executor([{ rows: [{ exists: true }] }, { rows: [release, release] }]), 2026, "preview"), /Multiple active/);
});

test("activation between queries stays pinned within the request and changes next request", async () => {
  let active = release;
  let loads = 0;
  const load = async (season: number, environment: "preview" | "production") => {
    loads++;
    return loadReleaseContext(executor([{ rows: [{ exists: true }] }, { rows: [{ ...active, season, environment }] }, { rows: [] }]), season, environment);
  };
  const request = createReleaseContextResolver(load);
  const first = await request(2026, "preview");
  active = { ...release, release_id: "release-b" };
  const second = await request(2026, "preview");
  assert.strictEqual(first, second);
  assert.equal(loads, 1);
  for (const context of [first, second]) {
    const query = seasonReleaseDb(db, context!.releaseId).select().from(schema.games).toSQL();
    assert.ok(query.params.every((value) => value === "release-a"));
  }
  assert.equal((await createReleaseContextResolver(load)(2026, "preview"))?.releaseId, "release-b");
  assert.equal((await request(2026, "production"))?.releaseId, "release-b");
});

test("environment and season mismatches fail closed", async () => {
  assert.equal(releaseEnvironment({ CFB_ARTIFACT_ENV: "preview" }), "preview");
  assert.equal(releaseEnvironment({ VERCEL_ENV: "preview" }), "preview");
  assert.throws(() => releaseEnvironment({ CFB_ARTIFACT_ENV: "local" }), /preview or production/);
  assert.throws(() => createReleaseContextResolver(async () => null)(NaN, "preview"), /Invalid release season/);
  await assert.rejects(loadReleaseContext(executor([{ rows: [{ exists: true }] }, { rows: [release] }, { rows: [] }]), 2026, "production"), /mismatch/);
});
