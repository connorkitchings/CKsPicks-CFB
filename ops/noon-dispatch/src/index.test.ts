import assert from "node:assert/strict";
import test from "node:test";
import { dispatchPlan, runDispatch } from "./index.ts";

// 2026-11-15 is a Sunday (EST), 2026-10-25 a Sunday (EDT).
test("dispatchPlan_sunday_noon_edt_closes_week", () => {
  assert.deepEqual(dispatchPlan(new Date("2026-10-25T16:00:00Z")), { mode: "close-week" });
});
test("dispatchPlan_sunday_noon_est_closes_week", () => {
  assert.deepEqual(dispatchPlan(new Date("2026-11-15T17:00:00Z")), { mode: "close-week" });
});
test("dispatchPlan_monday_noon_refreshes_market", () => {
  assert.deepEqual(dispatchPlan(new Date("2026-10-26T16:00:00Z")), { mode: "market-refresh" });
  assert.deepEqual(dispatchPlan(new Date("2026-11-16T17:00:00Z")), { mode: "market-refresh" });
});
test("dispatchPlan_off_hour_cron_firing_is_null", () => {
  assert.equal(dispatchPlan(new Date("2026-10-25T17:00:00Z")), null); // 13:00 EDT
  assert.equal(dispatchPlan(new Date("2026-11-15T16:00:00Z")), null); // 11:00 EST
});
test("dispatchPlan_tuesday_noon_is_null", () => {
  assert.equal(dispatchPlan(new Date("2026-10-27T16:00:00Z")), null);
  assert.equal(dispatchPlan(new Date("2026-11-17T17:00:00Z")), null);
});

const NOON_SUNDAY = new Date("2026-11-15T17:00:00Z");

const VARIABLE_URL =
  "https://api.github.com/repos/connorkitchings/CKsPicks-CFB/actions/variables/CFB_WEEKLY_AUTOMATION_ENABLED";

/** Routes GET variable vs POST dispatch. `variable` is a status or a value; `statuses` are dispatch responses. */
function fakeFetch(statuses: number[], variable: number | string = "true") {
  const calls: { url: string; init: RequestInit }[] = [];
  const dispatches: { url: string; init: RequestInit }[] = [];
  const impl = async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    if (init.method === "GET") {
      if (typeof variable === "number") return new Response(`body-${variable}`, { status: variable });
      return new Response(JSON.stringify({ name: "CFB_WEEKLY_AUTOMATION_ENABLED", value: variable }), { status: 200 });
    }
    dispatches.push({ url, init });
    const status = statuses[dispatches.length - 1] ?? statuses[statuses.length - 1];
    return new Response(status === 204 ? null : `body-${status}`, { status });
  };
  return { calls, dispatches, impl };
}

test("runDispatch_204_sends_explicit_mode_ref_and_headers", async () => {
  const f = fakeFetch([204]);
  assert.equal(await runDispatch(NOON_SUNDAY, "tok", f.impl, 0), "close-week");
  assert.equal(f.dispatches.length, 1);
  assert.equal(f.calls[0].url, VARIABLE_URL);
  assert.equal(f.calls[0].init.method, "GET");
  const { url, init } = f.dispatches[0];
  assert.equal(
    url,
    "https://api.github.com/repos/connorkitchings/CKsPicks-CFB/actions/workflows/weekly-season-update.yml/dispatches",
  );
  assert.equal(init.method, "POST");
  assert.deepEqual(JSON.parse(init.body as string), { ref: "main", inputs: { mode: "close-week" } });
  const h = init.headers as Record<string, string>;
  assert.equal(h.Authorization, "Bearer tok");
  assert.equal(h.Accept, "application/vnd.github+json");
  assert.equal(h["X-GitHub-Api-Version"], "2022-11-28");
});

test("runDispatch_skips_without_calling_github_off_schedule", async () => {
  const f = fakeFetch([204]);
  assert.equal(await runDispatch(new Date("2026-11-17T17:00:00Z"), "tok", f.impl, 0), null);
  assert.equal(f.calls.length, 0);
});

test("runDispatch_403_throws_with_status_and_body_without_token", async () => {
  const f = fakeFetch([403]);
  await assert.rejects(runDispatch(NOON_SUNDAY, "secret-token", f.impl, 0), (err: Error) => {
    assert.match(err.message, /403/);
    assert.match(err.message, /body-403/);
    assert.ok(!err.message.includes("secret-token"));
    return true;
  });
  assert.equal(f.dispatches.length, 1);
});

test("runDispatch_500_then_204_retries_once", async () => {
  const f = fakeFetch([500, 204]);
  assert.equal(await runDispatch(NOON_SUNDAY, "tok", f.impl, 0), "close-week");
  assert.equal(f.dispatches.length, 2);
});

test("runDispatch_persistent_500_throws_after_one_retry", async () => {
  const f = fakeFetch([500, 502]);
  await assert.rejects(runDispatch(NOON_SUNDAY, "tok", f.impl, 0), /502/);
  assert.equal(f.dispatches.length, 2);
});

const quiet = () => {};

test("runDispatch_variable_false_skips_without_dispatch", async () => {
  const f = fakeFetch([204], "false");
  const logs: string[] = [];
  assert.equal(await runDispatch(NOON_SUNDAY, "tok", f.impl, 0, (m) => logs.push(m)), null);
  assert.equal(f.dispatches.length, 0);
  assert.match(logs[0], /not "true"/);
});

test("runDispatch_variable_404_skips_without_dispatch", async () => {
  const f = fakeFetch([204], 404);
  assert.equal(await runDispatch(NOON_SUNDAY, "tok", f.impl, 0, quiet), null);
  assert.equal(f.dispatches.length, 0);
});

test("runDispatch_variable_read_500_skips_without_retry_or_dispatch", async () => {
  const f = fakeFetch([204], 500);
  const logs: string[] = [];
  assert.equal(await runDispatch(NOON_SUNDAY, "secret-token", f.impl, 0, (m) => logs.push(m)), null);
  assert.equal(f.calls.length, 1);
  assert.equal(f.dispatches.length, 0);
  assert.ok(!logs.join("").includes("secret-token"));
});

test("runDispatch_variable_fetch_throws_skips_without_dispatch", async () => {
  const dispatches: string[] = [];
  const impl = async (_url: string, init: RequestInit): Promise<Response> => {
    if (init.method === "GET") throw new TypeError("network down");
    dispatches.push("x");
    return new Response(null, { status: 204 });
  };
  assert.equal(await runDispatch(NOON_SUNDAY, "tok", impl, 0, quiet), null);
  assert.equal(dispatches.length, 0);
});
