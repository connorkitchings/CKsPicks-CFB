import assert from "node:assert/strict";
import test from "node:test";
import { tiedExistsSql } from "./tie-sql.ts";

for (const table of ["team_season_stats", "team_possession_stats"] as const) {
  test(`tie SQL for ${table} qualifies every outer column and excludes the row itself`, () => {
    const sql = tiedExistsSql(table);
    for (const column of ["season", "as_of_week", "role", "metric", "rank", "team"]) {
      assert.match(sql, new RegExp(`s2\\.${column} (=|<>) ${table}\\.${column}`));
    }
    // Outer references must never be bare identifiers (they would bind to s2).
    assert.doesNotMatch(sql, /(=|<>) "[a-z_]+"/);
    assert.match(sql, /^EXISTS \(/);
    assert.match(sql, /s2\.team <> /);
  });
}
