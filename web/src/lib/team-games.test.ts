import assert from "node:assert/strict";
import test from "node:test";
import {
  atsResult, forecastLine, forecastText, gameResultText, lineForTeam, lineText, marketText, modelPickedWinner, overUnderResult, recordText, teamRecords,
  type TeamGameFields, type TeamGameLines,
} from "./team-games.ts";

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

const lined = (over: Partial<TeamGameFields & TeamGameLines>): TeamGameFields & TeamGameLines => ({
  ...game({}), homeTeamSpreadLine: null, totalLine: null, ...over,
});

test("lineForTeam flips the home line for the away team", () => {
  const g = lined({ homeTeamSpreadLine: -3.5 });
  assert.equal(lineForTeam(g, "Texas"), -3.5);
  assert.equal(lineForTeam(g, "Rice"), 3.5);
  assert.equal(lineForTeam(lined({}), "Rice"), null);
});

test("atsResult covers when the favorite wins by more than the line", () => {
  const g = lined({ homeTeamSpreadLine: -3.5, homePoints: 30, awayPoints: 24 });
  assert.equal(atsResult(g, "Texas"), "W");
  assert.equal(atsResult(g, "Rice"), "L");
});

test("atsResult gives the away underdog the points", () => {
  const g = lined({ homeTeamSpreadLine: -7, homePoints: 20, awayPoints: 17 });
  assert.equal(atsResult(g, "Rice"), "W");
});

test("atsResult is a push on the number", () => {
  const g = lined({ homeTeamSpreadLine: -3, homePoints: 24, awayPoints: 21 });
  assert.equal(atsResult(g, "Texas"), "P");
  assert.equal(atsResult(g, "Rice"), "P");
});

test("atsResult is null without a line or a final score", () => {
  assert.equal(atsResult(lined({ homePoints: 24, awayPoints: 21 }), "Texas"), null);
  assert.equal(atsResult(lined({ homeTeamSpreadLine: -3 }), "Texas"), null);
});

test("overUnderResult compares combined points with the total", () => {
  assert.equal(overUnderResult(lined({ totalLine: 44.5, homePoints: 24, awayPoints: 21 })), "Over");
  assert.equal(overUnderResult(lined({ totalLine: 50.5, homePoints: 24, awayPoints: 21 })), "Under");
  assert.equal(overUnderResult(lined({ totalLine: 45, homePoints: 24, awayPoints: 21 })), "Push");
  assert.equal(overUnderResult(lined({ homePoints: 24, awayPoints: 21 })), null);
  assert.equal(overUnderResult(lined({ totalLine: 45 })), null);
});

test("modelPickedWinner reads the margin from the home side", () => {
  assert.equal(modelPickedWinner(lined({ predictedMargin: 3, homePoints: 24, awayPoints: 21 }), "Texas"), true);
  assert.equal(modelPickedWinner(lined({ predictedMargin: -3, homePoints: 24, awayPoints: 21 }), "Rice"), false);
  assert.equal(modelPickedWinner(lined({ homePoints: 24, awayPoints: 21 }), "Texas"), null);
  assert.equal(modelPickedWinner(lined({ predictedMargin: 3 }), "Texas"), null);
});

test("teamRecords tallies each record over the games that have the data", () => {
  const games = [
    lined({ homeTeamSpreadLine: -3.5, totalLine: 44.5, predictedMargin: 4, homePoints: 30, awayPoints: 24 }),
    lined({ homeTeamSpreadLine: -3, totalLine: 60, predictedMargin: -2, homePoints: 24, awayPoints: 21 }),
    lined({ predictedMargin: 5, homePoints: 10, awayPoints: 20 }),
    lined({ predictedMargin: 5 }),
  ];
  assert.deepEqual(teamRecords(games, "Texas"), {
    ats: { wins: 1, losses: 0, pushes: 1 },
    overUnder: { overs: 1, unders: 1, pushes: 0 },
    modelWinner: { right: 1, wrong: 2 },
  });
});

test("marketText reads the line from the favorite's side with the total", () => {
  assert.equal(marketText(lined({ homeTeamSpreadLine: -3.5, totalLine: 51.5 })), "Texas -3.5 · 51.5");
  assert.equal(marketText(lined({ homeTeamSpreadLine: 7, totalLine: 51 })), "Rice -7.0 · 51.0");
  assert.equal(marketText(lined({ homeTeamSpreadLine: 0 })), "PK");
  assert.equal(marketText(lined({ totalLine: 51.5 })), "51.5");
  assert.equal(marketText(lined({})), null);
});

test("forecastText gives the model line and total without a prefix", () => {
  assert.equal(forecastText(game({ predictedMargin: 3.5, predictedTotal: 54.84 })), "Texas -3.5 · 54.8");
  assert.equal(forecastText(game({})), null);
});

test("lineText prints a signed line, a pick'em or a dash", () => {
  assert.equal(lineText(-3.5), "-3.5");
  assert.equal(lineText(7), "+7.0");
  assert.equal(lineText(0), "PK");
  assert.equal(lineText(null), "—");
});

test("forecastLine is the model line without the total", () => {
  assert.equal(forecastLine(game({ predictedMargin: -3.5, predictedTotal: 54 })), "Texas +3.5");
  assert.equal(forecastLine(game({})), null);
});

test("recordText shows pushes only when there are some", () => {
  assert.equal(recordText(2, 3), "2–3");
  assert.equal(recordText(2, 3, 1), "2–3–1");
});
