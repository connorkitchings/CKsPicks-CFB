import assert from "node:assert/strict";
import test from "node:test";
import { searchTeams } from "./team-search.ts";

test("team finder resolves accents, known aliases and abbreviations to canonical names", () => {
  for (const [query, expected] of [["san jose", "San José State"], ["Connecticut", "UConn"], ["umass", "Massachusetts"], ["hawaii", "Hawai'i"], ["UT San Antonio", "UTSA"], ["TAMU", "Texas A&M"]]) {
    assert.equal(searchTeams(query)[0], expected, query);
  }
});

test("team finder bounds results, prioritizes exact schools and rejects empty/no matches", () => {
  assert.deepEqual(searchTeams("   "), []);
  assert.deepEqual(searchTeams("&'"), []);
  assert.deepEqual(searchTeams("not-a-real-college"), []);
  assert.equal(searchTeams("Michigan")[0], "Michigan");
  assert.equal(searchTeams("state", 3).length, 3);
});
