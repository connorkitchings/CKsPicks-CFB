import assert from "node:assert/strict";
import { register } from "node:module";
import test from "node:test";
import { pathToFileURL } from "node:url";

// The route imports through the "@/..." alias, which plain Node cannot resolve.
// Redirect those imports to stubs backed by globalThis.__health so the route's
// own logic runs against controlled release, legacy, and database behavior.
type Harness = {
  release: unknown;
  current: unknown;
  runs: unknown[];
  dbError: Error | null;
  selection: unknown;
};
const harness = globalThis as unknown as { __health: Harness };
const schemaUrl = pathToFileURL(new URL("../../../lib/schema.ts", import.meta.url).pathname).href;
const stubs: Record<string, string> = {
  // "next/server" has no ESM entry under plain Node; Response.json is equivalent here.
  "next/server": `export const NextResponse = { json: (body, init) => Response.json(body, init) };`,
  "@/lib/db": `export * as schema from ${JSON.stringify(schemaUrl)};`,
  "@/lib/publication": `export const publicationScope = { season: 2026, weeks: [1, 2], mode: "test" };`,
  "@/lib/queries": `const h = () => globalThis.__health;
    export const getCurrentWeek = async () => { if (h().dbError) throw h().dbError; return h().current; };
    export const getRunForWeek = async () => h().selection;`,
  "@/lib/season-release": `const h = () => globalThis.__health;
    export const getSeasonReleaseContext = async () => h().release;
    export const getSeasonDb = async () => ({ select: () => ({ from: () => ({ where: () => ({ limit: async () => h().runs }) }) }) });`,
};
const hooks = `export async function resolve(specifier, context, next) {
  const stubs = ${JSON.stringify(stubs)};
  if (stubs[specifier]) return { url: "data:text/javascript," + encodeURIComponent(stubs[specifier]), shortCircuit: true };
  return next(specifier, context);
}`;
register("data:text/javascript," + encodeURIComponent(hooks));

const { GET } = await import("./route.ts");

const runRow = {
  runId: "run-new", season: 2026, week: 8, state: "published",
  expectedGames: 50, predictedGames: 48, linedGames: 47,
  createdAt: new Date("2026-10-14T00:00:00Z"), dataAsOf: new Date("2026-10-13T00:00:00Z"),
  publishedAt: new Date("2026-10-14T01:00:00Z"),
};
const release = { releaseId: "rel-1", environment: "production", season: 2026, activeWeek: 8, activatedAt: new Date() };
const request = (query = "") => ({ nextUrl: new URL(`http://x/api/health${query}`) }) as never;
function setup(over: Partial<Harness>) {
  harness.__health = { release: null, current: null, runs: [], dbError: null, selection: null, ...over };
}

test("active release reports release id and week with its run", async () => {
  setup({
    release,
    current: { season: 2026, week: 8, updatedAt: new Date(), activeRunId: "run-new" },
    runs: [runRow],
  });
  const res = await GET(request());
  const body = await res.json();
  assert.equal(res.status, 200);
  assert.deepEqual(body.activeRelease, { releaseId: "rel-1", season: 2026, week: 8 });
  assert.equal(body.activeRun.runId, "run-new");
  assert.equal(body.activeRun.week, 8);
});

test("no active release falls back to the legacy pointer", async () => {
  setup({
    current: { season: 2026, week: 7, updatedAt: new Date(), activeRunId: "run-old" },
    runs: [{ ...runRow, runId: "run-old", week: 7 }],
  });
  const body = await (await GET(request())).json();
  assert.equal(body.status, "ok");
  assert.equal(body.activeRelease, null);
  assert.equal(body.activeRun.runId, "run-old");
  assert.equal(body.activeRun.week, 7);
});

test("no release and no legacy pointer reports no active run", async () => {
  setup({});
  const body = await (await GET(request())).json();
  assert.equal(body.activeRelease, null);
  assert.equal(body.activeRun, null);
  assert.equal(body.coverage, null);
});

test("selected week compares against the release active run", async () => {
  setup({
    release,
    current: { season: 2026, week: 8, updatedAt: new Date(), activeRunId: "run-new" },
    runs: [runRow],
    selection: { runId: "run-new", modelId: "m", state: "published", evidenceClass: "live", expectedGames: 1, predictedGames: 1, linedGames: 1, createdAt: new Date() },
  });
  const body = await (await GET(request("?season=2026&week=8"))).json();
  assert.equal(body.selectedWeek.agreesWithCurrentWeek, true);
});

test("database failure returns a sanitized 500", async () => {
  setup({ dbError: new Error("secret connection string") });
  const original = console.error;
  console.error = () => {};
  try {
    const res = await GET(request());
    const body = await res.json();
    assert.equal(res.status, 500);
    assert.equal(body.error, "database_unavailable");
    assert.equal(JSON.stringify(body).includes("secret"), false);
  } finally {
    console.error = original;
  }
});

test("partial or out-of-range week request is rejected with 400", async () => {
  setup({});
  assert.equal((await GET(request("?season=2026"))).status, 400);
  assert.equal((await GET(request("?season=2026&week=99"))).status, 400);
});
