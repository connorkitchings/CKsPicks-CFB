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

export const gameResults = pgTable(
  "game_results",
  {
    gameId: bigint("game_id", { mode: "number" }).primaryKey().references(() => games.gameId, { onDelete: "cascade" }),
    homePoints: integer("home_points"),
    awayPoints: integer("away_points"),
    spreadResult: betResult("spread_result"),
    totalResult: betResult("total_result"),
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
    updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
  },
  (table) => [check("current_week_singleton", sql`${table.id} = 1`)],
);

export type CurrentWeek = typeof currentWeek.$inferSelect;
