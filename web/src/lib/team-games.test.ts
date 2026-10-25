import assert from "node:assert/strict";
import test from "node:test";
import {
  atsResult, nextUpcomingGame, forecastLine, forecastText, gameResultText, lineForTeam, lineText, marketText, modelPickedWinner, modelRecords, modelSpreadPick,
  modelTotalPick, modelWinnerName, overUnderResult, recordText, teamRecords, winPercent,
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
  });
});

test("modelSpreadPick takes the home side when the forecast beats the home line and grades it", () => {
  const g = lined({ homeTeamSpreadLine: -3.5, predictedMargin: 4, homePoints: 30, awayPoints: 24 });
  assert.deepEqual(modelSpreadPick(g), { label: "Texas -3.5", result: "W" });
});

test("modelSpreadPick takes the away side and grades a miss", () => {
  const g = lined({ homeTeamSpreadLine: -3.5, predictedMargin: 2, homePoints: 30, awayPoints: 24 });
  assert.deepEqual(modelSpreadPick(g), { label: "Rice +3.5", result: "L" });
});

test("modelSpreadPick pushes on the number and sends an exact tie to the away side", () => {
  assert.equal(modelSpreadPick(lined({ homeTeamSpreadLine: -3, predictedMargin: 5, homePoints: 24, awayPoints: 21 }))?.result, "P");
  assert.equal(modelSpreadPick(lined({ homeTeamSpreadLine: -3, predictedMargin: 3 }))?.label, "Rice +3.0");
});

test("modelSpreadPick has no result before the game ends and no pick without a forecast or a line", () => {
  assert.deepEqual(modelSpreadPick(lined({ homeTeamSpreadLine: -3.5, predictedMargin: 4 })), { label: "Texas -3.5", result: null });
  assert.equal(modelSpreadPick(lined({ predictedMargin: 4 })), null);
  assert.equal(modelSpreadPick(lined({ homeTeamSpreadLine: -3.5 })), null);
});

test("modelTotalPick grades over and under picks and an exact tie goes to the under", () => {
  assert.deepEqual(modelTotalPick(lined({ totalLine: 44.5, predictedTotal: 50, homePoints: 24, awayPoints: 21 })), { label: "↑ Over 44.5", result: "W" });
  assert.deepEqual(modelTotalPick(lined({ totalLine: 44.5, predictedTotal: 40, homePoints: 24, awayPoints: 21 })), { label: "↓ Under 44.5", result: "L" });
  assert.equal(modelTotalPick(lined({ totalLine: 45, predictedTotal: 50, homePoints: 24, awayPoints: 21 }))?.result, "P");
  assert.equal(modelTotalPick(lined({ totalLine: 45, predictedTotal: 45 }))?.label, "↓ Under 45.0");
  assert.equal(modelTotalPick(lined({ totalLine: 45 })), null);
  assert.equal(modelTotalPick(lined({ predictedTotal: 45 })), null);
});

test("modelWinnerName names the forecast winner and is null on a dead-even forecast", () => {
  assert.equal(modelWinnerName(game({ predictedMargin: 2 })), "Texas");
  assert.equal(modelWinnerName(game({ predictedMargin: -2 })), "Rice");
  assert.equal(modelWinnerName(game({ predictedMargin: 0 })), null);
  assert.equal(modelWinnerName(game({})), null);
});

test("modelRecords tallies picks over played games with lines and a forecast", () => {
  const games = [
    lined({ homeTeamSpreadLine: -3.5, totalLine: 44.5, predictedMargin: 4, predictedTotal: 50, homePoints: 30, awayPoints: 24 }),
    lined({ homeTeamSpreadLine: -3, totalLine: 60, predictedMargin: 5, predictedTotal: 70, homePoints: 24, awayPoints: 21 }),
    lined({ homeTeamSpreadLine: -3, predictedMargin: -2, homePoints: 30, awayPoints: 20 }),
    lined({ homeTeamSpreadLine: -3, totalLine: 50, predictedMargin: 5, predictedTotal: 60 }),
    lined({ homePoints: 10, awayPoints: 20 }),
  ];
  assert.deepEqual(modelRecords(games, "Texas"), {
    ats: { wins: 1, losses: 1, pushes: 1 },
    overUnder: { wins: 1, losses: 1, pushes: 0 },
    winner: { right: 2, wrong: 1 },
  });
});

test("winPercent leaves pushes out of the denominator", () => {
  assert.equal(winPercent(2, 1), "67%");
  assert.equal(winPercent(0, 0), null);
  assert.equal(winPercent(0, 3), "0%");
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

const timed = (id: number, startDate: string, scored = false) => ({ id, startDate: new Date(startDate), homePoints: scored ? 20 : null, awayPoints: scored ? 10 : null });
const nextId = (games: ReturnType<typeof timed>[], now: string) => nextUpcomingGame(games, new Date(now))?.id ?? null;

test("nextUpcomingGame picks the first game that has not kicked off", () => {
  const games = [timed(1, "2026-09-05T23:00:00Z", true), timed(2, "2026-09-12T23:00:00Z"), timed(3, "2026-09-19T23:00:00Z")];
  assert.equal(nextId(games, "2026-09-08T12:00:00Z"), 2);
});

test("nextUpcomingGame skips an unscored game whose kickoff has passed", () => {
  const games = [timed(1, "2026-09-05T23:00:00Z", true), timed(2, "2026-09-12T23:00:00Z"), timed(3, "2026-09-19T23:00:00Z")];
  assert.equal(nextId(games, "2026-09-14T12:00:00Z"), 3);
});

test("nextUpcomingGame keeps a Time TBD placeholder until its Eastern day ends", () => {
  const games = [timed(1, "2026-10-03T04:00:00Z"), timed(2, "2026-10-10T23:00:00Z")]; // midnight ET on Oct 3 (EDT)
  assert.equal(nextId(games, "2026-10-03T20:00:00Z"), 1);
  assert.equal(nextId(games, "2026-10-04T05:00:00Z"), 2);
});

test("nextUpcomingGame handles bye weeks between games", () => {
  const games = [timed(1, "2026-09-05T23:00:00Z", true), timed(2, "2026-09-26T23:00:00Z")];
  assert.equal(nextId(games, "2026-09-15T12:00:00Z"), 2);
});

test("nextUpcomingGame is null when nothing is left to play", () => {
  assert.equal(nextId([timed(1, "2026-09-05T23:00:00Z", true), timed(2, "2026-09-12T23:00:00Z")], "2026-09-20T12:00:00Z"), null);
  assert.equal(nextId([], "2026-09-20T12:00:00Z"), null);
});
