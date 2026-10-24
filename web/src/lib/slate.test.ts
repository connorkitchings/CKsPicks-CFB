import assert from "node:assert/strict";
import test from "node:test";

import {
  biggestEdgesRecord,
  edgeTier,
  edgeTone,
  hasGradedPick,
  hasLean,
  leanFor,
  leanGradeRows,
  phoneLean,
  sortGames,
  sortSlate,
  slateSorts,
  weekPhase,
  topLeans,
  resultFor,
  topLeansRecord,
  winRatePct,
} from "./slate.ts";
import type { Game } from "./queries.ts";

function game(over: Record<string, unknown>): Game {
  return {
    gameId: 1,
    season: 2026,
    week: 5,
    startDate: new Date("2026-10-03T16:00:00Z"),
    homeTeam: "Home",
    awayTeam: "Away",
    homeTeamSpreadLine: -3.5,
    totalLine: 50.5,
    updatedAt: new Date("2026-09-30T00:00:00Z"),
    homePoints: null,
    awayPoints: null,
    homeRecord: null,
    awayRecord: null,
    publicationMode: "predictions",
    runId: "r",
    runState: "frozen",
    predictedSpread: 6.5,
    predictedTotal: 55,
    predictedSpreadStdDev: null,
    predictedTotalStdDev: null,
    spreadLean: "home",
    totalLean: "over",
    edgeSpread: 3,
    edgeTotal: 4.5,
    highConfidence: false,
    systemName: "x",
    modelId: "m",
    regime: null,
    homeCompletedGames: 4,
    awayCompletedGames: 4,
    spreadModelVersion: null,
    totalModelVersion: null,
    spreadResult: null,
    totalResult: null,
    ...over,
  } as Game;
}

test("edge tiers follow the spread and total thresholds", () => {
  assert.equal(edgeTier("spread", null), 0);
  assert.equal(edgeTier("spread", 0), 0);
  assert.equal(edgeTier("spread", 3), 1);
  assert.equal(edgeTier("spread", 3.1), 2);
  assert.equal(edgeTier("spread", 8), 2);
  assert.equal(edgeTier("spread", 8.1), 3);
  assert.equal(edgeTier("total", 2), 1);
  assert.equal(edgeTier("total", 7.1), 3);
});

test("edgeTone colors edge magnitudes on the same thresholds", () => {
  assert.equal(edgeTone(2.9, "spread"), "edge-low");
  assert.equal(edgeTone(3, "spread"), "edge-medium");
  assert.equal(edgeTone(8, "spread"), "edge-medium");
  assert.equal(edgeTone(8.1, "spread"), "edge-high");
  assert.equal(edgeTone(-8.1, "spread"), "edge-high");
  assert.equal(edgeTone(1.9, "total"), "edge-low");
  assert.equal(edgeTone(2, "total"), "edge-medium");
  assert.equal(edgeTone(7, "total"), "edge-medium");
  assert.equal(edgeTone(7.1, "total"), "edge-high");
});

test("leanFor labels the pick side with a positive edge", () => {
  const home = leanFor(game({}), "spread");
  assert.equal(home?.pick, "Home -3.5");
  assert.equal(home?.edge, 3);
  const away = leanFor(game({ spreadLean: "away", edgeSpread: -4.2 }), "spread");
  assert.equal(away?.pick, "Away +3.5");
  assert.equal(away?.edge, 4.2);
  assert.equal(leanFor(game({ totalLean: "under" }), "total")?.pick, "Under 50.5");
});

test("phoneLean abbreviates a long leaned team in the pick and model text only", () => {
  const long = leanFor(game({ homeTeam: "Florida International", awayTeam: "Georgia" }), "spread")!;
  const phone = phoneLean(long);
  assert.equal(phone.pick, "FIU -3.5");
  assert.equal(phone.model, "FIU by 6.5");
  assert.equal(phone.team, "Florida International");
  const short = leanFor(game({ homeTeam: "Georgia", awayTeam: "Florida International" }), "spread")!;
  assert.equal(phoneLean(short), short);
  const total = leanFor(game({ homeTeam: "Florida International" }), "total")!;
  assert.equal(phoneLean(total), total);
});

test("no lean when the lean or the line is missing, and for market games", () => {
  assert.equal(leanFor(game({ spreadLean: null }), "spread"), null);
  assert.equal(leanFor(game({ homeTeamSpreadLine: null }), "spread"), null);
  assert.equal(leanFor(game({ totalLine: null }), "total"), null);
  const market = { ...game({}), publicationMode: "market" } as Game;
  assert.equal(leanFor(market, "spread"), null);
  assert.equal(hasLean(game({ spreadLean: null, totalLean: null })), false);
  assert.equal(hasLean(game({ spreadLean: null })), true);
});

test("topLeans ranks by edge and skips finished games", () => {
  const games = [
    game({ gameId: 1, edgeSpread: 2 }),
    game({ gameId: 2, edgeSpread: 9 }),
    game({ gameId: 3, edgeSpread: 12, homePoints: 21, awayPoints: 17 }),
    game({ gameId: 4, edgeSpread: 5, spreadLean: null }),
  ];
  assert.deepEqual(topLeans(games, "spread", 5).map((l) => l.game.gameId), [2, 1]);
  assert.deepEqual(topLeans(games, "spread", 1).map((l) => l.game.gameId), [2]);
});

test("topLeans ranks finished games too when asked", () => {
  const games = [
    game({ gameId: 1, edgeSpread: 2 }),
    game({ gameId: 2, edgeSpread: 9 }),
    game({ gameId: 3, edgeSpread: 12, homePoints: 21, awayPoints: 17 }),
  ];
  assert.deepEqual(topLeans(games, "spread", 5).map((l) => l.game.gameId), [2, 1]);
  assert.deepEqual(topLeans(games, "spread", 5, true).map((l) => l.game.gameId), [3, 2, 1]);
});

test("topLeansRecord tallies each week's top leans from recorded grades", () => {
  const graded = (over: Record<string, unknown>) =>
    game({ homePoints: 24, awayPoints: 17, ...over });
  const week = [
    graded({ gameId: 1, edgeSpread: 9, spreadResult: "win", edgeTotal: 1, totalResult: "loss" }),
    graded({ gameId: 2, edgeSpread: 8, spreadResult: "loss", edgeTotal: 9, totalResult: "win" }),
    graded({ gameId: 3, edgeSpread: 1, spreadResult: "win", edgeTotal: 8, totalResult: "loss" }),
    graded({ gameId: 4, edgeSpread: 9.5, spreadResult: null, edgeTotal: null, totalResult: null }),
  ];
  // Spread top 2: ungraded game 4 is skipped, game 1 won. Total top 2: game 2 won, game 3 lost.
  assert.deepEqual(topLeansRecord([week], 2), { win: 2, loss: 1, push: 0 });
  assert.deepEqual(topLeansRecord([week, week], 2), { win: 4, loss: 2, push: 0 });
  assert.deepEqual(topLeansRecord([]), { win: 0, loss: 0, push: 0 });
});

test("biggestEdgesRecord ranks leans exactly as the per-week topLeans does", () => {
  const graded = (over: Record<string, unknown>) =>
    game({ homePoints: 24, awayPoints: 17, ...over });
  const results = ["win", "loss", "push"] as const;
  const slates = [5, 6, 7].map((week) =>
    Array.from({ length: 14 }, (_, i) => graded({
      gameId: week * 100 + i,
      week,
      // Repeated edges and kickoffs force the tie-breaks to matter.
      edgeSpread: (i % 5) + 1,
      edgeTotal: ((i * 3) % 4) + 1,
      spreadLean: i % 6 === 0 ? null : "home",
      startDate: new Date(Date.UTC(2026, 9, week, 16 + (i % 3))),
      spreadResult: i % 7 === 0 ? null : results[i % 3],
      totalResult: results[(i + 1) % 3],
    })),
  );
  const reference = { win: 0, loss: 0, push: 0 };
  for (const slate of slates) {
    for (const kind of ["spread", "total"] as const) {
      for (const lean of topLeans(slate, kind, 5, true)) {
        const grade = resultFor(lean.game, kind);
        if (grade) reference[grade] += 1;
      }
    }
  }
  assert.ok(reference.win + reference.loss + reference.push > 0);
  assert.deepEqual(topLeansRecord(slates), reference);
  assert.deepEqual(biggestEdgesRecord(slates.flatMap(leanGradeRows)), reference);
});

test("sortGames puts the biggest edge first and no-lean games last", () => {
  const games = [
    game({ gameId: 1, edgeSpread: 2, edgeTotal: 1 }),
    game({ gameId: 2, spreadLean: null, totalLean: null }),
    game({ gameId: 3, edgeSpread: 1, edgeTotal: 6 }),
  ];
  assert.deepEqual(sortGames(games, "bestEdge").map((g) => g.gameId), [3, 1, 2]);
  assert.deepEqual(sortGames(games, "spreadEdge").map((g) => g.gameId), [1, 3, 2]);
});

test("win rate excludes pushes and is null with no decisions", () => {
  assert.equal(winRatePct(0, 0), null);
  assert.equal(winRatePct(1, 1), 50);
  assert.equal(Math.round((winRatePct(93, 103) ?? 0) * 10) / 10, 47.4);
});

import {
  coverMargin,
  gradeFromMargin,
  matchesResult,
  sortResults,
  topResults,
  weekRecord,
} from "./slate.ts";

function finalGame(over: Record<string, unknown>): Game {
  return game({ homePoints: 24, awayPoints: 17, ...over });
}

test("coverMargin is positive when the lean side covered", () => {
  // Home -3.5 lean, home wins by 7 -> covers by 3.5.
  assert.equal(coverMargin(finalGame({}), "spread"), 3.5);
  // Away lean at +3.5 (home line -3.5): home wins by 7 -> away misses by 3.5.
  assert.equal(coverMargin(finalGame({ spreadLean: "away" }), "spread"), -3.5);
  // Over 50.5, final total 41 -> misses by 9.5; under covers by 9.5.
  assert.equal(coverMargin(finalGame({}), "total"), -9.5);
  assert.equal(coverMargin(finalGame({ totalLean: "under" }), "total"), 9.5);
  // Not final, or no lean -> null.
  assert.equal(coverMargin(game({}), "spread"), null);
  assert.equal(coverMargin(finalGame({ spreadLean: null }), "spread"), null);
});

test("gradeFromMargin maps sign to win, loss and push", () => {
  assert.equal(gradeFromMargin(0.5), "win");
  assert.equal(gradeFromMargin(-0.5), "loss");
  assert.equal(gradeFromMargin(0), "push");
  assert.equal(gradeFromMargin(null), null);
});

test("weekRecord tallies recorded grades per bet type", () => {
  const games = [
    finalGame({ gameId: 1, spreadResult: "win", totalResult: "loss" }),
    finalGame({ gameId: 2, spreadResult: "loss", totalResult: null }),
    finalGame({ gameId: 3, spreadResult: "push", totalResult: "win" }),
  ];
  assert.deepEqual(weekRecord(games), {
    spread: { win: 1, loss: 1, push: 1 },
    total: { win: 1, loss: 1, push: 0 },
  });
});

test("topResults ranks graded leans of one outcome by edge", () => {
  const games = [
    finalGame({ gameId: 1, spreadResult: "win", edgeSpread: 3, totalResult: "loss", edgeTotal: 9 }),
    finalGame({ gameId: 2, spreadResult: "win", edgeSpread: 7, totalResult: "win", edgeTotal: 2 }),
  ];
  const wins = topResults(games, "win", 5);
  assert.deepEqual(wins.map((w) => [w.game.gameId, w.kind]), [[2, "spread"], [1, "spread"], [2, "total"]]);
  const losses = topResults(games, "loss", 5);
  assert.deepEqual(losses.map((w) => [w.game.gameId, w.kind]), [[1, "total"]]);
});

test("result filters and sorts", () => {
  const win = finalGame({ gameId: 1, spreadResult: "win", totalLean: null });
  const loss = finalGame({ gameId: 2, spreadResult: "loss", spreadLean: "away", totalLean: null });
  const none = finalGame({ gameId: 3, spreadLean: null, totalLean: null });
  assert.equal(matchesResult(win, "win"), true);
  assert.equal(matchesResult(win, "loss"), false);
  assert.equal(matchesResult(none, "none"), true);
  assert.equal(matchesResult(win, "all"), true);
  // win covers +3.5, loss misses -3.5, none has no cover.
  assert.deepEqual(sortResults([loss, none, win], "bestResult").map((g) => g.gameId), [1, 2, 3]);
  assert.deepEqual(sortResults([win, none, loss], "worstResult").map((g) => g.gameId), [2, 1, 3]);
});


import { breakEvenDelta, finalMarginText } from "./slate.ts";

test("leans carry the model's prediction from the pick's side", () => {
  const fav = leanFor(game({}), "spread");
  assert.equal(fav?.model, "Home by 6.5");
  assert.equal(fav?.dir, "home");
  assert.equal(fav?.team, "Home");

  const dog = leanFor(game({ spreadLean: "away", homeTeamSpreadLine: -3.5 }), "spread");
  assert.equal(dog?.model, "Away by -6.5");

  const pk = leanFor(game({ homeTeamSpreadLine: 0 }), "spread");
  assert.equal(pk?.pick, "Home PK");

  const over = leanFor(game({}), "total");
  assert.equal(over?.model, "55.0");
  assert.equal(over?.dir, "over");
  assert.equal(leanFor(game({ totalLean: "under" }), "total")?.dir, "under");
});

test("breakEvenDelta is signed, bounded and comparable", () => {
  const below = breakEvenDelta(93, 103);
  assert.equal(Math.round((below.delta ?? 0) * 10) / 10, -5);
  assert.ok(below.fill < 0 && below.fill > -1);
  assert.equal(below.decided, 196);
  assert.ok(breakEvenDelta(82, 77).fill > -0.1);
  assert.equal(breakEvenDelta(0, 0).rate, null);
  assert.equal(breakEvenDelta(0, 0).fill, 0);
  assert.equal(breakEvenDelta(20, 0).fill, 1);
  assert.equal(breakEvenDelta(0, 20).fill, -1);
});

test("finalMarginText reads the result from the leaned team's side", () => {
  const g = game({ homePoints: 24, awayPoints: 17 });
  assert.equal(finalMarginText(g, "Home"), "won by 7");
  assert.equal(finalMarginText(g, "Away"), "lost by 7");
  assert.equal(finalMarginText(game({}), "Home"), null);
});


import { bookName, leanDetail } from "./slate.ts";

test("bookName maps sportsbook keys and tidies unknown providers", () => {
  assert.equal(bookName("draftkings"), "DraftKings");
  assert.equal(bookName("DraftKings"), "DraftKings");
  assert.equal(bookName("espnbet"), "ESPN Bet");
  assert.equal(bookName("williamhill_us"), "Caesars");
  assert.equal(bookName("some_new_book"), "Some New Book");
  assert.equal(bookName("Bovada"), "Bovada");
  assert.equal(bookName("  "), null);
  assert.equal(bookName(null), null);
  assert.equal(bookName(undefined), null);
});

test("leans carry the line's source and detail text only when known", () => {
  const withSource = leanFor(game({ spreadSource: "draftkings", totalSource: "bovada" }), "spread");
  assert.equal(withSource?.source, "DraftKings");
  assert.equal(leanDetail(withSource!), "model: Home by 6.5 · best line: DraftKings");
  assert.equal(leanFor(game({ totalSource: "bovada" }), "total")?.source, "Bovada");
  // Consensus fallback: no source recorded -> no invented source.
  const noSource = leanFor(game({}), "spread");
  assert.equal(noSource?.source, null);
  assert.equal(leanDetail(noSource!), "model: Home by 6.5");
});


import { venueLabel } from "./slate.ts";

test("venueLabel formats City, ST and degrades gracefully", () => {
  assert.equal(venueLabel("Los Angeles", "CA"), "Los Angeles, CA");
  assert.equal(venueLabel("  Ann Arbor ", " MI "), "Ann Arbor, MI");
  assert.equal(venueLabel("Dublin", null), "Dublin");
  assert.equal(venueLabel(null, "TX"), "TX");
  assert.equal(venueLabel("", "  "), "");
  assert.equal(venueLabel(undefined, undefined), "");
});


test("weekPhase is upcoming with no finished game or no games, final when all are, else in-progress", () => {
  const open = game({ gameId: 1 });
  const done = game({ gameId: 2, homePoints: 31, awayPoints: 24 });
  assert.equal(weekPhase([]), "upcoming");
  assert.equal(weekPhase([open, open]), "upcoming");
  assert.equal(weekPhase([done, open]), "in-progress");
  assert.equal(weekPhase([done, done]), "final");
});

test("sortSlate offers result sorts only once a game has finished", () => {
  assert.equal(slateSorts("upcoming").includes("worstResult"), false);
  assert.equal(slateSorts("final").includes("worstResult"), true);
  const early = game({ gameId: 1, startDate: new Date("2026-10-03T12:00:00Z"), edgeSpread: 1, edgeTotal: 1 });
  const late = game({ gameId: 2, startDate: new Date("2026-10-03T20:00:00Z"), edgeSpread: 5, edgeTotal: 1 });
  // An upcoming week ignores a result sort and keeps kickoff order.
  assert.deepEqual(sortSlate([late, early], "worstResult", "upcoming").map((g) => g.gameId), [1, 2]);
  assert.deepEqual(sortSlate([early, late], "bestEdge", "upcoming").map((g) => g.gameId), [2, 1]);
  const win = game({ gameId: 3, homePoints: 40, awayPoints: 10, totalLean: null });
  const loss = game({ gameId: 4, homePoints: 10, awayPoints: 40, totalLean: null });
  assert.deepEqual(sortSlate([loss, win], "bestResult", "final").map((g) => g.gameId), [3, 4]);
  assert.deepEqual(sortSlate([win, loss], "worstResult", "in-progress").map((g) => g.gameId), [4, 3]);
});

test("hasGradedPick is false for final games without a recorded grade", () => {
  const ungradedFinal = game({ homePoints: 30, awayPoints: 20 });
  assert.equal(hasGradedPick([ungradedFinal]), false);
  assert.equal(hasGradedPick([]), false);
});

test("hasGradedPick is true once any spread or total grade exists", () => {
  const ungraded = game({ homePoints: 30, awayPoints: 20 });
  assert.equal(hasGradedPick([ungraded, game({ spreadResult: "push" })]), true);
  assert.equal(hasGradedPick([game({ totalResult: "loss" })]), true);
});
