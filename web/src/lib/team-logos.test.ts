import assert from "node:assert/strict";
import test from "node:test";
import { hasLogo, legacyLogoSrc, logoSrc, teamInitials } from "./team-logos.ts";

test("unknown team has no v2 logo (generated map is empty until built)", () => {
  assert.equal(hasLogo("Nowhere State"), false);
  assert.equal(logoSrc("Nowhere State", "sm", "light"), null);
});

test("legacy path still resolves aliases", () => {
  assert.equal(legacyLogoSrc("UConn"), "/logos/Connecticut.png");
});

test("teamInitials", () => {
  assert.equal(teamInitials("Ohio State"), "OS");
  assert.equal(teamInitials("Tulane"), "TU");
  assert.equal(teamInitials(""), "?");
});
