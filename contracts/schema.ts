import { sql } from "drizzle-orm";
import {
  pgTable,
  bigint,
  integer,
  text,
  doublePrecision,
  boolean,
  timestamp,
  pgEnum,
  index,
  check,
  jsonb,
  primaryKey,
  numeric,
} from "drizzle-orm/pg-core";

// Enums ---------------------------------------------------------------------

export const leanSide = pgEnum("lean_side", ["home", "away"]);
export const totalSide = pgEnum("total_side", ["over", "under"]);
export const betResult = pgEnum("bet_result", ["win", "loss", "push"]);

// Tables --------------------------------------------------------------------

/**
 * One row per game with model prediction + market line.
 *
 * Semantics (matches Python pipeline output):
 *   predicted_spread       -> predicted HOME margin (+home wins, -home loses)
 *   home_team_spread_line  -> market line on home team (+home dog, -home favorite)
 *   spread_lean            -> 'home' if predicted_spread > -home_team_spread_line else 'away'
 *   predicted_total        -> model predicted total points
 *   total_lean             -> 'over' if predicted_total > total_line else 'under'
 */
export const games = pgTable(
  "games",
  {
    gameId: bigint("game_id", { mode: "number" }).primaryKey(),
    season: integer("season").notNull(),
    week: integer("week").notNull(),
    startDate: timestamp("start_date", { withTimezone: true }).notNull(),

    homeTeam: text("home_team").notNull(),
    awayTeam: text("away_team").notNull(),

    // Market lines (nullable)
    homeTeamSpreadLine: doublePrecision("home_team_spread_line"),
    totalLine: doublePrecision("total_line"),

    // Model predictions
    predictedSpread: doublePrecision("predicted_spread"),
    predictedTotal: doublePrecision("predicted_total"),
    predictedSpreadStdDev: doublePrecision("predicted_spread_std_dev"),
    predictedTotalStdDev: doublePrecision("predicted_total_std_dev"),

    // Derived leans + edges
    spreadLean: leanSide("spread_lean"),
    totalLean: totalSide("total_lean"),
    edgeSpread: doublePrecision("edge_spread"),
    edgeTotal: doublePrecision("edge_total"),
    highConfidence: boolean("high_confidence").notNull().default(false),

    // Provenance
    sourceConfig: text("source_config"),
    systemName: text("system_name"),
    modelId: text("model_id"),

    insertedAt: timestamp("inserted_at", { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    index("idx_games_season_week").on(table.season, table.week),
    index("idx_games_start_date").on(table.startDate),
  ],
);

export type Game = typeof games.$inferSelect;
export type NewGame = typeof games.$inferInsert;

// ---------------------------------------------------------------------------

export const predictionRuns = pgTable(
  "prediction_runs",
  {
    runId: text("run_id").primaryKey(),
    season: integer("season").notNull(),
    week: integer("week").notNull(),
    state: text("state").notNull(),
    expectedGames: integer("expected_games").notNull(),
    predictedGames: integer("predicted_games").notNull(),
    linedGames: integer("lined_games").notNull(),
    dataAsOf: timestamp("data_as_of", { withTimezone: true }).notNull(),
    sourceConfig: text("source_config"),
    systemName: text("system_name"),
    modelId: text("model_id"),
    codeSha: text("code_sha"),
    configSha: text("config_sha"),
    modelBundleSha256: text("model_bundle_sha256"),
    artifactUri: text("artifact_uri").notNull(),
    artifactSha256: text("artifact_sha256").notNull(),
    inputDatasetRefs: jsonb("input_dataset_refs").notNull().default([]),
    validation: jsonb("validation").notNull().default({}),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
    publishedAt: timestamp("published_at", { withTimezone: true }),
    frozenAt: timestamp("frozen_at", { withTimezone: true }),
    scoredAt: timestamp("scored_at", { withTimezone: true }),
  },
  (table) => [
    index("idx_prediction_runs_week_state").on(
      table.season,
      table.week,
      table.state,
      table.createdAt,
    ),
    check(
      "prediction_runs_state_check",
      sql`${table.state} IN ('preview', 'published', 'frozen', 'scored')`,
    ),
  ],
);

export type PredictionRun = typeof predictionRuns.$inferSelect;

export const predictions = pgTable(
  "predictions",
  {
    runId: text("run_id").notNull().references(() => predictionRuns.runId, { onDelete: "restrict" }),
    gameId: bigint("game_id", { mode: "number" }).notNull().references(() => games.gameId, { onDelete: "restrict" }),
    homeTeamSpreadLine: doublePrecision("home_team_spread_line"),
    totalLine: doublePrecision("total_line"),
    predictedSpread: doublePrecision("predicted_spread"),
    predictedTotal: doublePrecision("predicted_total"),
    predictedSpreadStdDev: doublePrecision("predicted_spread_std_dev"),
    predictedTotalStdDev: doublePrecision("predicted_total_std_dev"),
    spreadLean: leanSide("spread_lean"),
    totalLean: totalSide("total_lean"),
    edgeSpread: doublePrecision("edge_spread"),
    edgeTotal: doublePrecision("edge_total"),
    highConfidence: boolean("high_confidence").notNull().default(false),
    highConfidenceEligible: boolean("high_confidence_eligible").notNull().default(false),
    homeCompletedGames: integer("home_completed_games").notNull().default(0),
    awayCompletedGames: integer("away_completed_games").notNull().default(0),
    regime: text("regime").notNull(),
    spreadModelVersion: text("spread_model_version"),
    totalModelVersion: text("total_model_version"),
    marketSnapshotId: text("market_snapshot_id"),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [
    primaryKey({ columns: [table.runId, table.gameId] }),
    index("idx_predictions_game_id").on(table.gameId),
  ],
);

export type Prediction = typeof predictions.$inferSelect;

export const marketQuotes = pgTable(
  "market_quotes",
  {
    quoteId: text("quote_id").primaryKey(),
    gameId: bigint("game_id", { mode: "number" }).notNull().references(() => games.gameId, { onDelete: "restrict" }),
    provider: text("provider").notNull(),
    capturedAt: timestamp("captured_at", { withTimezone: true }).notNull(),
    spread: doublePrecision("spread"),
    total: doublePrecision("total"),
    sourceCaptureId: text("source_capture_id"),
  },
  (table) => [index("idx_market_quotes_game_capture").on(table.gameId, table.capturedAt)],
);

export const marketSnapshots = pgTable(
  "market_snapshots",
  {
    snapshotId: text("snapshot_id").primaryKey(),
    gameId: bigint("game_id", { mode: "number" }).notNull().references(() => games.gameId, { onDelete: "restrict" }),
    capturedAt: timestamp("captured_at", { withTimezone: true }).notNull(),
    spread: doublePrecision("spread"),
    total: doublePrecision("total"),
    spreadRule: text("spread_rule"),
    totalRule: text("total_rule"),
    spreadProviderCount: integer("spread_provider_count").notNull().default(0),
    totalProviderCount: integer("total_provider_count").notNull().default(0),
    sourceQuoteIds: jsonb("source_quote_ids").notNull().default([]),
    policyVersion: text("policy_version").notNull(),
    createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [index("idx_market_snapshots_game_capture").on(table.gameId, table.capturedAt)],
);

export const marketSnapshotQuotes = pgTable(
  "market_snapshot_quotes",
  {
    snapshotId: text("snapshot_id").notNull().references(() => marketSnapshots.snapshotId, { onDelete: "restrict" }),
    quoteId: text("quote_id").notNull().references(() => marketQuotes.quoteId, { onDelete: "restrict" }),
    target: text("target").notNull(),
  },
  (table) => [primaryKey({ columns: [table.snapshotId, table.quoteId, table.target] })],
);

export const predictionGrades = pgTable(
  "prediction_grades",
  {
    runId: text("run_id").notNull().references(() => predictionRuns.runId, { onDelete: "restrict" }),
    gameId: bigint("game_id", { mode: "number" }).notNull().references(() => games.gameId, { onDelete: "restrict" }),
    target: text("target").notNull(),
    marketSnapshotId: text("market_snapshot_id").references(() => marketSnapshots.snapshotId, { onDelete: "restrict" }),
    side: text("side").notNull(),
    result: betResult("result").notNull(),
    profitUnits: numeric("profit_units", { precision: 10, scale: 4 }).notNull(),
    gradingVersion: text("grading_version").notNull(),
    gradedAt: timestamp("graded_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [primaryKey({ columns: [table.runId, table.gameId, table.target] })],
);

// ---------------------------------------------------------------------------

export const gameResults = pgTable(
  "game_results",
  {
    gameId: bigint("game_id", { mode: "number" }).primaryKey().references(() => games.gameId, { onDelete: "cascade" }),
    homePoints: integer("home_points"),
    awayPoints: integer("away_points"),
    spreadResult: betResult("spread_result"),
    totalResult: betResult("total_result"),
    completionState: text("completion_state").notNull().default("completed"),
    sourceDatasetVersionId: text("source_dataset_version_id"),
    scoredAt: timestamp("scored_at", { withTimezone: true }).notNull().defaultNow(),
  },
);

export type GameResult = typeof gameResults.$inferSelect;

// ---------------------------------------------------------------------------

export const systemStats = pgTable("system_stats", {
  season: integer("season").primaryKey(),
  asOfWeek: integer("as_of_week").notNull(),
  spreadWins: integer("spread_wins").notNull().default(0),
  spreadLosses: integer("spread_losses").notNull().default(0),
  spreadPushes: integer("spread_pushes").notNull().default(0),
  totalWins: integer("total_wins").notNull().default(0),
  totalLosses: integer("total_losses").notNull().default(0),
  totalPushes: integer("total_pushes").notNull().default(0),
  spreadProfitUnits: numeric("spread_profit_units", { precision: 12, scale: 4 }).notNull().default("0"),
  totalProfitUnits: numeric("total_profit_units", { precision: 12, scale: 4 }).notNull().default("0"),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

export type SystemStats = typeof systemStats.$inferSelect;

// ---------------------------------------------------------------------------

export const currentWeek = pgTable(
  "current_week",
  {
    id: integer("id").primaryKey(),
    season: integer("season").notNull(),
    week: integer("week").notNull(),
    activeRunId: text("active_run_id").references(() => predictionRuns.runId, { onDelete: "restrict" }),
    updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [check("current_week_singleton", sql`${table.id} = 1`)],
);

export type CurrentWeek = typeof currentWeek.$inferSelect;
