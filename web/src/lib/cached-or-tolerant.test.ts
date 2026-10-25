import assert from "node:assert/strict";
import test from "node:test";
import { createCachedOrTolerant, SwallowedReadError } from "./cached-or-tolerant.ts";

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
  assert.equal(await run(cached, tolerant, 1), "ok1");
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
  assert.equal(await run(cached, tolerant, 1), "degraded1");
  assert.equal(await run(cached, tolerant, 1), "degraded1");
  assert.equal(await run(cached, tolerant, 1), "degraded1");
  assert.deepEqual(calls, { cached: 1, tolerant: 1 });
  assert.equal(await run(cached, tolerant, 2), "degraded2");
  assert.deepEqual(calls, { cached: 2, tolerant: 2 });
  healthy = true;
  advance(1001);
  assert.equal(await run(cached, tolerant, 1), "ok1");
});

test("required-data errors still propagate and are not remembered", async () => {
  const { run } = harness();
  let fail = true;
  const cached = async () => { if (fail) throw new Error("required"); return "ok"; };
  const tolerant = async () => "degraded";
  await assert.rejects(run(cached, tolerant), /required/);
  fail = false;
  assert.equal(await run(cached, tolerant), "ok");
});

test("a failing tolerant loader is not remembered", async () => {
  const { calls, run } = harness();
  const cached = async () => { throw new SwallowedReadError(new Error("x")); };
  const tolerant = async () => { calls.tolerant++; throw new Error("boom"); };
  await assert.rejects(run(cached, tolerant), /boom/);
  await new Promise((r) => setImmediate(r));
  await assert.rejects(run(cached, tolerant), /boom/);
  assert.equal(calls.tolerant, 2);
});
