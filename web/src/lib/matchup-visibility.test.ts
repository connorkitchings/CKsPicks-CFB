import assert from "node:assert/strict";
import test from "node:test";

import { selectMatchupView } from "./matchup-visibility.ts";
import type { Game } from "./queries.ts";

const base = {
  gameId: 1,
  season: 2026,
  week: 5,
  startDate: new Date("2026-10-03T16:00:00Z"),
  homeTeam: "Home",
  awayTeam: "Away",
  homeTeamSpreadLine: -3.5,
  totalLine: 51.5,
  updatedAt: new Date("2026-09-30T00:00:00Z"),
  homePoints: null,
  awayPoints: null,
  homeRecord: null,
  awayRecord: null,
};

const marketGame = {
  ...base,
  publicationMode: "market",
  spreadResult: null,
  totalResult: null,
} as Game;

const predictionGame = {
  ...base,
  publicationMode: "predictions",
  runId: "run-selected",
  runState: "frozen",
  predictedSpread: 6.2,
  predictedTotal: 55.1,
  predictedSpreadStdDev: null,
  predictedTotalStdDev: null,
  spreadLean: "home",
  totalLean: "over",
  edgeSpread: 2.7,
  edgeTotal: 3.6,
  highConfidence: true,
  systemName: "Blitzkrieg V5",
  modelId: "v5-possession-ppp-rho060-exposure",
  regime: null,
  homeCompletedGames: 4,
  awayCompletedGames: 4,
  spreadModelVersion: null,
  totalModelVersion: null,
  spreadResult: null,
  totalResult: null,
} as Game;

test("missing game yields no view", () => {
  assert.equal(selectMatchupView(undefined, "predictions"), null);
});

test("predictions mode with a selected-run game exposes model fields", () => {
  const view = selectMatchupView(predictionGame, "predictions");
  assert.equal(view?.publicationMode, "predictions");
  assert.equal(view?.predictedSpread, 6.2);
  assert.equal(view?.spreadLean, "home");
  assert.equal(view?.modelId, "v5-possession-ppp-rho060-exposure");
});

test("market mode never exposes model fields even for a prediction game", () => {
  const view = selectMatchupView(predictionGame, "market");
  assert.equal(view?.publicationMode, "market");
  assert.equal(view?.predictedSpread, null);
  assert.equal(view?.predictedTotal, null);
  assert.equal(view?.spreadLean, null);
  assert.equal(view?.totalLean, null);
  assert.equal(view?.modelId, null);
  assert.equal(view?.marketSpreadLine, -3.5);
});

test("a week with no selected run (market game) stays market-only in predictions mode", () => {
  const view = selectMatchupView(marketGame, "predictions");
  assert.equal(view?.publicationMode, "market");
  assert.equal(view?.predictedSpread, null);
  assert.equal(view?.edgeSpread, null);
  assert.equal(view?.highConfidence, false);
  assert.equal(view?.marketTotal, 51.5);
});

test("sportsbook sources are model-side fields: present only in predictions mode", () => {
  const game = {
    publicationMode: "predictions",
    homeTeamSpreadLine: -2.5,
    totalLine: 57.5,
    homePoints: null,
    awayPoints: null,
    systemName: "Blitzkrieg",
    modelId: "m",
    predictedSpread: -7.6,
    predictedTotal: 54.1,
    spreadLean: "home",
    totalLean: "under",
    edgeSpread: 5.1,
    edgeTotal: 3.4,
    highConfidence: false,
    spreadSource: "DraftKings",
    totalSource: null,
  } as unknown as Parameters<typeof selectMatchupView>[0];
  const open = selectMatchupView(game, "predictions");
  assert.equal(open?.spreadSource, "DraftKings");
  assert.equal(open?.totalSource, null);
  const closed = selectMatchupView(game, "market");
  assert.equal(closed?.spreadSource, null);
  assert.equal(closed?.edgeSpread, null);
});
