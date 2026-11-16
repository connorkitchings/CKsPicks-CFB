import assert from "node:assert/strict";
import test from "node:test";
import { searchAnnouncement, searchTeams } from "./team-search.ts";

test("team finder ranks exact matches, then prefix matches, then other substring matches", () => {
  assert.equal(searchTeams("Texas", 50)[0], "Texas", "exact match beats Texas A&M and Texas State");
  const ohio = searchTeams("ohio", 50);
  assert.ok(ohio.indexOf("Ohio") < ohio.indexOf("Ohio State"), "exact before prefix");
  const state = searchTeams("state", 50);
  assert.deepEqual(state, [...state].sort((a, b) => a.localeCompare(b)), "equal ranks stay alphabetical");
});

test("a prefix match outranks an earlier-alphabet substring match", () => {
  const results = searchTeams("mia", 50);
  const prefix = results.filter((team) => team.toLowerCase().startsWith("mia"));
  assert.ok(prefix.length > 0);
  assert.deepEqual(results.slice(0, prefix.length), prefix);
});

test("search announcement reports a count, the no-match message, or nothing when empty", () => {
  assert.equal(searchAnnouncement("  ", 0), "");
  assert.equal(searchAnnouncement("zzz", 0), "No matching team");
  assert.equal(searchAnnouncement("mich", 1), "1 team found");
  assert.equal(searchAnnouncement("mich", 4), "4 teams found");
});

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
