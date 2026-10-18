import assert from "node:assert/strict";
import test from "node:test";
import { isChartsEnabled } from "./charts-gate.ts";

test("Charts require exact opt-in in every environment, including fixtures", () => {
  for (const NODE_ENV of ["development", "production", "test"]) {
    for (const VERCEL_ENV of [undefined, "preview", "production"]) {
      for (const CFB_UI_TEST_MODE of [undefined, "1"]) {
        const env = { NODE_ENV, VERCEL_ENV, CFB_UI_TEST_MODE };
        for (const flag of [undefined, "", "0", "true", "yes", "01", " 1", "1 ", "invalid"]) {
          assert.equal(isChartsEnabled({ ...env, CFB_CHARTS_ENABLED: flag }), false, JSON.stringify({ env, flag }));
        }
        assert.equal(isChartsEnabled({ ...env, CFB_CHARTS_ENABLED: "1" }), true);
      }
    }
  }
});
