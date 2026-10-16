import assert from "node:assert/strict";
import test from "node:test";
import { eq, getTableName, sql, type SQL } from "drizzle-orm";
import { drizzle } from "drizzle-orm/neon-http";
import { PgDialect } from "drizzle-orm/pg-core";
import * as schema from "./schema.ts";
import { seasonReleaseDb, CHARTS_V1_KEYS, CHART_RELEASE_TABLES, CORE_RELEASE_TABLES, RELEASE_PROJECTIONS } from "./season-release-query.ts";
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
  for (const table of CORE_RELEASE_TABLES) {
    const name = getTableName(schema[table]);
    assert.ok(query.sql.includes(`"${name}" as (`), name);
    assert.ok(query.sql.includes(`"season_release_${name}"`), name);
  }
  assert.equal(query.sql.includes(identity), false);
  assert.equal(query.params.filter((value) => value === identity).length, CORE_RELEASE_TABLES.length + 1);
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

test("missing-projection probe binds the projection names as one text[] parameter", async () => {
  const queries: SQL[] = [];
  const responses = [{ rows: [{ exists: true }] }, { rows: [release] }, { rows: [] }];
  await loadReleaseContext(async (query) => { queries.push(query); return responses.shift(); }, 2026, "preview");
  const rendered = new PgDialect().sqlToQuery(queries[2]);
  assert.match(rendered.sql, /unnest\(\$1::text\[\]\)/);
  assert.equal(rendered.sql.includes("($1,"), false);
  assert.deepEqual(rendered.params, [RELEASE_PROJECTIONS]);
});

test("chart CTEs are added only with charts enabled and bind the same release id", () => {
  const without = seasonReleaseDb(db, "release-a").select().from(schema.games).toSQL();
  const withCharts = seasonReleaseDb(db, "release-a", { charts: true }).select().from(schema.teamSeasonRoster).toSQL();
  for (const key of CHART_RELEASE_TABLES) {
    const name = getTableName(schema[key]);
    assert.equal(without.sql.includes(`"season_release_${name}"`), false, name);
    assert.ok(withCharts.sql.includes(`"${name}" as (`), name);
    assert.ok(withCharts.sql.includes(`"season_release_${name}"`), name);
  }
  assert.equal(withCharts.params.filter((value) => value === "release-a").length, CORE_RELEASE_TABLES.length + CHART_RELEASE_TABLES.length + 1);
  assert.ok(withCharts.params.every((value) => value === "release-a"));
  assert.equal(seasonReleaseDb(db, "release-a", { charts: false }).select().from(schema.games).toSQL().sql, without.sql);
});

test("a chart query shadows the live chart table with the release rows, never the live table", () => {
  const query = seasonReleaseDb(db, "release-a", { charts: true })
    .select({ team: schema.teamAdjustedEpa.team }).from(schema.teamAdjustedEpa).toSQL();
  assert.match(query.sql, /with[\s\S]*"team_adjusted_epa" as \(select[\s\S]* from "season_release_team_adjusted_epa" AS "team_adjusted_epa" WHERE release_id = \$/i);
});

const chartsRelease = { ...release, projection_keys: [...CHARTS_V1_KEYS].reverse(), chart_relations: true };
const resolve = (row: Record<string, unknown>) => loadReleaseContext(executor([{ rows: [{ exists: true }] }, { rows: [row] }, { rows: [] }]), 2026, "preview");

test("chartsAvailable requires the charts_v1 set and every chart relation", async () => {
  assert.equal((await resolve(chartsRelease))?.chartsAvailable, true);
  const chartNames: string[] = CHART_RELEASE_TABLES.map((k) => getTableName(schema[k]));
  const core = CHARTS_V1_KEYS.filter((key) => !chartNames.includes(key));
  assert.equal(core.length, CORE_RELEASE_TABLES.length);
  assert.equal((await resolve({ ...chartsRelease, projection_keys: core }))?.chartsAvailable, false);
  assert.equal((await resolve({ ...chartsRelease, projection_keys: CHARTS_V1_KEYS.slice(1) }))?.chartsAvailable, false);
  assert.equal((await resolve({ ...chartsRelease, projection_keys: [...CHARTS_V1_KEYS, "extra"] }))?.chartsAvailable, false);
  assert.equal((await resolve({ ...chartsRelease, chart_relations: false }))?.chartsAvailable, false);
  assert.equal((await resolve({ ...chartsRelease, chart_relations: null }))?.chartsAvailable, false);
  assert.equal((await resolve(release))?.chartsAvailable, false);
});

test("a core_v1 release still resolves and serves core pages without chart relations", async () => {
  const context = await resolve({ ...release, projection_keys: CORE_RELEASE_TABLES.map((key) => getTableName(schema[key])).sort(), chart_relations: false });
  assert.equal(context?.releaseId, "release-a");
  assert.equal(context?.chartsAvailable, false);
  const query = seasonReleaseDb(db, context!.releaseId).select().from(schema.games).toSQL();
  assert.equal(RELEASE_PROJECTIONS.some((name) => !query.sql.includes(`"${name}"`)), false);
});
