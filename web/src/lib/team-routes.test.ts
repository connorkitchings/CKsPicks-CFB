import assert from "node:assert/strict";
import test from "node:test";
import { canonicalTeamSegment, resolveTeam, teamHref } from "./team-routes.ts";
import { TEAM_LOGO_MAP } from "./teams.ts";

test("teamHref encodes accents, ampersands and spaces", () => {
  assert.equal(teamHref("Texas A&M"), "/teams/Texas_A%26M");
  assert.equal(teamHref("San José State"), "/teams/San_Jos%C3%A9_State");
});

test("a normal team resolves to itself for games and ratings", () => {
  assert.deepEqual(resolveTeam("Texas"), { gameName: "Texas", ratingName: "Texas" });
  assert.deepEqual(resolveTeam("Texas%20A%26M"), { gameName: "Texas A&M", ratingName: "Texas A&M" });
});

test("underscores stand for spaces, and %20 links still resolve", () => {
  assert.deepEqual(resolveTeam("Texas_A%26M"), { gameName: "Texas A&M", ratingName: "Texas A&M" });
  assert.deepEqual(resolveTeam("San_Jos%C3%A9_State"), resolveTeam("San José State"));
  assert.deepEqual(resolveTeam("Middle_Tennessee"), resolveTeam("Middle Tennessee"));
  assert.equal(resolveTeam("Not_A_School"), null);
});

test("legacy-name teams resolve from either spelling", () => {
  const cases: [string, string, string][] = [
    ["San José State", "San José State", "San Jose State"],
    ["San Jose State", "San José State", "San Jose State"],
    ["Hawai'i", "Hawai'i", "Hawai_i"],
    ["Hawai_i", "Hawai'i", "Hawai_i"],
    ["App State", "App State", "Appalachian State"],
    ["Appalachian State", "App State", "Appalachian State"],
    ["UMass", "Massachusetts", "UMass"],
    ["Massachusetts", "Massachusetts", "UMass"],
    ["Connecticut", "UConn", "Connecticut"],
    ["UConn", "UConn", "Connecticut"],
    ["Louisiana Monroe", "UL Monroe", "Louisiana Monroe"],
    ["Sam Houston State", "Sam Houston", "Sam Houston State"],
    ["UT San Antonio", "UTSA", "UT San Antonio"],
    ["Southern Mississippi", "Southern Miss", "Southern Mississippi"],
    ["Florida International", "Florida International", "Florida International"],
  ];
  for (const [segment, gameName, ratingName] of cases) {
    assert.deepEqual(resolveTeam(segment), { gameName, ratingName }, segment);
  }
});

test("alias keys resolve to their school", () => {
  assert.deepEqual(resolveTeam("Hawaii"), { gameName: "Hawai'i", ratingName: "Hawai_i" });
  assert.deepEqual(resolveTeam("Hawai i"), { gameName: "Hawai'i", ratingName: "Hawai_i" });
  assert.deepEqual(resolveTeam("FIU"), { gameName: "Florida International", ratingName: "Florida International" });
});

test("canonicalTeamSegment names the canonical slug only for non-canonical spellings", () => {
  assert.equal(canonicalTeamSegment("Hawaii"), "Hawai'i");
  assert.equal(canonicalTeamSegment("Hawai_i"), "Hawai'i");
  assert.equal(canonicalTeamSegment("San_Jose_State"), "San_Jos%C3%A9_State");
  assert.equal(canonicalTeamSegment("Appalachian_State"), "App_State");
  assert.equal(canonicalTeamSegment("Texas"), null);
  assert.equal(canonicalTeamSegment("Texas%20A%26M"), null);
  assert.equal(canonicalTeamSegment("Texas_A%26M"), null);
  assert.equal(canonicalTeamSegment("Not_A_School"), null);
});

test("every stored rating name resolves to a CFBD name that maps back to it", () => {
  for (const [game, stored] of Object.entries(TEAM_LOGO_MAP)) {
    const fromStored = resolveTeam(stored);
    assert.ok(fromStored, stored);
    assert.equal(fromStored.ratingName, stored);
    assert.equal(TEAM_LOGO_MAP[fromStored.gameName] ?? fromStored.gameName, stored, game);
  }
});

test("unknown or malformed names do not resolve", () => {
  assert.equal(resolveTeam("Nowhere State"), null);
  assert.equal(resolveTeam("%E0%A4%A"), null);
  assert.equal(resolveTeam(""), null);
  assert.equal(resolveTeam("constructor"), null);
});
