import assert from "node:assert/strict";
import test from "node:test";
import { drizzle } from "drizzle-orm/neon-http";
import * as schema from "./schema.ts";
import { matchupRatingQuery, renderedRatingSource } from "./matchup-rating-query.ts";

test("rating provenance DISTINCT selects its ordering column and preserves pregame scope", () => {
  const kickoff = new Date("2026-10-04T03:59:00Z");
  const query = matchupRatingQuery(drizzle.mock({ schema }), 2026, kickoff, ["Hawai_i", "San Jose State"], "rendered-source").toSQL();
  const selection = query.sql.slice(0, query.sql.indexOf(" from "));
  assert.match(selection, /select distinct/);
  assert.match(selection, /"cutoff_utc"/); // Omitting this caused PostgreSQL 42P10.
  assert.match(query.sql, /"cutoff_utc" <= \$4/);
  assert.match(query.sql, /order by "v5_rating_snapshots"\."cutoff_utc" desc$/);
  assert.match(query.sql, /"source_manifest_sha256" = \$3/);
  assert.deepEqual(query.params, [2026, "current", "rendered-source", kickoff.toISOString(), "Hawai_i", "San Jose State"]);
});


test("competing same-cutoff manifests cannot replace the rendered rating source", () => {
  const teams = ["A", "B"];
  const cutoff = new Date("2026-10-04T00:00:00Z");
  const candidates = ["other-source", "selected-source"].flatMap((sourceManifestSha256) =>
    teams.map((team) => ({ team, sourceManifestSha256, cutoffUtc: cutoff })));
  const rendered = candidates.filter((row) => row.sourceManifestSha256 === "selected-source");
  const source = renderedRatingSource(rendered, teams);
  assert.equal(source, "selected-source");
  const query = matchupRatingQuery(drizzle.mock({ schema }), 2026, cutoff, teams, source!).toSQL();
  assert.equal(query.params[2], "selected-source");
  assert.match(query.sql, /"source_manifest_sha256" = \$3/);
  assert.equal(renderedRatingSource(candidates, teams), null);
  assert.equal(renderedRatingSource(rendered.slice(0, 1), teams), null);
  assert.equal(renderedRatingSource([rendered[0], candidates[1]], teams), null);
});

test("PostgreSQL selects only the rendered manifest when cutoffs tie", {
  skip: !process.env.TEST_DATABASE_URL,
}, async () => {
  const { execFileSync } = await import("node:child_process");
  const url = process.env.TEST_DATABASE_URL!;
  assert.ok(["localhost", "127.0.0.1"].includes(new URL(url).hostname), "integration fixture requires a disposable local database");
  const query = matchupRatingQuery(drizzle.mock({ schema }), 2026,
    new Date("2026-10-04T00:00:00Z"), ["A", "B"], "selected-source").toSQL();
  const parameters = query.params.map((value) => typeof value === "number" ? String(value) : `'${String(value).replaceAll("'", "''")}'`).join(", ");
  const output = execFileSync("psql", [url, "-X", "-q", "-t", "-A", "-v", "ON_ERROR_STOP=1"], {
    encoding: "utf8",
    input: `BEGIN;
CREATE TEMP TABLE v5_rating_snapshots (team text, source_manifest_sha256 text, cutoff_utc timestamptz, season int, snapshot_class text);
INSERT INTO v5_rating_snapshots VALUES
('A', 'other-source', '2026-10-04T00:00:00Z', 2026, 'current'),
('B', 'other-source', '2026-10-04T00:00:00Z', 2026, 'current'),
('A', 'selected-source', '2026-10-04T00:00:00Z', 2026, 'current'),
('B', 'selected-source', '2026-10-04T00:00:00Z', 2026, 'current');
PREPARE provenance AS ${query.sql};
EXECUTE provenance(${parameters});
ROLLBACK;`,
  });
  const rows = output.trim().split("\n");
  assert.equal(rows.length, 2);
  assert.ok(rows.every((row) => row.includes("|selected-source|")));
  assert.deepEqual(rows.map((row) => row.split("|")[0]).sort(), ["A", "B"]);
});
