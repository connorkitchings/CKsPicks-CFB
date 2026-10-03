import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import test from "node:test";
import { isMatchupEnabled } from "./matchup-gate.ts";

test("enabled by default across all environments", () => {
  assert.equal(isMatchupEnabled({ NODE_ENV: "production" }), true);
  assert.equal(isMatchupEnabled({ NODE_ENV: "development" }), true);
  assert.equal(isMatchupEnabled({ NODE_ENV: "production", CFB_UI_TEST_MODE: "1" }), true);
  assert.equal(isMatchupEnabled({ NODE_ENV: "production", CFB_MATCHUP_ENABLED: "1" }), true);
});

test("can be emergency-disabled with CFB_MATCHUP_ENABLED=0", () => {
  assert.equal(isMatchupEnabled({ NODE_ENV: "production", CFB_MATCHUP_ENABLED: "0" }), false);
  assert.equal(isMatchupEnabled({ NODE_ENV: "development", CFB_MATCHUP_ENABLED: "0" }), false);
});


function sourceFiles(dir: URL): URL[] {
  return readdirSync(dir).flatMap((name) => {
    const url = new URL(name, dir);
    if (statSync(url).isDirectory()) return sourceFiles(new URL(`${name}/`, dir));
    return /\.(tsx?|mjs)$/.test(name) && !/\.test\./.test(name) ? [url] : [];
  });
}

test("no page or component links to a team page (team pages are not ready)", () => {
  const offenders = sourceFiles(new URL("../", import.meta.url))
    .filter((url) => !url.pathname.includes("/app/teams/"))
    .filter((url) => /["'`]\/teams\/|href=\{`\/teams/.test(readFileSync(url, "utf8")))
    .map((url) => url.pathname.split("/src/")[1]);
  assert.deepEqual(offenders, []);
});

test("the root layout provides the matchup gate to client cards", () => {
  const layout = readFileSync(new URL("../app/layout.tsx", import.meta.url), "utf8");
  assert.match(layout, /MatchupLinksProvider enabled=\{isMatchupEnabled\(\)\}/);
  const links = readFileSync(new URL("../components/MatchupLinks.tsx", import.meta.url), "utf8");
  assert.match(links, /createContext\(false\)/); // closed unless the server says otherwise
});

test("no page or component links to the GitHub repository (the footer carries no source link)", () => {
  const offenders = sourceFiles(new URL("../", import.meta.url))
    .filter((url) => /github\.com/.test(readFileSync(url, "utf8")))
    .map((url) => url.pathname.split("/src/")[1]);
  assert.deepEqual(offenders, []);
});
