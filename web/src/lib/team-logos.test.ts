import assert from "node:assert/strict";
import test from "node:test";
import { hasLogo, logoId, logoSrc, phoneTeamName, teamAbbr, teamInitials } from "./team-logos.ts";
import { TEAM_DISPLAY } from "./team-logos.generated.ts";

test("unknown team has no v2 logo", () => {
  assert.equal(hasLogo("Nowhere State"), false);
  assert.equal(logoSrc("Nowhere State", "sm", "light"), null);
});

test("known teams resolve to id-keyed light/dark paths", () => {
  assert.equal(logoSrc("Michigan", "sm", "light"), "/logos/v2/sm/light/130.webp");
  assert.equal(logoSrc("Michigan", "lg", "dark"), "/logos/v2/lg/dark/130.webp");
});

test("readable primary marks retain team color at every size in both themes", () => {
  for (const [team, id] of [
    ["Tennessee", 2633], ["Clemson", 228], ["Sam Houston", 2534], ["Texas", 251],
    ["North Texas", 249], ["Buffalo", 2084], ["Utah", 254],
  ] as const) {
    for (const size of ["sm", "lg"] as const) {
      for (const theme of ["light", "dark"] as const) {
        assert.equal(logoSrc(team, size, theme), `/logos/v2/${size}/light/${id}.webp`, team);
      }
    }
  }
});

test("darker primary marks retain their dark contrast variants", () => {
  for (const [team, id] of [["Alabama", 333], ["Michigan", 130], ["Duke", 150], ["Temple", 218]] as const) {
    for (const size of ["sm", "lg"] as const) {
      assert.equal(logoSrc(team, size, "dark"), `/logos/v2/${size}/dark/${id}.webp`, team);
    }
  }
});

test("alternate spellings resolve to the same logo as the CFBD name", () => {
  for (const [alias, canonical] of [
    ["Appalachian State", "App State"],
    ["Southern Mississippi", "Southern Miss"],
    ["Hawaii", "Hawai'i"],
    ["Connecticut", "UConn"],
    ["UMass", "Massachusetts"],
  ]) {
    assert.notEqual(logoId(canonical), null, canonical);
    assert.equal(logoId(alias), logoId(canonical), alias);
  }
});

test("teamInitials", () => {
  assert.equal(teamInitials("Ohio State"), "OS");
  assert.equal(teamInitials("Tulane"), "TU");
  assert.equal(teamInitials(""), "?");
});

test("every FBS team has a short, unique abbreviation", () => {
  const abbrs = Object.keys(TEAM_DISPLAY).map((team) => teamAbbr(team));
  for (const abbr of abbrs) assert.match(abbr, /^[A-Z&-]{2,5}$/, abbr);
  assert.equal(new Set(abbrs).size, abbrs.length);
});

test("house abbreviations replace CFBD's, including through an alias", () => {
  assert.equal(teamAbbr("Texas A&M"), "TAMU");
  assert.equal(teamAbbr("Connecticut"), "UCONN");
  assert.equal(teamAbbr("Georgia"), "UGA");
});

test("phones keep short names and abbreviate long ones", () => {
  assert.equal(phoneTeamName("Georgia"), "Georgia");
  assert.equal(phoneTeamName("San José State"), "San José State");
  assert.equal(phoneTeamName("Florida International"), "FIU");
  assert.equal(phoneTeamName("Southern Mississippi"), "USM");
});
