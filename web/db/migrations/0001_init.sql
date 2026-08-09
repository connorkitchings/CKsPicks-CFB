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
-- prediction_runs: immutable publication attempts for one season/week
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prediction_runs (
    run_id                 TEXT PRIMARY KEY,
    season                 INTEGER NOT NULL,
    week                   INTEGER NOT NULL,
    state                  TEXT NOT NULL CHECK (state IN ('preview', 'published', 'frozen', 'scored')),
    expected_games         INTEGER NOT NULL CHECK (expected_games >= 0),
    predicted_games        INTEGER NOT NULL CHECK (predicted_games >= 0),
    lined_games            INTEGER NOT NULL CHECK (lined_games >= 0),
    data_as_of             TIMESTAMPTZ NOT NULL,
    source_config          TEXT,
    system_name            TEXT,
    model_id               TEXT,
    code_sha               TEXT,
    config_sha             TEXT,
    model_bundle_sha256    TEXT,
    artifact_uri           TEXT NOT NULL,
    artifact_sha256        TEXT NOT NULL,
    validation             JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(validation) = 'object'),
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at           TIMESTAMPTZ,
    frozen_at              TIMESTAMPTZ,
    scored_at              TIMESTAMPTZ,
    UNIQUE (season, week, run_id),
    CHECK (predicted_games <= expected_games),
    CHECK (lined_games <= expected_games)
);

CREATE INDEX IF NOT EXISTS idx_prediction_runs_week_state
    ON prediction_runs (season, week, state, created_at DESC);

-- ---------------------------------------------------------------------------
-- predictions: per-game output for an immutable prediction run
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS predictions (
    run_id                    TEXT NOT NULL REFERENCES prediction_runs(run_id) ON DELETE RESTRICT,
    game_id                   BIGINT NOT NULL REFERENCES games(game_id) ON DELETE RESTRICT,
    home_team_spread_line     DOUBLE PRECISION,
    total_line                DOUBLE PRECISION,
    predicted_spread          DOUBLE PRECISION,
    predicted_total           DOUBLE PRECISION,
    predicted_spread_std_dev  DOUBLE PRECISION,
    predicted_total_std_dev   DOUBLE PRECISION,
    spread_lean               lean_side,
    total_lean                total_side,
    edge_spread               DOUBLE PRECISION,
    edge_total                DOUBLE PRECISION,
    high_confidence           BOOLEAN NOT NULL DEFAULT FALSE,
    high_confidence_eligible  BOOLEAN NOT NULL DEFAULT FALSE,
    home_completed_games      INTEGER NOT NULL DEFAULT 0 CHECK (home_completed_games >= 0),
    away_completed_games      INTEGER NOT NULL DEFAULT 0 CHECK (away_completed_games >= 0),
    regime                    TEXT NOT NULL CHECK (regime IN ('preseason', 'one_game', 'two_games', 'three_games', 'established')),
    spread_model_version      TEXT,
    total_model_version       TEXT,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, game_id)
);

CREATE INDEX IF NOT EXISTS idx_predictions_game_id ON predictions (game_id);
CREATE INDEX IF NOT EXISTS idx_predictions_run_confidence
    ON predictions (run_id, high_confidence) WHERE high_confidence = TRUE;

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
    active_run_id TEXT REFERENCES prediction_runs(run_id) ON DELETE RESTRICT,
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

-- Canonical serving view. Historical weeks prefer the newest frozen/scored
-- run; the active week follows current_week.active_run_id.
CREATE OR REPLACE VIEW active_game_predictions AS
WITH selected_runs AS (
    SELECT DISTINCT ON (pr.season, pr.week)
        pr.run_id,
        pr.season,
        pr.week,
        pr.state,
        pr.created_at
    FROM prediction_runs pr
    LEFT JOIN current_week cw
      ON cw.id = 1 AND cw.season = pr.season AND cw.week = pr.week
    WHERE pr.run_id = cw.active_run_id OR pr.state IN ('frozen', 'scored')
    ORDER BY
        pr.season,
        pr.week,
        (pr.run_id = cw.active_run_id) DESC,
        (pr.state IN ('frozen', 'scored')) DESC,
        pr.created_at DESC
)
SELECT
    g.game_id,
    g.season,
    g.week,
    g.start_date,
    g.home_team,
    g.away_team,
    p.*,
    sr.state AS run_state,
    sr.created_at AS run_created_at
FROM selected_runs sr
JOIN predictions p ON p.run_id = sr.run_id
JOIN games g ON g.game_id = p.game_id;
