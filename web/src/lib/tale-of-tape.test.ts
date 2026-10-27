import assert from "node:assert/strict";
import { test } from "node:test";
import { barFraction, buildTapeRows, tapeVerdict } from "./tale-of-tape.ts";
import type { RowEdge, UnitMatchupRow } from "./team-stats.ts";

function row(key: string, o: number | null, d: number | null, edge: RowEdge | null, oc = 138, dc = 138): UnitMatchupRow {
  return {
    key,
    name: key,
    offenseValue: "1",
    offenseRank: o,
    offenseCohort: o === null ? null : oc,
    offenseTied: false,
    defenseValue: "2",
    defenseRank: d,
    defenseCohort: d === null ? null : dc,
    defenseTied: true,
    edge,
    section: "situational",
  };
}
const off: RowEdge = { side: "offense", strength: "strong" };
const def: RowEdge = { side: "defense", strength: "slight" };
const even: RowEdge = { side: "even", strength: null };

test("barFraction scales by the row's own cohort", () => {
  assert.equal(barFraction(1, 138), 1);
  assert.equal(barFraction(138, 138), 0.05);
  assert.equal(barFraction(11, 21), 0.5);
  assert.equal(barFraction(null, 21), null);
  assert.equal(barFraction(5, null), 1 - 4 / 137);
  assert.equal(barFraction(1, 1), 1);
});

test("missing rank gives a non-comparable row with no bars", () => {
  const [eff] = buildTapeRows([row("success_rate", 10, null, null)]);
  assert.equal(eff.edge, null);
  assert.equal(eff.offenseBar, null);
  assert.equal(eff.defenseBar, null);
  assert.equal(eff.offenseRank, 10);
});

test("absent metric row yields placeholders", () => {
  const rows = buildTapeRows([]);
  assert.equal(rows.length, 5);
  assert.equal(rows[0].offenseValue, "—");
  assert.equal(rows[0].edge, null);
});

test("ties and per-side cohorts carry through", () => {
  const [eff] = buildTapeRows([row("success_rate", 3, 3, even, 11, 21)]);
  assert.equal(eff.defenseTied, true);
  assert.equal(eff.offenseTied, false);
  assert.equal(eff.offenseBar, 0.8);
  assert.equal(eff.defenseBar, 0.9);
});

test("verdict counts only compared rows", () => {
  const rows = buildTapeRows([
    row("success_rate", 1, 100, off),
    row("explosive_rate", 1, 100, off),
    row("pts_per_scoring_opp", 50, 50, even),
    row("conv_rate_3rd_4th", null, 50, null),
    row("avg_start_field_pos", 100, 1, def),
  ]);
  assert.deepEqual(tapeVerdict(rows), { kind: "offense", count: 2, compared: 4 });
});

test("verdict defense, split, and all-missing", () => {
  const mk = (edges: (RowEdge | null)[]) =>
    tapeVerdict(
      buildTapeRows(
        ["success_rate", "explosive_rate", "pts_per_scoring_opp", "conv_rate_3rd_4th", "avg_start_field_pos"].map((k, i) =>
          row(k, edges[i] ? 1 : null, 1, edges[i] ?? null),
        ),
      ),
    );
  assert.deepEqual(mk([def, def, off, null, null]), { kind: "defense", count: 2, compared: 3 });
  assert.deepEqual(mk([def, off, null, null, null]), { kind: "split", compared: 2 });
  assert.deepEqual(mk([null, null, null, null, null]), { kind: "none" });
  assert.deepEqual(tapeVerdict(buildTapeRows([])), { kind: "none" });
});
