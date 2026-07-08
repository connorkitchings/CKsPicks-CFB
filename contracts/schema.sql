-- 0001_init.sql — CKsPicks-CFB predictions schema
-- Target: Neon Postgres (serverless)
--
-- Conventions:
--   - predicted_spread = predicted HOME margin (signed; +home wins, -home loses)
--   - home_team_spread_line = market line on home team (signed; +home dog, -home favorite)
--   - spread_lean derived: 'home' if predicted_spread > -home_team_spread_line else 'away'
--   - predicted_total / total_line are positive point totals
--   - total_lean derived: 'over' if predicted_total > total_line else 'under'

-- Enum types for clarity
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'lean_side') THEN
        CREATE TYPE lean_side AS ENUM ('home', 'away');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'total_side') THEN
        CREATE TYPE total_side AS ENUM ('over', 'under');
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'bet_result') THEN
        CREATE TYPE bet_result AS ENUM ('win', 'loss', 'push');
    END IF;
END $$;

-- ---------------------------------------------------------------------------
-- games: one row per game with model prediction + market line
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS games (
    game_id              BIGINT PRIMARY KEY,
    season               INTEGER NOT NULL,
    week                 INTEGER NOT NULL,
    start_date           TIMESTAMPTZ NOT NULL,
    home_team            TEXT NOT NULL,
    away_team            TEXT NOT NULL,

    -- Market lines (nullable: FCS games or unavailable lines)
    home_team_spread_line DOUBLE PRECISION,
    total_line            DOUBLE PRECISION,

    -- Model predictions
    predicted_spread       DOUBLE PRECISION,  -- predicted home margin
    predicted_total        DOUBLE PRECISION,
    predicted_spread_std_dev DOUBLE PRECISION,
    predicted_total_std_dev  DOUBLE PRECISION,

    -- Derived leans + edge metrics
    spread_lean            lean_side,         -- 'home' or 'away'
    total_lean             total_side,        -- 'over' or 'under'
    edge_spread            DOUBLE PRECISION,  -- |predicted_spread + home_team_spread_line|
    edge_total             DOUBLE PRECISION,  -- |predicted_total - total_line|
    high_confidence        BOOLEAN NOT NULL DEFAULT FALSE,

    -- Provenance
    source_config          TEXT,              -- e.g., 'conf/weekly_bets/v2_champion.yaml'
    system_name            TEXT,              -- e.g., 'Trench Warfare V2'
    model_id               TEXT,              -- e.g., 'TW-V2-2025'
    inserted_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_games_season_week ON games (season, week);
CREATE INDEX IF NOT EXISTS idx_games_start_date  ON games (start_date);
CREATE INDEX IF NOT EXISTS idx_games_spread_lean ON games (spread_lean) WHERE spread_lean IS NOT NULL;

-- updated_at trigger
CREATE OR REPLACE FUNCTION trg_games_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS games_set_updated_at ON games;
CREATE TRIGGER games_set_updated_at
    BEFORE UPDATE ON games
    FOR EACH ROW
    EXECUTE FUNCTION trg_games_set_updated_at();

-- ---------------------------------------------------------------------------
-- game_results: scores + bet outcomes (populated after games finish)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS game_results (
    game_id        BIGINT PRIMARY KEY REFERENCES games(game_id) ON DELETE CASCADE,
    home_points    INTEGER,
    away_points    INTEGER,
    spread_result  bet_result,
    total_result   bet_result,
    scored_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- system_stats: YTD aggregate record per season
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_stats (
    season         INTEGER PRIMARY KEY,
    as_of_week     INTEGER NOT NULL,
    spread_wins    INTEGER NOT NULL DEFAULT 0,
    spread_losses  INTEGER NOT NULL DEFAULT 0,
    spread_pushes  INTEGER NOT NULL DEFAULT 0,
    total_wins     INTEGER NOT NULL DEFAULT 0,
    total_losses   INTEGER NOT NULL DEFAULT 0,
    total_pushes   INTEGER NOT NULL DEFAULT 0,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ---------------------------------------------------------------------------
-- current_week: singleton row (id=1) marking the active week
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS current_week (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    season      INTEGER NOT NULL,
    week        INTEGER NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

INSERT INTO current_week (id, season, week)
VALUES (1, 0, 0)
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Views for convenience
-- ---------------------------------------------------------------------------

-- Games with results joined (for historical browse)
CREATE OR REPLACE VIEW games_with_results AS
SELECT
    g.*,
    gr.home_points,
    gr.away_points,
    gr.spread_result,
    gr.total_result
FROM games g
LEFT JOIN game_results gr ON g.game_id = gr.game_id;

-- Season record view (compute from system_stats)
CREATE OR REPLACE VIEW season_record AS
SELECT
    season,
    as_of_week,
    spread_wins,
    spread_losses,
    spread_pushes,
    total_wins,
    total_losses,
    total_pushes,
    CASE
        WHEN (spread_wins + spread_losses) > 0
        THEN ROUND(100.0 * spread_wins / (spread_wins + spread_losses), 1)
        ELSE NULL
    END AS spread_win_pct,
    CASE
        WHEN (total_wins + total_losses) > 0
        THEN ROUND(100.0 * total_wins / (total_wins + total_losses), 1)
        ELSE NULL
    END AS total_win_pct,
    CASE
        WHEN (spread_wins + spread_losses) > 0
        THEN ROUND(100.0 * (spread_wins - spread_losses) / (spread_wins + spread_losses) - 4.55, 1)
        ELSE NULL
    END AS spread_roi,  -- assumes -110 vigorish: ROI = win_pct*(1) - loss_pct*(1.1)
    CASE
        WHEN (total_wins + total_losses) > 0
        THEN ROUND(100.0 * (total_wins - total_losses) / (total_wins + total_losses) - 4.55, 1)
        ELSE NULL
    END AS total_roi,
    updated_at
FROM system_stats;
