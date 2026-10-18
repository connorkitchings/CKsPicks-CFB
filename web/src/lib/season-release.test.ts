import assert from "node:assert/strict";
import test from "node:test";
import { eq, getTableName, sql, type SQL } from "drizzle-orm";
import { drizzle } from "drizzle-orm/neon-http";
import { PgDialect } from "drizzle-orm/pg-core";
import * as schema from "./schema.ts";
import {
  seasonReleaseDb, CHARTS_V1_KEYS, CHART_SETS, CHART_SET_KEYS, CHART_SET_PROJECTIONS, CHART_TABLE_SETS,
  CORE_RELEASE_TABLES, RELEASE_PROJECTIONS, type ChartSet,
} from "./season-release-query.ts";
import {
  chartsAvailable, createReleaseContextResolver, explosivenessAvailable, loadReleaseContext, releaseEnvironment,
  type SeasonReleaseContext,
} from "./season-release-context.ts";

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

const YARDAGE = "season_release_team_game_yardage";
const chartSql = (releaseId: string, chartSet: ChartSet | null) =>
  seasonReleaseDb(db, releaseId, { chartSet }).select().from(schema.teamSeasonRoster).toSQL();

test("chart sets are frozen per version and charts_v1 keeps its recorded keys", () => {
  assert.deepEqual(CHARTS_V1_KEYS, [
    "game_results", "game_venues", "games", "market_quotes", "market_snapshot_quotes", "market_snapshots",
    "matchup_data_publications", "prediction_grades", "prediction_market_selections", "predictions",
    "site_week_selections", "system_stats", "team_adjusted_epa", "team_game_measurements", "team_game_stats",
    "team_possession_adjusted", "team_possession_stats", "team_rating_components", "team_season_roster",
    "team_season_stats", "v5_rating_snapshots",
  ]);
  assert.deepEqual(CHART_SET_KEYS.charts_v2, [...CHARTS_V1_KEYS, "team_game_yardage"].sort());
  assert.deepEqual(CHART_SET_PROJECTIONS.charts_v1, ["season_release_team_season_roster", "season_release_team_game_stats", "season_release_team_adjusted_epa"]);
  assert.deepEqual(CHART_SET_PROJECTIONS.charts_v2, [...CHART_SET_PROJECTIONS.charts_v1, YARDAGE]);
  assert.deepEqual(CHART_TABLE_SETS.charts_v2.slice(0, -1), CHART_TABLE_SETS.charts_v1);
});

test("chart CTEs cover exactly the chart set's tables and bind the same release id", () => {
  const without = seasonReleaseDb(db, "release-a").select().from(schema.games).toSQL();
  for (const chartSet of CHART_SETS) {
    const query = chartSql("release-a", chartSet);
    for (const key of CHART_TABLE_SETS[chartSet]) {
      const name = getTableName(schema[key]);
      assert.equal(without.sql.includes(`"season_release_${name}"`), false, name);
      assert.ok(query.sql.includes(`"${name}" as (`), name);
      assert.ok(query.sql.includes(`"season_release_${name}"`), name);
    }
    assert.equal(query.sql.includes(YARDAGE), chartSet === "charts_v2", chartSet);
    assert.equal(query.params.length, CORE_RELEASE_TABLES.length + CHART_TABLE_SETS[chartSet].length + 1);
    assert.ok(query.params.every((value) => value === "release-a"));
  }
  assert.equal(seasonReleaseDb(db, "release-a", { chartSet: null }).select().from(schema.games).toSQL().sql, without.sql);
});

test("a chart query shadows the live chart table with the release rows, never the live table", () => {
  const query = seasonReleaseDb(db, "release-a", { chartSet: "charts_v2" })
    .select({ team: schema.teamGameYardage.team }).from(schema.teamGameYardage).toSQL();
  assert.match(query.sql, /with[\s\S]*"team_game_yardage" as \(select[\s\S]* from "season_release_team_game_yardage" AS "team_game_yardage" WHERE release_id = \$/i);
});

const v1Release = { ...release, projection_keys: [...CHARTS_V1_KEYS].reverse(), charts_v1_relations: true, charts_v2_relations: null };
const v2Release = { ...release, projection_keys: [...CHART_SET_KEYS.charts_v2].reverse(), charts_v1_relations: true, charts_v2_relations: true };
const resolve = (row: Record<string, unknown>) => loadReleaseContext(executor([{ rows: [{ exists: true }] }, { rows: [row] }, { rows: [] }]), 2026, "preview");
const capabilities = (context: SeasonReleaseContext | null) =>
  [context?.chartSet, chartsAvailable(context!.chartSet), explosivenessAvailable(context!.chartSet)];

test("a retained charts_v1 release without 0027 serves charts without explosiveness", async () => {
  const context = await resolve(v1Release);
  assert.deepEqual(capabilities(context), ["charts_v1", true, false]);
  assert.equal(chartSql(context!.releaseId, context!.chartSet).sql.includes(YARDAGE), false);
});

test("a retained charts_v1 release after 0027 behaves the same: the recorded set governs", async () => {
  const context = await resolve({ ...v1Release, charts_v2_relations: true });
  assert.deepEqual(capabilities(context), ["charts_v1", true, false]);
  assert.equal(chartSql(context!.releaseId, context!.chartSet).sql.includes(YARDAGE), false);
});

test("a charts_v2 release serves explosiveness with the yardage CTE bound to its release id", async () => {
  const context = await resolve(v2Release);
  assert.deepEqual(capabilities(context), ["charts_v2", true, true]);
  const query = chartSql(context!.releaseId, context!.chartSet);
  assert.match(query.sql, /"team_game_yardage" as \(select[\s\S]* from "season_release_team_game_yardage" AS "team_game_yardage" WHERE release_id = \$/i);
  assert.ok(query.params.every((value) => value === "release-a"));
});

test("a charts_v2 release whose yardage relation is missing has no chart set", async () => {
  assert.deepEqual(capabilities(await resolve({ ...v2Release, charts_v2_relations: false })), [null, false, false]);
  assert.deepEqual(capabilities(await resolve({ ...v2Release, charts_v2_relations: null })), [null, false, false]);
});

test("unknown or partial recorded keys, or missing charts_v1 relations, have no chart set", async () => {
  const yardageOnly = [...CHARTS_V1_KEYS.slice(1), "team_game_yardage"];
  for (const projection_keys of [[], CHARTS_V1_KEYS.slice(1), [...CHARTS_V1_KEYS, "extra"], yardageOnly, CHART_SET_KEYS.charts_v2.slice(1)]) {
    assert.equal((await resolve({ ...v2Release, projection_keys }))?.chartSet, null, projection_keys.join(","));
  }
  assert.equal((await resolve({ ...v1Release, charts_v1_relations: false }))?.chartSet, null);
  assert.equal((await resolve({ ...v1Release, charts_v1_relations: null }))?.chartSet, null);
  assert.equal((await resolve(release))?.chartSet, null);
});

test("the resolver probes each chart set's relations as one bound text[] parameter", async () => {
  const queries: SQL[] = [];
  const responses = [{ rows: [{ exists: true }] }, { rows: [v2Release] }, { rows: [] }];
  await loadReleaseContext(async (query) => { queries.push(query); return responses.shift(); }, 2026, "preview");
  const rendered = new PgDialect().sqlToQuery(queries[1]);
  for (const set of CHART_SETS) assert.match(rendered.sql, new RegExp(`AS "${set}_relations"`));
  assert.deepEqual(rendered.params.slice(0, CHART_SETS.length), CHART_SETS.map((set) => CHART_SET_PROJECTIONS[set]));
});

test("one request keeps the release id and chart set even when another release activates", async () => {
  let active: Record<string, unknown> = v1Release;
  const load = async (season: number, environment: "preview" | "production") =>
    loadReleaseContext(executor([{ rows: [{ exists: true }] }, { rows: [{ ...active, season, environment }] }, { rows: [] }]), season, environment);
  const request = createReleaseContextResolver(load);
  const first = await request(2026, "preview");
  active = { ...v2Release, release_id: "release-b" };
  const second = await request(2026, "preview");
  for (const context of [first, second]) {
    assert.deepEqual([context?.releaseId, context?.chartSet], ["release-a", "charts_v1"]);
    const query = chartSql(context!.releaseId, context!.chartSet);
    assert.equal(query.sql.includes(YARDAGE), false);
    assert.ok(query.params.every((value) => value === "release-a"));
  }
  const next = await createReleaseContextResolver(load)(2026, "preview");
  assert.deepEqual([next?.releaseId, next?.chartSet], ["release-b", "charts_v2"]);
});

test("a core_v1 release still resolves and serves core pages without chart relations", async () => {
  const context = await resolve({ ...release, projection_keys: CORE_RELEASE_TABLES.map((key) => getTableName(schema[key])).sort(), charts_v1_relations: false, charts_v2_relations: false });
  assert.equal(context?.releaseId, "release-a");
  assert.equal(context?.chartSet, null);
  const query = seasonReleaseDb(db, context!.releaseId).select().from(schema.games).toSQL();
  assert.equal(RELEASE_PROJECTIONS.some((name) => !query.sql.includes(`"${name}"`)), false);
});
