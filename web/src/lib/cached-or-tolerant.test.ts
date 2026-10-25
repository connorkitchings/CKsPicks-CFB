import assert from "node:assert/strict";
import test from "node:test";
import { createCachedOrTolerant, degradedScope, SwallowedReadError } from "./cached-or-tolerant.ts";

const S = degradedScope({ environment: "production", season: 2026, releaseId: "r1", chartSet: "charts_v2" });

function harness() {
  let clock = 0;
  const calls = { cached: 0, tolerant: 0 };
  const run = createCachedOrTolerant(1000, () => clock);
  return { calls, run, advance: (ms: number) => { clock += ms; } };
}

test("healthy path uses the cached loader only", async () => {
  const { calls, run } = harness();
  const cached = async (n: number) => { calls.cached++; return `ok${n}`; };
  const tolerant = async (n: number) => { calls.tolerant++; return `degraded${n}`; };
  assert.equal(await run(S, cached, tolerant, 1), "ok1");
  assert.equal(calls.tolerant, 0);
});

test("degraded path runs the tolerant loader once per window, then retries strict", async () => {
  const { calls, run, advance } = harness();
  let healthy = false;
  const cached = async (n: number) => {
    calls.cached++;
    if (!healthy) throw new SwallowedReadError(new Error("db down"));
    return `ok${n}`;
  };
  const tolerant = async (n: number) => { calls.tolerant++; return `degraded${n}`; };
  assert.equal(await run(S, cached, tolerant, 1), "degraded1");
  assert.equal(await run(S, cached, tolerant, 1), "degraded1");
  assert.equal(await run(S, cached, tolerant, 1), "degraded1");
  assert.deepEqual(calls, { cached: 1, tolerant: 1 });
  assert.equal(await run(S, cached, tolerant, 2), "degraded2");
  assert.deepEqual(calls, { cached: 2, tolerant: 2 });
  healthy = true;
  advance(1001);
  assert.equal(await run(S, cached, tolerant, 1), "ok1");
});

test("required-data errors still propagate and are not remembered", async () => {
  const { run } = harness();
  let fail = true;
  const cached = async () => { if (fail) throw new Error("required"); return "ok"; };
  const tolerant = async () => "degraded";
  await assert.rejects(run(S, cached, tolerant), /required/);
  fail = false;
  assert.equal(await run(S, cached, tolerant), "ok");
});

test("a failing tolerant loader is not remembered", async () => {
  const { calls, run } = harness();
  const cached = async () => { throw new SwallowedReadError(new Error("x")); };
  const tolerant = async () => { calls.tolerant++; throw new Error("boom"); };
  await assert.rejects(run(S, cached, tolerant), /boom/);
  await new Promise((r) => setImmediate(r));
  await assert.rejects(run(S, cached, tolerant), /boom/);
  assert.equal(calls.tolerant, 2);
});

const scopeOf = (environment: string, releaseId: string, chartSet: string | null = "charts_v2") =>
  degradedScope({ environment, season: 2026, releaseId, chartSet });

function degradedLoaders() {
  const calls = { cached: 0, tolerant: 0 };
  return {
    calls,
    cached: async () => { calls.cached++; throw new SwallowedReadError(new Error("down")); },
    tolerant: async () => `degraded${++calls.tolerant}`,
  };
}

test("scope is the environment, season, release id and chart set", () => {
  assert.equal(scopeOf("production", "r1"), '["production",2026,"r1","charts_v2"]');
  assert.equal(degradedScope({ environment: "preview", season: 2025, releaseId: "r2", chartSet: null }), '["preview",2025,"r2","none"]');
  assert.equal(degradedScope(null), null);
});

test("activation: a result remembered under the old release is not served for the new one", async () => {
  const { run } = harness();
  const { calls, cached, tolerant } = degradedLoaders();
  assert.equal(await run(scopeOf("production", "r1"), cached, tolerant), "degraded1");
  assert.equal(await run(scopeOf("production", "r2"), cached, tolerant), "degraded2");
  assert.equal(await run(scopeOf("production", "r1", "charts_v1"), cached, tolerant), "degraded3");
  assert.equal(calls.tolerant, 3);
});

test("rollback: returning to the old release reuses only an unexpired entry of that release", async () => {
  const { run, advance } = harness();
  const { calls, cached, tolerant } = degradedLoaders();
  const old = scopeOf("production", "r1");
  const next = scopeOf("production", "r2");
  assert.equal(await run(old, cached, tolerant), "degraded1");
  assert.equal(await run(next, cached, tolerant), "degraded2");
  assert.equal(await run(old, cached, tolerant), "degraded1"); // still inside the window, same identity
  advance(1001);
  assert.equal(await run(old, cached, tolerant), "degraded3"); // expired: strict retried, no resurrection
  assert.equal(calls.cached, 3);
});

test("environments never share a remembered result", async () => {
  const { run } = harness();
  const { cached, tolerant } = degradedLoaders();
  assert.equal(await run(scopeOf("production", "r1"), cached, tolerant), "degraded1");
  assert.equal(await run(scopeOf("preview", "r1"), cached, tolerant), "degraded2");
  assert.equal(await run(scopeOf("production", "r1"), cached, tolerant), "degraded1");
});

test("same release: tolerant loader runs once within the window, strict retried after expiry", async () => {
  const { run, advance } = harness();
  const { calls, cached, tolerant } = degradedLoaders();
  await run(S, cached, tolerant);
  advance(999);
  await run(S, cached, tolerant);
  assert.deepEqual(calls, { cached: 1, tolerant: 1 });
  advance(2);
  await run(S, cached, tolerant);
  assert.deepEqual(calls, { cached: 2, tolerant: 2 });
});

test("no active release bypasses remembering: strict then tolerant every time", async () => {
  const { run } = harness();
  const { calls, cached, tolerant } = degradedLoaders();
  assert.equal(await run(null, cached, tolerant), "degraded1");
  assert.equal(await run(null, cached, tolerant), "degraded2");
  assert.deepEqual(calls, { cached: 2, tolerant: 2 });
});

test("no active release: required-data and tolerant failures surface", async () => {
  const { run } = harness();
  await assert.rejects(run(null, async () => { throw new Error("required"); }, async () => "d"), /required/);
  await assert.rejects(
    run(null, async () => { throw new SwallowedReadError(new Error("x")); }, async () => { throw new Error("boom"); }),
    /boom/,
  );
});
