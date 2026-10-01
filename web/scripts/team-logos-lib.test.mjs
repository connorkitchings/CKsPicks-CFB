import assert from "node:assert/strict";
import test from "node:test";
import {
  assetPath,
  buildGeneratedTs,
  buildManifest,
  espnDarkUrl,
  parseTeams,
} from "./team-logos-lib.mjs";

test("parseTeams uses CFBD logos and derives the dark variant", () => {
  const [t] = parseTeams([
    { id: 130, school: "Michigan", logos: ["https://a.espncdn.com/i/teamlogos/ncaa/500/130.png"] },
  ]);
  assert.equal(t.id, 130);
  assert.equal(t.usedFallback, false);
  assert.equal(t.dark, "https://a.espncdn.com/i/teamlogos/ncaa/500-dark/130.png");
});

test("parseTeams falls back to ESPN when logos are missing and skips bad rows", () => {
  const teams = parseTeams([
    { id: 2, school: "Auburn", logos: [] },
    { id: "x", school: "Bad" },
    { id: 3, school: "" },
    { id: 2, school: "Auburn dup" },
  ]);
  assert.equal(teams.length, 1);
  assert.equal(teams[0].usedFallback, true);
  assert.equal(teams[0].light, "https://a.espncdn.com/i/teamlogos/ncaa/500/2.png");
});

test("parseTeams rejects a non-array response", () => {
  assert.throws(() => parseTeams({ error: "x" }));
});

test("espnDarkUrl is null for non-ESPN urls", () => {
  assert.equal(espnDarkUrl("https://example.com/a.png"), null);
});

test("assetPath, manifest and generated map are deterministic", () => {
  assert.equal(assetPath("sm", "dark", 130), "sm/dark/130.webp");
  const entries = [
    { id: 2, school: "Auburn", sources: {}, darkFallbackToLight: false, files: {} },
    { id: 1, school: "Alabama", sources: {}, darkFallbackToLight: true, files: {} },
  ];
  assert.deepEqual(Object.keys(buildManifest(entries, "2026-10-01").teams), ["1", "2"]);
  const ts = buildGeneratedTs(entries);
  assert.ok(ts.indexOf('"Alabama": 1') < ts.indexOf('"Auburn": 2'));
});
