import assert from "node:assert/strict";
import test from "node:test";
import { groupGamesByDay, pickWeek } from "./matchup-index.ts";

const game = (gameId: number, iso: string) => ({
  gameId,
  startDate: new Date(iso),
  homeTeam: `H${gameId}`,
  awayTeam: `A${gameId}`,
});

test("groupGamesByDay groups by Eastern calendar day in kickoff order", () => {
  const groups = groupGamesByDay([
    game(3, "2026-10-04T03:59:00Z"), // 11:59 PM EDT Saturday
    game(1, "2026-10-03T16:00:00Z"),
    game(2, "2026-10-03T23:30:00Z"),
    game(4, "2026-10-04T16:00:00Z"), // Sunday
  ]);
  assert.deepEqual(groups.map((g) => g.label), ["Saturday, Oct 3", "Sunday, Oct 4"]);
  assert.deepEqual(groups[0].games.map((g) => g.gameId), [1, 2, 3]);
  assert.deepEqual(groups[1].games.map((g) => g.gameId), [4]);
});

test("groupGamesByDay is empty for no games and does not mutate its input", () => {
  assert.deepEqual(groupGamesByDay([]), []);
  const input = [game(2, "2026-10-03T23:00:00Z"), game(1, "2026-10-03T16:00:00Z")];
  groupGamesByDay(input);
  assert.deepEqual(input.map((g) => g.gameId), [2, 1]);
});

test("pickWeek prefers a valid request, then the fallback, then the latest week", () => {
  assert.equal(pickWeek("3", [0, 1, 2, 3, 4, 5], 5), 3);
  assert.equal(pickWeek("9", [0, 1, 2, 3, 4, 5], 5), 5);
  assert.equal(pickWeek("x", [0, 1, 2], 7), 2);
  assert.equal(pickWeek(undefined, [], 5), null);
});
