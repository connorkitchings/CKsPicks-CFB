import { eq, asc, and, inArray, lte, sql, notLike } from "drizzle-orm";
import { cache } from "react";
import { db, schema } from "./db";
import { isSelectableRun } from "./run-selection";
import { deriveSpreadView, deriveTotalView } from "./publication";

type BaseGame = {
  gameId: number;
  season: number;
  week: number;
  startDate: Date;
  homeTeam: string;
  awayTeam: string;
  homeTeamSpreadLine: number | null;
  totalLine: number | null;
  updatedAt: Date;
  homePoints: number | null;
  awayPoints: number | null;
  /** Season W-L as of this game's kickoff (null before the first game). */
  homeRecord: string | null;
  awayRecord: string | null;
};

/** Public-safe schedule and market projection with no model-only fields. */
export type MarketGame = BaseGame & {
  publicationMode: "market";
  /** Settled outcomes are public-safe; predictions and model metadata are not. */
  spreadResult: "win" | "loss" | "push" | null;
  totalResult: "win" | "loss" | "push" | null;
};

/** Prediction-bearing projection, selected only after explicit publication opt-in. */
export type PredictionGame = BaseGame & {
  publicationMode: "predictions";
  runId: string | null;
  runState: "preview" | "published" | "frozen" | "scored" | "legacy";
  predictedSpread: number | null;
  predictedTotal: number | null;
  predictedSpreadStdDev: number | null;
  predictedTotalStdDev: number | null;
  spreadLean: "home" | "away" | null;
  totalLean: "over" | "under" | null;
  edgeSpread: number | null;
  edgeTotal: number | null;
  highConfidence: boolean;
  systemName: string | null;
  modelId: string | null;
  evidenceClass?: "legacy" | "pending" | "replay" | "live" | "missed";
  regime: "preseason" | "one_game" | "two_games" | "three_games" | "game_1" | "game_2" | "game_3" | "game_4" | "established" | null;
  homeCompletedGames: number;
  awayCompletedGames: number;
  spreadModelVersion: string | null;
  totalModelVersion: string | null;
  spreadResult: "win" | "loss" | "push" | null;
  totalResult: "win" | "loss" | "push" | null;
};

export type Game = MarketGame | PredictionGame;

/** YTD system record shape. */
export type Stats = {
  season: number;
  /** Last week with immutable grades in this selected-week snapshot. */
  asOfWeek: number | null;
  spreadWins: number;
  spreadLosses: number;
  spreadPushes: number;
  totalWins: number;
  totalLosses: number;
  totalPushes: number;
};

/** Diagnostic-only reconstructed historical comparison; never a live bet record. */
export type HistoricalContextPeriod = {
  comparisonSeason: number;
  comparisonWeek: number | null;
  spreadWins: number;
  spreadLosses: number;
  spreadPushes: number;
  spreadComparedGames: number;
  totalWins: number;
  totalLosses: number;
  totalPushes: number;
  totalComparedGames: number;
};

export type HistoricalModelContext = {
  modelId: string;
  fullSeason: HistoricalContextPeriod;
  matchingWeek: HistoricalContextPeriod | null;
};

/** Return the active { season, week, updatedAt } from the singleton current_week row. */
export const getCurrentWeek = cache(async (): Promise<{
  season: number;
  week: number;
  updatedAt: Date;
  activeRunId: string | null;
} | null> => {
  const rows = await db
    .select({
      season: schema.currentWeek.season,
      week: schema.currentWeek.week,
      updatedAt: schema.currentWeek.updatedAt,
      activeRunId: schema.currentWeek.activeRunId,
    })
    .from(schema.currentWeek)
    .where(eq(schema.currentWeek.id, 1))
    .limit(1);
  const row = rows[0];
  if (!row || (row.season === 0 && row.week === 0)) return null;
  return { season: row.season, week: row.week, updatedAt: row.updatedAt, activeRunId: row.activeRunId };
});

export type RunSummary = {
  runId: string;
  modelId: string;
  state: "preview" | "published" | "frozen" | "scored";
  evidenceClass: "legacy" | "pending" | "replay" | "live" | "missed";
  createdAt: Date;
  expectedGames: number;
  predictedGames: number;
  linedGames: number;
};

/**
 * One explicitly selected public run; missing selection never guesses. The
 * selected run may be V5 or an eligible legacy V4 rollback (same slate),
 * so eligibility is validated after the join rather than filtered to V5.
 */
export const getRunForWeek = cache(async (season: number, week: number): Promise<RunSummary | null> => {
  const rows = await db.select({
    runId: schema.predictionRuns.runId,
    modelId: schema.predictionRuns.modelId,
    state: schema.predictionRuns.state,
    evidenceClass: schema.predictionRuns.evidenceClass,
    createdAt: schema.predictionRuns.createdAt,
    expectedGames: schema.predictionRuns.expectedGames,
    predictedGames: schema.predictionRuns.predictedGames,
    linedGames: schema.predictionRuns.linedGames,
  })
    .from(schema.siteWeekSelections)
    .innerJoin(schema.predictionRuns, eq(schema.siteWeekSelections.runId, schema.predictionRuns.runId))
    .where(and(
      eq(schema.siteWeekSelections.season, season),
      eq(schema.siteWeekSelections.week, week),
      eq(schema.predictionRuns.season, season),
      eq(schema.predictionRuns.week, week),
    ))
    .limit(1);
  const row = rows[0];
  if (!row || !isSelectableRun(row)) return null;
  return {
    runId: row.runId,
    modelId: row.modelId ?? "",
    state: row.state as RunSummary["state"],
    evidenceClass: row.evidenceClass as RunSummary["evidenceClass"],
    createdAt: row.createdAt,
    expectedGames: row.expectedGames,
    predictedGames: row.predictedGames,
    linedGames: row.linedGames,
  };
});

/** Distinct weeks with published games for a season, ascending. Used by the week nav. */
export async function getAvailableWeeks(season: number): Promise<number[]> {
  const rows = await db.select({
    week: schema.siteWeekSelections.week,
    modelId: schema.predictionRuns.modelId,
    state: schema.predictionRuns.state,
    evidenceClass: schema.predictionRuns.evidenceClass,
  })
    .from(schema.siteWeekSelections)
    .innerJoin(schema.predictionRuns, eq(schema.siteWeekSelections.runId, schema.predictionRuns.runId))
    .where(eq(schema.siteWeekSelections.season, season))
    .orderBy(asc(schema.siteWeekSelections.week));
  return rows.filter(isSelectableRun).map((row) => row.week);
}

type CompletedGameRow = {
  startDate: Date;
  homeTeam: string;
  awayTeam: string;
  homePoints: number;
  awayPoints: number;
};

/**
 * Completed season games in kickoff order. Card views advance through this
 * timeline to snapshot each team's record as of a game's kickoff, so
 * historical week pages never leak later results.
 */
const getSeasonCompletedGames = cache(async (season: number): Promise<CompletedGameRow[]> => {
  const rows = await db
    .select({
      startDate: schema.games.startDate,
      homeTeam: schema.games.homeTeam,
      awayTeam: schema.games.awayTeam,
      homePoints: schema.gameResults.homePoints,
      awayPoints: schema.gameResults.awayPoints,
    })
    .from(schema.games)
    .innerJoin(
      schema.gameResults,
      eq(schema.games.gameId, schema.gameResults.gameId),
    )
    .where(
      and(
        eq(schema.games.season, season),
        eq(schema.gameResults.completionState, "completed"),
      ),
    )
    .orderBy(asc(schema.games.startDate), asc(schema.games.gameId));
  return rows.filter(
    (row): row is CompletedGameRow =>
      row.homePoints !== null && row.awayPoints !== null,
  );
});

function recordLabel(record: { wins: number; losses: number } | undefined): string | null {
  if (!record || record.wins + record.losses === 0) return null;
  return `${record.wins}-${record.losses}`;
}

/**
 * Attach point-in-time season records to a week's games (either publication
 * mode). Precondition: `games` is in kickoff order (all query paths order by
 * startDate). Strictly-earlier completions count, so a game's own final never
 * appears in its own record.
 */
function withRecords<
  T extends { startDate: Date; homeTeam: string; awayTeam: string },
>(games: T[], completed: CompletedGameRow[]): (T & {
  homeRecord: string | null;
  awayRecord: string | null;
})[] {
  const records = new Map<string, { wins: number; losses: number }>();
  const bump = (team: string) => {
    const entry = records.get(team) ?? { wins: 0, losses: 0 };
    records.set(team, entry);
    return entry;
  };
  let cursor = 0;
  return games.map((game) => {
    const kickoff = game.startDate.getTime();
    while (cursor < completed.length && completed[cursor].startDate.getTime() < kickoff) {
      const { homeTeam, awayTeam, homePoints, awayPoints } = completed[cursor];
      const winner = homePoints > awayPoints ? homeTeam : awayPoints > homePoints ? awayTeam : null;
      const loser = homePoints > awayPoints ? awayTeam : awayPoints > homePoints ? homeTeam : null;
      if (winner && loser) {
        bump(winner).wins += 1;
        bump(loser).losses += 1;
      }
      cursor += 1;
    }
    return {
      ...game,
      homeRecord: recordLabel(records.get(game.homeTeam)),
      awayRecord: recordLabel(records.get(game.awayTeam)),
    };
  });
}

type FrozenLine = { spread: number | null; total: number | null };

/** Frozen pre-kickoff snapshot lines from the week's closed non-V5 run. */
async function frozenLinesForWeek(
  season: number,
  week: number,
): Promise<Map<number, FrozenLine>> {
  const runs = await db
    .select({
      runId: schema.predictionRuns.runId,
      state: schema.predictionRuns.state,
    })
    .from(schema.predictionRuns)
    .where(
      and(
        eq(schema.predictionRuns.season, season),
        eq(schema.predictionRuns.week, week),
        notLike(schema.predictionRuns.modelId, "v5-%"),
        inArray(schema.predictionRuns.state, ["frozen", "scored"]),
      ),
    );
  const ordered = [...runs].sort((a, b) =>
    a.state === b.state ? 0 : a.state === "scored" ? -1 : 1,
  );
  const lines = new Map<number, FrozenLine>();
  for (const run of ordered) {
    const snapshotRows = await db
      .select({
        gameId: schema.predictions.gameId,
        spread: schema.marketSnapshots.spread,
        total: schema.marketSnapshots.total,
      })
      .from(schema.predictions)
      .innerJoin(
        schema.marketSnapshots,
        eq(schema.predictions.marketSnapshotId, schema.marketSnapshots.snapshotId),
      )
      .where(eq(schema.predictions.runId, run.runId));
    for (const row of snapshotRows) {
      if (!lines.has(row.gameId)) {
        lines.set(row.gameId, { spread: row.spread, total: row.total });
      }
    }
    if (lines.size > 0) break;
  }
  return lines;
}

/**
 * Fill market lines missing from serv­ing rows (replay runs are built without
 * a market feed) from the week's frozen snapshots — the same quotes the
 * grades use — and derive the matching leans and edges. Stored values are
 * never overwritten; the immutable prediction bytes are untouched.
 */
export async function withFrozenLines<
  T extends {
    gameId: number;
    homeTeamSpreadLine: number | null;
    totalLine: number | null;
    predictedSpread: number | null;
    predictedTotal: number | null;
    spreadLean: "home" | "away" | null;
    totalLean: "over" | "under" | null;
    edgeSpread: number | null;
    edgeTotal: number | null;
  },
>(rows: T[], season: number, week: number): Promise<T[]> {
  if (!rows.some((row) => row.homeTeamSpreadLine === null || row.totalLine === null)) {
    return rows;
  }
  const lines = await frozenLinesForWeek(season, week);
  if (lines.size === 0) return rows;
  return rows.map((row) => {
    const frozen = lines.get(row.gameId);
    if (!frozen) return row;
    const homeTeamSpreadLine = row.homeTeamSpreadLine ?? frozen.spread;
    const totalLine = row.totalLine ?? frozen.total;
    let { spreadLean, totalLean, edgeSpread, edgeTotal } = row;
    if (spreadLean === null) {
      const view = deriveSpreadView(row.predictedSpread, homeTeamSpreadLine);
      spreadLean = view.lean;
      if (edgeSpread === null) edgeSpread = view.edge;
    }
    if (totalLean === null) {
      const view = deriveTotalView(row.predictedTotal, totalLine);
      totalLean = view.lean;
      if (edgeTotal === null) edgeTotal = view.edge;
    }
    return { ...row, homeTeamSpreadLine, totalLine, spreadLean, totalLean, edgeSpread, edgeTotal };
  });
}

/** Return all games (with optional results) for a given season/week, sorted by start time. */
export async function getGamesForWeek(season: number, week: number): Promise<Game[]> {
  const run = await getRunForWeek(season, week);
  if (run) {
    const rows = await db
      .select({
        runId: schema.predictions.runId,
        gameId: schema.games.gameId,
        season: schema.games.season,
        week: schema.games.week,
        startDate: schema.games.startDate,
        homeTeam: schema.games.homeTeam,
        awayTeam: schema.games.awayTeam,
        homeTeamSpreadLine: schema.predictions.homeTeamSpreadLine,
        totalLine: schema.predictions.totalLine,
        predictedSpread: schema.predictions.predictedSpread,
        predictedTotal: schema.predictions.predictedTotal,
        predictedSpreadStdDev: schema.predictions.predictedSpreadStdDev,
        predictedTotalStdDev: schema.predictions.predictedTotalStdDev,
        spreadLean: schema.predictions.spreadLean,
        totalLean: schema.predictions.totalLean,
        edgeSpread: schema.predictions.edgeSpread,
        edgeTotal: schema.predictions.edgeTotal,
        highConfidence: schema.predictions.highConfidence,
        regime: schema.predictions.regime,
        homeCompletedGames: schema.predictions.homeCompletedGames,
        awayCompletedGames: schema.predictions.awayCompletedGames,
        spreadModelVersion: schema.predictions.spreadModelVersion,
        totalModelVersion: schema.predictions.totalModelVersion,
        systemName: schema.predictionRuns.systemName,
        modelId: schema.predictionRuns.modelId,
        updatedAt: schema.predictionRuns.createdAt,
        homePoints: schema.gameResults.homePoints,
        awayPoints: schema.gameResults.awayPoints,
        spreadResult: sql<"win" | "loss" | "push" | null>`(
          SELECT pg.result FROM prediction_grades pg
          WHERE pg.run_id = ${schema.predictions.runId}
            AND pg.game_id = ${schema.predictions.gameId}
            AND pg.target = 'spread'
          LIMIT 1
        )`,
        totalResult: sql<"win" | "loss" | "push" | null>`(
          SELECT pg.result FROM prediction_grades pg
          WHERE pg.run_id = ${schema.predictions.runId}
            AND pg.game_id = ${schema.predictions.gameId}
            AND pg.target = 'total'
          LIMIT 1
        )`,
      })
      .from(schema.predictions)
      .innerJoin(schema.games, eq(schema.predictions.gameId, schema.games.gameId))
      .innerJoin(schema.predictionRuns, eq(schema.predictions.runId, schema.predictionRuns.runId))
      .leftJoin(schema.gameResults, eq(schema.games.gameId, schema.gameResults.gameId))
      .where(eq(schema.predictions.runId, run.runId))
      .orderBy(asc(schema.games.startDate), asc(schema.games.gameId));
    const completed = await getSeasonCompletedGames(season);
    const games = await withFrozenLines(
      rows.map((row) => ({
        ...row,
        publicationMode: "predictions" as const,
        runState: run.state,
        evidenceClass: run.evidenceClass,
      })),
      season,
      week,
    );
    return withRecords(games, completed) as PredictionGame[];
  }

  if (season === 2026) return getMarketGamesForWeek(season, week);

  // Temporary compatibility path for rows published before run versioning.
  const rows = await db
    .select({
      gameId: schema.games.gameId,
      season: schema.games.season,
      week: schema.games.week,
      startDate: schema.games.startDate,
      homeTeam: schema.games.homeTeam,
      awayTeam: schema.games.awayTeam,
      homeTeamSpreadLine: schema.games.homeTeamSpreadLine,
      totalLine: schema.games.totalLine,
      predictedSpread: schema.games.predictedSpread,
      predictedTotal: schema.games.predictedTotal,
      predictedSpreadStdDev: schema.games.predictedSpreadStdDev,
      predictedTotalStdDev: schema.games.predictedTotalStdDev,
      spreadLean: schema.games.spreadLean,
      totalLean: schema.games.totalLean,
      edgeSpread: schema.games.edgeSpread,
      edgeTotal: schema.games.edgeTotal,
      highConfidence: schema.games.highConfidence,
      systemName: schema.games.systemName,
      modelId: schema.games.modelId,
      updatedAt: schema.games.updatedAt,
      // Results (nullable until scored)
      homePoints: schema.gameResults.homePoints,
      awayPoints: schema.gameResults.awayPoints,
      spreadResult: schema.gameResults.spreadResult,
      totalResult: schema.gameResults.totalResult,
    })
    .from(schema.games)
    .leftJoin(
      schema.gameResults,
      eq(schema.games.gameId, schema.gameResults.gameId),
    )
    .where(
      and(
        eq(schema.games.season, season),
        eq(schema.games.week, week),
      ),
    )
    .orderBy(asc(schema.games.startDate), asc(schema.games.gameId));
  const completed = await getSeasonCompletedGames(season);
  return withRecords(
    rows.map((row) => ({
      ...row,
      publicationMode: "predictions" as const,
      runId: null,
      runState: "legacy" as const,
      regime: null,
      homeCompletedGames: 0,
      awayCompletedGames: 0,
      spreadModelVersion: null,
      totalModelVersion: null,
    })),
    completed,
  ) as PredictionGame[];
}

/** Schedule + current published market lines without selecting model output. */
export async function getMarketGamesForWeek(
  season: number,
  week: number,
): Promise<MarketGame[]> {
  // A settled grade is safe to disclose, but it must remain tied to the exact
  // versioned run selected for this week. Legacy rows have no run identity.
  const run = await getRunForWeek(season, week);
  const spreadResult = run
    ? sql<"win" | "loss" | "push" | null>`(
        SELECT pg.result FROM prediction_grades pg
        WHERE pg.run_id = ${run.runId}
          AND pg.game_id = ${schema.games.gameId}
          AND pg.target = 'spread'
        LIMIT 1
      )`
    : season === 2026 ? sql<"win" | "loss" | "push" | null>`NULL` : schema.gameResults.spreadResult;
  const totalResult = run
    ? sql<"win" | "loss" | "push" | null>`(
        SELECT pg.result FROM prediction_grades pg
        WHERE pg.run_id = ${run.runId}
          AND pg.game_id = ${schema.games.gameId}
          AND pg.target = 'total'
        LIMIT 1
      )`
    : season === 2026 ? sql<"win" | "loss" | "push" | null>`NULL` : schema.gameResults.totalResult;
  const rows = await db
    .select({
      gameId: schema.games.gameId,
      season: schema.games.season,
      week: schema.games.week,
      startDate: schema.games.startDate,
      homeTeam: schema.games.homeTeam,
      awayTeam: schema.games.awayTeam,
      homeTeamSpreadLine: schema.games.homeTeamSpreadLine,
      totalLine: schema.games.totalLine,
      updatedAt: schema.games.updatedAt,
      homePoints: schema.gameResults.homePoints,
      awayPoints: schema.gameResults.awayPoints,
      spreadResult,
      totalResult,
    })
    .from(schema.games)
    .leftJoin(schema.gameResults, eq(schema.games.gameId, schema.gameResults.gameId))
    .where(and(eq(schema.games.season, season), eq(schema.games.week, week)))
    .orderBy(asc(schema.games.startDate), asc(schema.games.gameId));

  const completed = await getSeasonCompletedGames(season);
  return withRecords(
    rows.map((row) => ({ ...row, publicationMode: "market" as const })),
    completed,
  );
}

function emptyStats(season: number): Stats {
  return {
    season,
    asOfWeek: null,
    spreadWins: 0,
    spreadLosses: 0,
    spreadPushes: 0,
    totalWins: 0,
    totalLosses: 0,
    totalPushes: 0,
  };
}

/**
 * Immutable W-L-P snapshot through a selected week. A replacement run can be
 * published during the week, but only the latest scored run is authoritative
 * once results are final. This intentionally does not read `system_stats`:
 * that table is the latest full-season aggregate maintained by the pipeline.
 */
export const getSystemStatsThroughWeek = cache(async (
  season: number,
  throughWeek: number,
): Promise<Stats> => {
  const candidates = await db
    .select({
      runId: schema.predictionRuns.runId,
      week: schema.predictionRuns.week,
    })
    .from(schema.siteWeekSelections)
    .innerJoin(schema.predictionRuns, eq(schema.siteWeekSelections.runId, schema.predictionRuns.runId))
    .where(
      and(
        eq(schema.siteWeekSelections.season, season),
        lte(schema.siteWeekSelections.week, throughWeek),
        eq(schema.predictionRuns.state, "scored"),
      ),
    )
    .orderBy(asc(schema.siteWeekSelections.week));

  const selectedWeeks = new Map<number, string>();
  for (const candidate of candidates) {
    if (!selectedWeeks.has(candidate.week)) {
      selectedWeeks.set(candidate.week, candidate.runId);
    }
  }
  const runIds = [...selectedWeeks.values()];
  if (runIds.length === 0) return emptyStats(season);

  const grades = await db
    .select({
      runId: schema.predictionGrades.runId,
      target: schema.predictionGrades.target,
      result: schema.predictionGrades.result,
    })
    .from(schema.predictionGrades)
    .where(inArray(schema.predictionGrades.runId, runIds));

  if (grades.length === 0) return emptyStats(season);

  const stats = emptyStats(season);
  let asOfWeek: number | null = null;
  const weekByRunId = new Map(
    [...selectedWeeks.entries()].map(([week, runId]) => [runId, week]),
  );
  for (const grade of grades) {
    const week = weekByRunId.get(grade.runId);
    if (week !== undefined) {
      asOfWeek = asOfWeek === null ? week : Math.max(asOfWeek, week);
    }
    if (grade.target === "spread") {
      if (grade.result === "win") stats.spreadWins += 1;
      if (grade.result === "loss") stats.spreadLosses += 1;
      if (grade.result === "push") stats.spreadPushes += 1;
    }
    if (grade.target === "total") {
      if (grade.result === "win") stats.totalWins += 1;
      if (grade.result === "loss") stats.totalLosses += 1;
      if (grade.result === "push") stats.totalPushes += 1;
    }
  }
  return { ...stats, asOfWeek };
});

/**
 * Read only the pinned, diagnostic-only V4 historical context. A missing or
 * ambiguous serving projection fails closed rather than selecting a row.
 */
export const getHistoricalModelContext = cache(async (
  comparisonSeason: number,
  selectedWeek: number,
): Promise<HistoricalModelContext | null> => {
  const rows = await db
    .select()
    .from(schema.historicalModelContext)
    .where(and(
      eq(schema.historicalModelContext.comparisonSeason, comparisonSeason),
      eq(schema.historicalModelContext.modelId, "week0-2026-v4-strict-20260818-r2"),
      eq(schema.historicalModelContext.calculationVersion, "v1"),
      eq(schema.historicalModelContext.timingClass, "historically_reconstructed"),
      eq(schema.historicalModelContext.usage, "post_phase5_diagnostic_only"),
    ));
  const full = rows.filter((row) => row.periodScope === "season");
  const week = rows.filter(
    (row) => row.periodScope === "week" && row.comparisonWeek === selectedWeek,
  );
  if (full.length !== 1 || week.length > 1) return null;
  const map = (row: typeof rows[number]): HistoricalContextPeriod => ({
    comparisonSeason: row.comparisonSeason,
    comparisonWeek: row.comparisonWeek,
    spreadWins: row.spreadWins,
    spreadLosses: row.spreadLosses,
    spreadPushes: row.spreadPushes,
    spreadComparedGames: row.spreadComparedGames,
    totalWins: row.totalWins,
    totalLosses: row.totalLosses,
    totalPushes: row.totalPushes,
    totalComparedGames: row.totalComparedGames,
  });
  return { modelId: full[0].modelId, fullSeason: map(full[0]), matchingWeek: week[0] ? map(week[0]) : null };
});
