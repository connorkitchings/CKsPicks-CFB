import assert from "node:assert/strict";
import test from "node:test";
import {
  buildUnitBreakdown,
  componentId,
  contributionText,
  excludedReasonLabel,
  opponentFor,
  parseComponent,
  pppText,
  priorPercent,
  type ComponentRow,
  type RenderedUnit,
  type ScheduledGame,
  type UnitRole,
} from "./rating-breakdown.ts";

const SNAPSHOT = "run:current:post-week-3:Georgia";
const SOURCE = "a".repeat(64);

const schedule = new Map<number, ScheduledGame>([
  [11, { week: 1, homeTeam: "Georgia", awayTeam: "Clemson" }],
  [12, { week: 2, homeTeam: "Alabama", awayTeam: "Georgia" }],
  [13, { week: 3, homeTeam: "Georgia", awayTeam: "Kentucky" }],
]);

const ev = (gameId: number, week: number, exposure: number, raw: number, adjusted: number, contribution: number, missing: string | null = null) => ({
  game_id: gameId, source_week: week, exposure, raw_ppp: raw, adjusted_ppp: adjusted, adjusted_z: 0, contribution, missing_context_reason: missing,
});

/** Prior 0.25 plus contributions 0.5 + 0.25 + 0.125 = rating 1.125. */
function componentRow(role: UnitRole, overrides: Partial<ComponentRow> = {}): ComponentRow {
  return {
    componentId: componentId(SNAPSHOT, role),
    v5SnapshotId: SNAPSHOT,
    sourceManifestSha256: SOURCE,
    ratingTeam: "Georgia",
    unitRole: role,
    ratingMean: 1.125,
    priorWeight: 0.17,
    priorContribution: 0.25,
    usableExposure: 40,
    completedGames: 3,
    evidence: [
      ev(13, 3, 10, 4.0, 4.0, 0.125, "missing_opponent_context_raw_ppp"),
      ev(11, 1, 10, 2.0, 3.0, 0.5),
      ev(12, 2, 20, 3.0, 3.5, 0.25),
    ],
    excludedObservations: [{ game_id: 12, week: 2, reason: "unresolved_scoring_attribution" }, { game_id: 11, week: 1, reason: "mystery_code" }],
    ...overrides,
  };
}

const rendered = (overrides: Partial<RenderedUnit> = {}): RenderedUnit => ({
  snapshotId: SNAPSHOT, sourceManifestSha256: SOURCE, ratingTeam: "Georgia", rating: 1.125, rank: 5, ...overrides,
});

function build(row: ComponentRow | undefined, options: { role?: UnitRole; rendered?: RenderedUnit | undefined; lookup?: boolean } = {}) {
  const role = options.role ?? "offense";
  const components = new Map(row ? [[row.componentId, row]] : []);
  return buildUnitBreakdown({
    role,
    team: "Georgia",
    rendered: "rendered" in options ? options.rendered : rendered(),
    components: options.lookup ? null : components,
    schedule,
  });
}

function reasonOf(result: ReturnType<typeof build>) {
  assert.equal(result.status, "unavailable");
  return result.status === "unavailable" ? result.reason : null;
}

test("componentId joins the snapshot id and role", () => {
  assert.equal(componentId("snap", "defense"), "snap:defense");
});

test("ready unit: weighted means, sorted rows, and contributions sum to the rating", () => {
  const result = build(componentRow("offense"));
  assert.equal(result.status, "ready");
  if (result.status !== "ready") return;
  assert.deepEqual(result.games.map((game) => game.gameId), [11, 12, 13]);
  assert.deepEqual(result.games.map((game) => game.opponent), ["Clemson", "Alabama", "Kentucky"]);
  assert.equal(result.possessions, 40);
  assert.ok(Math.abs(result.rawPpp! - (2 * 10 + 3 * 20 + 4 * 10) / 40) < 1e-12);
  assert.ok(Math.abs(result.adjustedPpp! - (3 * 10 + 3.5 * 20 + 4 * 10) / 40) < 1e-12);
  const sum = result.priorContribution + result.games.reduce((total, game) => total + game.contribution, 0);
  assert.ok(Math.abs(sum - result.rating) < 1e-9);
  assert.deepEqual(result.games.map((game) => game.missingContext), [false, false, true]);
  assert.equal(result.rank, 5);
});

test("excluded games map known codes and fall back for unknown ones", () => {
  const result = build(componentRow("offense"));
  assert.equal(result.status, "ready");
  if (result.status !== "ready") return;
  assert.deepEqual(result.excluded.map((game) => [game.gameId, game.reason]), [
    [11, "failed a data-quality check"],
    [12, "scoring could not be attributed to a possession"],
  ]);
  assert.equal(excludedReasonLabel(null), "failed a data-quality check");
});

test("defense passes through the stored contributions unchanged", () => {
  const result = build(componentRow("defense", { ratingMean: 1.125 }), { role: "defense" });
  assert.equal(result.status, "ready");
  if (result.status !== "ready") return;
  assert.equal(result.role, "defense");
  assert.equal(result.games[0].contribution, 0.5);
});

test("a jsonb string parses as a fallback", () => {
  const row = componentRow("offense");
  const result = build({ ...row, evidence: JSON.stringify(row.evidence), excludedObservations: JSON.stringify(row.excludedObservations) });
  assert.equal(result.status, "ready");
});

test("preseason-only component is ready with no games and null means", () => {
  const row = componentRow("offense", {
    ratingMean: 0.4, priorWeight: 1, priorContribution: 0.4, usableExposure: 0, completedGames: 0, evidence: [], excludedObservations: [],
  });
  const result = build(row, { rendered: rendered({ rating: 0.4 }) });
  assert.equal(result.status, "ready");
  if (result.status !== "ready") return;
  assert.equal(result.rawPpp, null);
  assert.equal(result.adjustedPpp, null);
  assert.equal(result.games.length, 0);
  assert.equal(priorPercent(result.priorWeight), "100%");
});

test("a rating differing by 1e-9 from the rendered value is a mismatch", () => {
  assert.equal(reasonOf(build(componentRow("offense", { ratingMean: 1.125 + 1e-9 }))), "mismatch");
});

test("a different snapshot id, source, team or role is a mismatch", () => {
  assert.equal(reasonOf(build(componentRow("offense", { v5SnapshotId: "other" }))), "mismatch");
  assert.equal(reasonOf(build(componentRow("offense", { sourceManifestSha256: "b".repeat(64) }))), "mismatch");
  assert.equal(reasonOf(build(componentRow("offense", { ratingTeam: "Florida" }))), "mismatch");
  assert.equal(reasonOf(build(componentRow("offense", { unitRole: "defense" }))), "mismatch");
  assert.equal(reasonOf(build(componentRow("offense"), { rendered: rendered({ sourceManifestSha256: undefined }) })), "mismatch");
});

test("a missing component, rendered row or snapshot id is missing", () => {
  assert.equal(reasonOf(build(undefined)), "missing");
  assert.equal(reasonOf(build(componentRow("offense"), { rendered: undefined })), "missing");
  assert.equal(reasonOf(build(componentRow("offense"), { rendered: rendered({ snapshotId: undefined }) })), "missing");
});

test("a failed lookup is reported as lookup", () => {
  assert.equal(reasonOf(build(componentRow("offense"), { lookup: true })), "lookup");
});

test("rows that fail their own arithmetic or types are invalid", () => {
  const good = componentRow("offense");
  assert.equal(reasonOf(build({ ...good, priorContribution: 0.3 })), "invalid");
  assert.equal(reasonOf(build({ ...good, usableExposure: 41 })), "invalid");
  assert.equal(reasonOf(build({ ...good, completedGames: 2 })), "invalid");
  assert.equal(reasonOf(build({ ...good, priorWeight: Number.NaN })), "invalid");
  assert.equal(reasonOf(build({ ...good, evidence: [{ ...(good.evidence as object[])[0], exposure: "10" }] })), "invalid");
  assert.equal(reasonOf(build({ ...good, evidence: "not json" })), "invalid");
  assert.equal(reasonOf(build({ ...good, excludedObservations: [{ game_id: "x", week: 1, reason: null }] })), "invalid");
  assert.equal(reasonOf(build({ ...good, ratingMean: Number.NaN })), "mismatch");
});

test("parseComponent never coerces numeric strings", () => {
  assert.equal(parseComponent({ ...componentRow("offense"), usableExposure: "40" as unknown as number }), null);
  assert.notEqual(parseComponent(componentRow("offense")), null);
});

test("opponentFor returns the other side, or null when absent or unrelated", () => {
  const game = { homeTeam: "Georgia", awayTeam: "Florida" };
  assert.equal(opponentFor(game, "Georgia"), "Florida");
  assert.equal(opponentFor(game, "Florida"), "Georgia");
  assert.equal(opponentFor(game, "Texas"), null);
  assert.equal(opponentFor(undefined, "Georgia"), null);
});

test("formatters", () => {
  assert.equal(pppText(3.2459), "3.25");
  assert.equal(contributionText(0.1234), "+0.123");
  assert.equal(contributionText(-0.0456), "-0.046");
  assert.equal(priorPercent(0.174), "17%");
});
