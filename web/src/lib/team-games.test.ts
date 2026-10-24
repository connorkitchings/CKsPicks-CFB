import assert from "node:assert/strict";
import test from "node:test";
import { gameResultText, type TeamGameFields } from "./team-games.ts";

const game = (over: Partial<TeamGameFields>): TeamGameFields => ({
  homeTeam: "Texas", awayTeam: "Rice", predictedMargin: null, predictedTotal: null, homePoints: null, awayPoints: null, ...over,
});

test("gameResultText reads a home win from the home side", () => {
  assert.equal(gameResultText(game({ homePoints: 59, awayPoints: 45 }), "Texas"), "W 59–45");
});

test("gameResultText reads an away loss from the away side", () => {
  assert.equal(gameResultText(game({ homePoints: 30, awayPoints: 6 }), "Rice"), "L 6–30");
});

test("gameResultText shows the forecast for a game that is not final", () => {
  assert.equal(gameResultText(game({ predictedMargin: 3.5, predictedTotal: 54.84 }), "Rice"), "Forecast: Texas -3.5 · 54.8");
});

test("gameResultText is null when a game has no forecast", () => {
  assert.equal(gameResultText(game({}), "Texas"), null);
});
