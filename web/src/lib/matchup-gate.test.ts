import assert from "node:assert/strict";
import test from "node:test";
import { isMatchupEnabled } from "./matchup-gate.ts";

test("closed in production unless the flag is set", () => {
  assert.equal(isMatchupEnabled({ NODE_ENV: "production" }), false);
  assert.equal(isMatchupEnabled({ NODE_ENV: "production", CFB_MATCHUP_ENABLED: "0" }), false);
  assert.equal(isMatchupEnabled({ NODE_ENV: "production", CFB_MATCHUP_ENABLED: "1" }), true);
});

test("open in development and fixture test mode", () => {
  assert.equal(isMatchupEnabled({ NODE_ENV: "development" }), true);
  assert.equal(isMatchupEnabled({ NODE_ENV: "production", CFB_UI_TEST_MODE: "1" }), true);
});
