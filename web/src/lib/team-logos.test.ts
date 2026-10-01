import assert from "node:assert/strict";
import test from "node:test";
import { hasLogo, legacyLogoSrc, logoId, logoSrc, teamInitials } from "./team-logos.ts";

test("unknown team has no v2 logo", () => {
  assert.equal(hasLogo("Nowhere State"), false);
  assert.equal(logoSrc("Nowhere State", "sm", "light"), null);
});

test("known teams resolve to id-keyed light/dark paths", () => {
  assert.equal(logoSrc("Michigan", "sm", "light"), "/logos/v2/sm/light/130.webp");
  assert.equal(logoSrc("Michigan", "lg", "dark"), "/logos/v2/lg/dark/130.webp");
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

test("legacy path still resolves aliases", () => {
  assert.equal(legacyLogoSrc("UConn"), "/logos/Connecticut.png");
});

test("teamInitials", () => {
  assert.equal(teamInitials("Ohio State"), "OS");
  assert.equal(teamInitials("Tulane"), "TU");
  assert.equal(teamInitials(""), "?");
});
