import assert from "node:assert/strict";
import test from "node:test";
import type { TeamGameRow } from "./charts.ts";
import { gameLogBars } from "./team-game-log.ts";

const row = (over: Partial<TeamGameRow>): TeamGameRow => ({
  week: 1, gameId: 1, team: "Texas", opponent: "Rice", site: "home", pointsFor: 30, pointsAgainst: 10,
  offPlays: 60, offSuccessN: 60, offSuccessSum: 27, offEpaN: 60, offEpaSum: 5,
  defPlays: 50, defSuccessN: 50, defSuccessSum: 15, defEpaN: 50, defEpaSum: -3, ...over,
});

test("gameLogBars derives success rates for the team and its opponent", () => {
  const [bar] = gameLogBars([row({})], ["Texas"]);
  assert.equal(bar.teamSuccess, 0.45);
  assert.equal(bar.opponentSuccess, 0.3);
  assert.deepEqual([bar.pointsFor, bar.pointsAgainst, bar.opponent], [30, 10, "Rice"]);
});

test("gameLogBars keeps only the team's rows, ordered by week", () => {
  const rows = [row({ week: 3, gameId: 3 }), row({ team: "Rice", week: 1, gameId: 1 }), row({ week: 2, gameId: 2 })];
  assert.deepEqual(gameLogBars(rows, ["Texas"]).map((bar) => bar.week), [2, 3]);
});

test("gameLogBars matches either spelling of the team name", () => {
  assert.equal(gameLogBars([row({ team: "Appalachian State" })], ["App State", "Appalachian State"]).length, 1);
});

test("gameLogBars gives a null rate when no plays were counted", () => {
  const [bar] = gameLogBars([row({ offSuccessN: 0, offSuccessSum: 0 })], ["Texas"]);
  assert.equal(bar.teamSuccess, null);
  assert.equal(bar.opponentSuccess, 0.3);
});
