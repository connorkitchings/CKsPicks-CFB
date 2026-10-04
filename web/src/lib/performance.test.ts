import test from "node:test";
import assert from "node:assert/strict";
import { v5PerformanceDetailFixture } from "../test/fixtures/publication.ts";

test("performance detail fixture contains expected summary structure and valid records", () => {
  const { summary, byWeek, gradedGames, weeks } = v5PerformanceDetailFixture;

  assert.equal(summary.classification, "all");
  assert.equal(summary.games, 2);
  assert.equal(summary.evaluated, 2);
  assert.equal(summary.marginMae, 4.5);
  assert.equal(summary.totalMae, 6.0);

  // Spread record assertions
  assert.equal(summary.spread.win, 1);
  assert.equal(summary.spread.loss, 0);
  assert.equal(summary.spread.push, 0);
  assert.equal(summary.spread.winRate, 100);

  // Total record assertions
  assert.equal(summary.total.win, 0);
  assert.equal(summary.total.loss, 1);
  assert.equal(summary.total.push, 0);
  assert.equal(summary.total.winRate, 0);

  // Combined assertions
  assert.equal(summary.combined.win, 1);
  assert.equal(summary.combined.loss, 1);
  assert.equal(summary.combined.push, 0);
  assert.equal(summary.combined.winRate, 50);

  // Weeks mapping
  assert.deepEqual(weeks, [0]);
  assert.ok(byWeek[0]);
  assert.equal(byWeek[0].spread.win, 1);

  // Graded games list
  assert.equal(gradedGames.length, 1);
  const game = gradedGames[0];
  assert.equal(game.gameId, 401000001);
  assert.equal(game.week, 0);
  assert.equal(game.homeTeam, "Texas");
  assert.equal(game.awayTeam, "Ohio State");
  assert.equal(game.spreadResult, "win");
  assert.equal(game.totalResult, "loss");
  assert.equal(game.highConfidence, true);
  assert.equal(game.evidenceClass, "replay");
});

test("win rate calculation excludes pushes from denominator", () => {
  const wins = 8;
  const losses = 4;
  const pushes = 3;
  const decisions = wins + losses;
  const winRate = (wins / decisions) * 100;

  assert.equal(pushes, 3);
  assert.equal(winRate, 66.66666666666666);
  assert.equal(Math.round(winRate * 10) / 10, 66.7);
});

test("accuracyRecord counts pushes but excludes them from the win rate", async () => {
  const { accuracyRecord } = await import("./performance-accuracy.ts");
  const record = accuracyRecord(["win", "win", "loss", "push", null]);
  assert.deepEqual(record, { win: 2, loss: 1, push: 1, winRate: (100 * 2) / 3 });
  assert.equal(accuracyRecord([null, "push"]).winRate, null);
});

test("performance fixtures carry no financial fields", () => {
  const text = JSON.stringify(v5PerformanceDetailFixture);
  assert.doesNotMatch(text, /units|roi|profit/i);
});
