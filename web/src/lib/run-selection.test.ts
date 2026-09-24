import assert from "node:assert/strict";
import test from "node:test";

import { isSelectableRun, selectsV5 } from "./run-selection.ts";

test("V5 runs render only with a truthful evidence class and published state", () => {
  assert.equal(isSelectableRun({ modelId: "v5-possession-ppp-rho060-exposure", evidenceClass: "replay", state: "scored" }), true);
  assert.equal(isSelectableRun({ modelId: "v5-possession-ppp-rho060-exposure", evidenceClass: "live", state: "published" }), true);
  assert.equal(isSelectableRun({ modelId: "v5-possession-ppp-rho060-exposure", evidenceClass: "pending", state: "frozen" }), true);
});

test("V5 runs fail closed on preview state or missing evidence", () => {
  assert.equal(isSelectableRun({ modelId: "v5-possession-ppp-rho060-exposure", evidenceClass: "replay", state: "preview" }), false);
  assert.equal(isSelectableRun({ modelId: "v5-possession-ppp-rho060-exposure", evidenceClass: null, state: "scored" }), false);
  assert.equal(isSelectableRun({ modelId: "v5-possession-ppp-rho060-exposure", evidenceClass: "missed", state: "scored" }), false);
  assert.equal(isSelectableRun({ modelId: null, evidenceClass: "replay", state: "scored" }), false);
});

test("legacy V4 fallback renders only as a complete published run", () => {
  assert.equal(isSelectableRun({ modelId: "week0-2026-v4-strict-20260818-r2", evidenceClass: "legacy", state: "frozen" }), true);
  assert.equal(isSelectableRun({ modelId: "week0-2026-v4-strict-20260818-r2", evidenceClass: "legacy", state: "preview" }), false);
  assert.equal(isSelectableRun({ modelId: "week0-2026-v4-strict-20260818-r2", evidenceClass: null, state: "frozen" }), false);
});

test("non-V5 runs without legacy evidence never render as fallback", () => {
  assert.equal(isSelectableRun({ modelId: "week0-2026-v4-strict-20260818-r2", evidenceClass: "pending", state: "scored" }), false);
  assert.equal(isSelectableRun({ modelId: "v6-future", evidenceClass: "live", state: "scored" }), false);
});

test("banner gating keys on the V5 model prefix", () => {
  assert.equal(selectsV5("v5-possession-ppp-rho060-exposure"), true);
  assert.equal(selectsV5("week0-2026-v4-strict-20260818-r2"), false);
  assert.equal(selectsV5(null), false);
  assert.equal(selectsV5(undefined), false);
  assert.equal(selectsV5(""), false);
});
