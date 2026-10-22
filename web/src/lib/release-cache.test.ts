import assert from "node:assert/strict";
import test from "node:test";
import {
  CACHE_WARN_BYTES, createReleaseCached, decodeCacheValue, encodeCacheValue, pointerCacheKey, releaseCacheKey, RUN_STATE_CACHE, timeBucket,
  type CacheDeps,
} from "./release-cache.ts";
import { requestNow } from "./request-clock.ts";
import type { SeasonReleaseContext } from "./season-release-context.ts";

const context: SeasonReleaseContext = {
  releaseId: "release-a", environment: "preview", season: 2026, activeWeek: 7,
  activatedAt: new Date("2026-10-14T00:00:00Z"), chartSet: "charts_v2",
};

type Call = { keyParts: string[]; options: { tags: string[]; revalidate: number | false } };

/** In-memory stand-in for `unstable_cache`: memoizes by key parts and arguments. */
function harness(env: Record<string, string | undefined>, active: SeasonReleaseContext | null = context, clock = { ms: 0 }) {
  const calls: Call[] = [];
  const warnings: string[] = [];
  const store = new Map<string, string>();
  const deps: CacheDeps = {
    env: () => env,
    now: () => clock.ms,
    getContext: async () => active,
    cache: async (load, keyParts, options) => {
      calls.push({ keyParts, options });
      return async (...args) => {
        const key = JSON.stringify([keyParts, args]);
        if (!store.has(key)) store.set(key, await load(...args));
        return store.get(key)!;
      };
    },
    warn: (message) => warnings.push(message),
  };
  return { releaseCached: createReleaseCached(deps), calls, warnings };
}

test("the codec round-trips Date and Map, nested and invalid", () => {
  const value = {
    when: new Date("2026-10-14T12:00:00Z"),
    ranks: new Map([["Ohio State", 1], ["Texas", 2]]),
    nested: [{ at: new Date("2026-09-01T00:00:00Z"), byWeek: new Map([[3, { day: new Date("2026-09-20T00:00:00Z") }]]) }],
    none: null,
    text: "plain",
    broken: new Date(NaN),
  };
  const back = decodeCacheValue<typeof value>(encodeCacheValue(value));
  assert.ok(back.when instanceof Date);
  assert.equal(back.when.toISOString(), "2026-10-14T12:00:00.000Z");
  assert.ok(back.ranks instanceof Map);
  assert.deepEqual([...back.ranks], [["Ohio State", 1], ["Texas", 2]]);
  assert.ok(back.nested[0].byWeek.get(3)!.day instanceof Date);
  assert.equal(back.nested[0].at.getTime(), Date.parse("2026-09-01T00:00:00Z"));
  assert.equal(back.none, null);
  assert.equal(back.text, "plain");
  assert.ok(Number.isNaN(back.broken.getTime()));
});

test("the key carries loader, deployment, environment, release, chart set and arguments", () => {
  const key = releaseCacheKey("getGamesForWeek", { VERCEL_DEPLOYMENT_ID: "dpl_1" }, context, [2026, 7]);
  assert.deepEqual(key, ["getGamesForWeek", "dpl_1", "preview", "release-a", "charts_v2", "[2026,7]"]);
  assert.equal(releaseCacheKey("x", {}, { ...context, chartSet: null }, [])[1], "local");
  assert.equal(releaseCacheKey("x", {}, { ...context, chartSet: null }, [])[4], "none");
  const other = releaseCacheKey("getGamesForWeek", { VERCEL_DEPLOYMENT_ID: "dpl_1" }, { ...context, releaseId: "release-b" }, [2026, 7]);
  assert.notDeepEqual(other, key);
});

test("a release-scoped call is cached, tagged by release, and decoded back to Date and Map", async () => {
  const { releaseCached, calls } = harness({ VERCEL_DEPLOYMENT_ID: "dpl_1" });
  let loads = 0;
  const loader = releaseCached("slate", async (season: number) => {
    loads++;
    return { season, at: new Date("2026-10-14T00:00:00Z"), ranks: new Map([["Texas", 2]]) };
  });
  const first = await loader(2026);
  const second = await loader(2026);
  assert.equal(loads, 1);
  assert.ok(first.at instanceof Date && second.ranks instanceof Map);
  assert.deepEqual(calls[0].options, { tags: ["release:release-a"], revalidate: false });
  assert.equal(calls[0].keyParts[3], "release-a");
});

test("run-state loaders cap their entries at one hour", async () => {
  const { releaseCached, calls } = harness({});
  await releaseCached("runs", async (season: number) => season, RUN_STATE_CACHE)(2026);
  assert.equal(calls[0].options.revalidate, 3600);
});

test("test mode and the kill switch bypass the cache entirely", async () => {
  for (const env of [{ CFB_UI_TEST_MODE: "1" }, { CFB_DATA_CACHE: "0" }]) {
    const { releaseCached, calls } = harness(env);
    let loads = 0;
    const loader = releaseCached("slate", async (season: number) => { loads++; return season; });
    await loader(2026);
    await loader(2026);
    assert.equal(loads, 2, JSON.stringify(env));
    assert.equal(calls.length, 0);
  }
  const { releaseCached, calls } = harness({ CFB_DATA_CACHE: "1" });
  await releaseCached("slate", async (season: number) => season)(2026);
  assert.equal(calls.length, 1);
});

test("a request with no release is never cached", async () => {
  const { releaseCached, calls } = harness({}, null);
  let loads = 0;
  const loader = releaseCached("slate", async (season: number) => { loads++; return season; });
  await loader(2026);
  await loader(2026);
  assert.equal(loads, 2);
  assert.equal(calls.length, 0);
});

test("a failing loader is not stored", async () => {
  const { releaseCached } = harness({});
  let attempts = 0;
  const loader = releaseCached("flaky", async (season: number) => {
    if (++attempts === 1) throw new Error("db down");
    return season;
  });
  await assert.rejects(loader(2026), /db down/);
  assert.equal(await loader(2026), 2026);
});

test("an oversized entry is logged", async () => {
  const { releaseCached, warnings } = harness({});
  await releaseCached("big", async () => "x".repeat(CACHE_WARN_BYTES + 1))();
  assert.equal(warnings.length, 1);
  assert.match(warnings[0], /big/);
});

test("time-capped entries carry a bucket in the key; immutable ones do not", async () => {
  const clock = { ms: 0 };
  const { releaseCached, calls } = harness({}, context, clock);
  const mutable = releaseCached("runs", async (season: number) => season, RUN_STATE_CACHE);
  const immutable = releaseCached("games", async (season: number) => season);
  await mutable(2026);
  await immutable(2026);
  assert.equal(calls[0].keyParts.at(-1), "bucket:0");
  assert.equal(calls[1].keyParts.length, 6);
  assert.ok(!calls[1].keyParts.some((part) => part.startsWith("bucket:")));
  assert.deepEqual(calls[0].options.tags, ["release:release-a"]);
});

test("a new bucket is a cache miss that reloads; the same bucket hits", async () => {
  const clock = { ms: 0 };
  const { releaseCached, calls } = harness({}, context, clock);
  let loads = 0;
  const loader = releaseCached("runs", async (season: number) => ++loads + season * 0, RUN_STATE_CACHE);
  await loader(2026);
  clock.ms = 3599_000;
  await loader(2026);
  assert.equal(loads, 1);
  clock.ms = 3600_000;
  assert.equal(await loader(2026), 2);
  assert.notDeepEqual(calls[0].keyParts, calls[2].keyParts);
  assert.deepEqual(calls[0].keyParts, calls[1].keyParts);
  assert.deepEqual(calls[2].options.tags, calls[0].options.tags);
});

test("the pointer key buckets by its ttl and keeps a constant tag-independent prefix", () => {
  const key = (ms: number) => pointerCacheKey("release-pointer", { VERCEL_DEPLOYMENT_ID: "d" }, "preview", 2026, ms, 60);
  assert.deepEqual(key(59_999), ["release-pointer", "d", "preview", "2026", "bucket:0"]);
  assert.deepEqual(key(0), key(59_999));
  assert.notDeepEqual(key(60_000), key(59_999));
  assert.equal(timeBucket(120_000, 60), 2);
});

test("team loaders key on the resolved names", async () => {
  const { releaseCached, calls } = harness({});
  const loader = releaseCached("getTeamGames", async (season: number, team: string) => `${season}${team}`, RUN_STATE_CACHE);
  await loader(2026, "San José State");
  assert.equal(calls[0].keyParts[5], JSON.stringify([2026, "San José State"]));
});

/** Stand-in for React `cache()`: memoizes per "request", reset by `newRequest()`. */
function requestScope(clock: { ms: number }) {
  let pinned: number | undefined;
  return { now: () => (pinned ??= clock.ms), newRequest: () => { pinned = undefined; } };
}

/** Harness whose clock is either pinned per request or read fresh on every call. */
function boundaryHarness(pin: boolean) {
  const clock = { ms: 0 };
  const scope = requestScope(clock);
  const calls: Call[] = [];
  const store = new Map<string, string>();
  const deps: CacheDeps = {
    env: () => ({}),
    now: pin ? scope.now : () => clock.ms,
    getContext: async () => context,
    cache: async (load, keyParts, options) => {
      calls.push({ keyParts, options });
      return async (...args) => {
        const key = JSON.stringify([keyParts, args]);
        if (!store.has(key)) store.set(key, await load(...args));
        return store.get(key)!;
      };
    },
    warn: () => {},
  };
  const releaseCached = createReleaseCached(deps);
  let state = "old";
  const requestMemo = new Map<string, Promise<unknown>>();
  const getRun = releaseCached("getRunForWeek", async (season: number) => `${state}${season * 0 || ""}`, RUN_STATE_CACHE);
  const getGames = releaseCached("getGamesForWeek", async (season: number) => `games(${await memoRun()})${season * 0 || ""}`, RUN_STATE_CACHE);
  const memoRun = () => {
    if (!requestMemo.has("run")) requestMemo.set("run", getRun(2026));
    return requestMemo.get("run") as Promise<string>;
  };
  return {
    clock, calls, setState: (next: string) => { state = next; },
    newRequest: () => { scope.newRequest(); requestMemo.clear(); },
    /** Loader A reads at `startMs`; loader B (depending on A's memoized output) reads at `endMs`. */
    request: async (startMs: number, endMs: number) => {
      clock.ms = startMs;
      const run = await memoRun();
      clock.ms = endMs;
      const games = await getGames(2026);
      return { run, games };
    },
  };
}

test("a request straddling a bucket boundary uses one bucket for every loader", async () => {
  const h = boundaryHarness(true);
  await h.request(3600_000 - 1, 3600_000 + 1);
  const buckets = h.calls.map((call) => call.keyParts.at(-1));
  assert.deepEqual(buckets, ["bucket:0", "bucket:0"]);
  // A later request, after the boundary, uses the new bucket and blocks on a fresh read.
  h.setState("frozen");
  h.newRequest();
  const result = await h.request(3600_000 + 5, 3600_000 + 6);
  assert.equal(h.calls.at(-1)!.keyParts.at(-1), "bucket:1");
  assert.equal(result.run, "frozen");
  assert.equal(result.games, "games(frozen)");
});

test("without a pinned clock the same request mixes buckets (failure mode)", async () => {
  const h = boundaryHarness(false);
  await h.request(3600_000 - 1, 3600_000 + 1);
  const buckets = h.calls.map((call) => call.keyParts.at(-1));
  assert.deepEqual(buckets, ["bucket:0", "bucket:1"]);
});

test("the production request clock returns epoch milliseconds", () => {
  const before = Date.now();
  const value = requestNow();
  assert.ok(value >= before && value <= Date.now());
});
