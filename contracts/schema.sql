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

CREATE TABLE IF NOT EXISTS schema_migrations (
    version       TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    checksum      TEXT NOT NULL CHECK (length(checksum) = 64),
    applied_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

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
    input_dataset_refs     JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(input_dataset_refs) = 'array'),
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
    regime                    TEXT NOT NULL CHECK (regime IN ('preseason', 'one_game', 'two_games', 'three_games', 'game_1', 'game_2', 'game_3', 'established')),
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
    spread_profit_units NUMERIC(12, 4) NOT NULL DEFAULT 0,
    total_profit_units  NUMERIC(12, 4) NOT NULL DEFAULT 0,
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
-- Canonical market observations and run-specific grades
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS market_quotes (
    quote_id       TEXT PRIMARY KEY,
    game_id        BIGINT NOT NULL REFERENCES games(game_id) ON DELETE RESTRICT,
    provider       TEXT NOT NULL,
    captured_at    TIMESTAMPTZ NOT NULL,
    spread         DOUBLE PRECISION,
    total          DOUBLE PRECISION,
    source_capture_id TEXT,
    CHECK (spread IS NOT NULL OR total IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_market_quotes_game_capture
    ON market_quotes (game_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS market_snapshots (
    snapshot_id          TEXT PRIMARY KEY,
    game_id              BIGINT NOT NULL REFERENCES games(game_id) ON DELETE RESTRICT,
    captured_at          TIMESTAMPTZ NOT NULL,
    spread               DOUBLE PRECISION,
    total                DOUBLE PRECISION,
    spread_rule          TEXT,
    total_rule           TEXT,
    spread_provider_count INTEGER NOT NULL DEFAULT 0 CHECK (spread_provider_count >= 0),
    total_provider_count  INTEGER NOT NULL DEFAULT 0 CHECK (total_provider_count >= 0),
    source_quote_ids      JSONB NOT NULL DEFAULT '[]'::jsonb,
    policy_version       TEXT NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (game_id, captured_at, policy_version)
);

CREATE INDEX IF NOT EXISTS idx_market_snapshots_game_capture
    ON market_snapshots (game_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS market_snapshot_quotes (
    snapshot_id TEXT NOT NULL REFERENCES market_snapshots(snapshot_id) ON DELETE RESTRICT,
    quote_id    TEXT NOT NULL REFERENCES market_quotes(quote_id) ON DELETE RESTRICT,
    target      TEXT NOT NULL CHECK (target IN ('spread', 'total')),
    PRIMARY KEY (snapshot_id, quote_id, target)
);

CREATE INDEX IF NOT EXISTS idx_market_snapshot_quotes_quote
    ON market_snapshot_quotes (quote_id);

ALTER TABLE predictions
    ADD COLUMN IF NOT EXISTS market_snapshot_id TEXT
        REFERENCES market_snapshots(snapshot_id) ON DELETE RESTRICT;

CREATE TABLE IF NOT EXISTS prediction_grades (
    run_id             TEXT NOT NULL REFERENCES prediction_runs(run_id) ON DELETE RESTRICT,
    game_id            BIGINT NOT NULL REFERENCES games(game_id) ON DELETE RESTRICT,
    target             TEXT NOT NULL CHECK (target IN ('spread', 'total')),
    market_snapshot_id TEXT REFERENCES market_snapshots(snapshot_id) ON DELETE RESTRICT,
    side               TEXT NOT NULL CHECK (side IN ('home', 'away', 'over', 'under')),
    result             bet_result NOT NULL,
    profit_units       NUMERIC(10, 4) NOT NULL,
    grading_version    TEXT NOT NULL,
    graded_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, game_id, target)
);

CREATE INDEX IF NOT EXISTS idx_prediction_grades_game ON prediction_grades (game_id);
CREATE INDEX IF NOT EXISTS idx_prediction_grades_run_result
    ON prediction_grades (run_id, target, result);

-- Objective outcomes remain independent of any line or prediction run.  The
-- legacy result columns are retained only until the post-Week-1 compatibility
-- migration is complete.
ALTER TABLE game_results
    ADD COLUMN IF NOT EXISTS completion_state TEXT NOT NULL DEFAULT 'completed',
    ADD COLUMN IF NOT EXISTS source_dataset_version_id TEXT;

-- ---------------------------------------------------------------------------
-- Immutable lake catalog and resumable workflow control plane
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS catalog;
CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS catalog.ingestion_runs (
    ingestion_run_id TEXT PRIMARY KEY,
    provider         TEXT NOT NULL,
    entity           TEXT NOT NULL,
    state            TEXT NOT NULL CHECK (state IN ('running', 'succeeded', 'failed')),
    request           JSONB NOT NULL CHECK (jsonb_typeof(request) = 'object'),
    started_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at       TIMESTAMPTZ,
    error_category    TEXT,
    error_detail      TEXT
);

CREATE TABLE IF NOT EXISTS catalog.source_captures (
    capture_id          TEXT PRIMARY KEY,
    ingestion_run_id    TEXT REFERENCES catalog.ingestion_runs(ingestion_run_id) ON DELETE RESTRICT,
    provider            TEXT NOT NULL,
    entity              TEXT NOT NULL,
    captured_at         TIMESTAMPTZ NOT NULL,
    effective_at        TIMESTAMPTZ,
    request             JSONB NOT NULL CHECK (jsonb_typeof(request) = 'object'),
    content_sha         TEXT NOT NULL CHECK (length(content_sha) = 64),
    object_sha          TEXT NOT NULL CHECK (length(object_sha) = 64),
    uri                 TEXT NOT NULL,
    row_count           BIGINT NOT NULL CHECK (row_count >= 0),
    provider_api_version TEXT,
    response_metadata   JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(response_metadata) = 'object'),
    state               TEXT NOT NULL DEFAULT 'registered'
        CHECK (state IN ('staged', 'registered', 'quarantined', 'failed')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_source_captures_as_of
    ON catalog.source_captures (provider, entity, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_captures_content
    ON catalog.source_captures (content_sha);

CREATE TABLE IF NOT EXISTS catalog.schema_versions (
    dataset        TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    schema_json    JSONB NOT NULL CHECK (jsonb_typeof(schema_json) = 'object'),
    schema_sha     TEXT,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (dataset, schema_version)
);

CREATE TABLE IF NOT EXISTS catalog.dataset_versions (
    version_id       TEXT PRIMARY KEY,
    dataset          TEXT NOT NULL,
    tier             TEXT NOT NULL CHECK (tier IN ('bronze', 'silver', 'gold')),
    schema_version   TEXT NOT NULL,
    content_sha      TEXT NOT NULL CHECK (length(content_sha) = 64),
    uri              TEXT NOT NULL,
    manifest_uri     TEXT NOT NULL,
    row_count        BIGINT NOT NULL CHECK (row_count >= 0),
    partitions       JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(partitions) = 'object'),
    as_of            TIMESTAMPTZ NOT NULL,
    code_sha         TEXT,
    config_sha       TEXT,
    identity_version TEXT NOT NULL DEFAULT 'v1'
        CHECK (identity_version IN ('v1', 'dataset_identity_v2')),
    schema_sha       TEXT,
    state            TEXT NOT NULL CHECK (state IN ('staged', 'validated', 'failed', 'quarantined')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (dataset, version_id)
);

CREATE INDEX IF NOT EXISTS idx_dataset_versions_as_of
    ON catalog.dataset_versions (dataset, as_of DESC);
CREATE INDEX IF NOT EXISTS idx_dataset_versions_schema
    ON catalog.dataset_versions (dataset, schema_version, schema_sha);

CREATE TABLE IF NOT EXISTS catalog.dataset_dependencies (
    child_version_id  TEXT NOT NULL REFERENCES catalog.dataset_versions(version_id) ON DELETE RESTRICT,
    parent_version_id TEXT NOT NULL REFERENCES catalog.dataset_versions(version_id) ON DELETE RESTRICT,
    ordinal           INTEGER NOT NULL CHECK (ordinal >= 0),
    PRIMARY KEY (child_version_id, parent_version_id),
    UNIQUE (child_version_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_dataset_dependencies_parent
    ON catalog.dataset_dependencies (parent_version_id);

CREATE TABLE IF NOT EXISTS catalog.dataset_capture_dependencies (
    child_version_id TEXT NOT NULL REFERENCES catalog.dataset_versions(version_id) ON DELETE RESTRICT,
    capture_id       TEXT NOT NULL REFERENCES catalog.source_captures(capture_id) ON DELETE RESTRICT,
    ordinal          INTEGER NOT NULL CHECK (ordinal >= 0),
    PRIMARY KEY (child_version_id, capture_id),
    UNIQUE (child_version_id, ordinal)
);

CREATE INDEX IF NOT EXISTS idx_dataset_capture_dependencies_capture
    ON catalog.dataset_capture_dependencies (capture_id);

CREATE TABLE IF NOT EXISTS catalog.quality_results (
    quality_result_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    version_id        TEXT NOT NULL REFERENCES catalog.dataset_versions(version_id) ON DELETE RESTRICT,
    check_name        TEXT NOT NULL,
    passed            BOOLEAN NOT NULL,
    details           JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details) = 'object'),
    checked_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (version_id, check_name)
);

CREATE INDEX IF NOT EXISTS idx_quality_results_version
    ON catalog.quality_results (version_id);

CREATE TABLE IF NOT EXISTS catalog.source_reconciliations (
    reconciliation_id TEXT PRIMARY KEY,
    season             INTEGER NOT NULL,
    game_id            BIGINT NOT NULL,
    classification     TEXT NOT NULL CHECK (
        classification IN (
            'exact_match', 'tolerated_difference', 'known_correction',
            'incomplete_source', 'blocking_conflict'
        )
    ),
    blocking           BOOLEAN NOT NULL,
    source_dataset_versions JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(source_dataset_versions) = 'array'),
    details            JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(details) = 'object'),
    reconciled_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (season, game_id, reconciliation_id)
);

CREATE INDEX IF NOT EXISTS idx_source_reconciliations_scope
    ON catalog.source_reconciliations (season, game_id, blocking);

CREATE TABLE IF NOT EXISTS ops.pipeline_runs (
    pipeline_run_id TEXT PRIMARY KEY,
    command         TEXT NOT NULL,
    environment     TEXT NOT NULL CHECK (environment IN ('preview', 'production')),
    season          INTEGER NOT NULL,
    week            INTEGER,
    state           TEXT NOT NULL CHECK (state IN ('running', 'succeeded', 'failed')),
    input_refs      JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(input_refs) = 'array'),
    started_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMPTZ,
    error_category  TEXT,
    error_detail    TEXT,
    definition_json JSONB,
    definition_sha  TEXT,
    lease_owner     TEXT,
    lease_epoch     BIGINT NOT NULL DEFAULT 0,
    lease_expires_at TIMESTAMPTZ,
    heartbeat_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_scope
    ON ops.pipeline_runs (environment, season, week, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_lease
    ON ops.pipeline_runs (environment, season, week, lease_expires_at);

CREATE TABLE IF NOT EXISTS ops.pipeline_steps (
    pipeline_run_id TEXT NOT NULL REFERENCES ops.pipeline_runs(pipeline_run_id) ON DELETE RESTRICT,
    step_name       TEXT NOT NULL,
    ordinal         INTEGER NOT NULL CHECK (ordinal >= 0),
    state           TEXT NOT NULL CHECK (state IN ('pending', 'running', 'succeeded', 'failed')),
    attempts        INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    input_refs      JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(input_refs) = 'array'),
    output_refs     JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(output_refs) = 'array'),
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    error_category  TEXT,
    error_detail    TEXT,
    definition_sha  TEXT,
    lease_epoch     BIGINT,
    PRIMARY KEY (pipeline_run_id, step_name),
    UNIQUE (pipeline_run_id, ordinal)
);

CREATE TABLE IF NOT EXISTS ops.activation_history (
    activation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    environment   TEXT NOT NULL CHECK (environment IN ('preview', 'production')),
    season        INTEGER NOT NULL,
    week          INTEGER NOT NULL,
    run_id        TEXT NOT NULL REFERENCES prediction_runs(run_id) ON DELETE RESTRICT,
    action        TEXT NOT NULL CHECK (action IN ('publish', 'freeze', 'score', 'deactivate')),
    activated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    UNIQUE (run_id, action)
);

CREATE INDEX IF NOT EXISTS idx_activation_history_scope
    ON ops.activation_history (environment, season, week, activated_at DESC);

CREATE TABLE IF NOT EXISTS ops.waivers (
    waiver_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id       TEXT NOT NULL REFERENCES prediction_runs(run_id) ON DELETE RESTRICT,
    waiver_type  TEXT NOT NULL,
    reason       TEXT NOT NULL CHECK (length(reason) > 0),
    recorded_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_waivers_run ON ops.waivers (run_id);

CREATE TABLE IF NOT EXISTS ops.reconciliation_status (
    object_uri       TEXT PRIMARY KEY,
    object_sha256    TEXT NOT NULL CHECK (length(object_sha256) = 64),
    status           TEXT NOT NULL CHECK (status IN ('registered', 'orphaned', 'quarantined')),
    pipeline_run_id  TEXT REFERENCES ops.pipeline_runs(pipeline_run_id) ON DELETE RESTRICT,
    discovered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reconciled_at    TIMESTAMPTZ
);

-- Roles are NOLOGIN group roles; deployment-specific login roles inherit one.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cks_web') THEN
        CREATE ROLE cks_web NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cks_pipeline') THEN
        CREATE ROLE cks_pipeline NOLOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cks_migrator') THEN
        CREATE ROLE cks_migrator NOLOGIN;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO cks_web;
GRANT SELECT ON games, game_results, prediction_runs, predictions,
    prediction_grades, market_snapshots, system_stats, current_week TO cks_web;
GRANT USAGE ON SCHEMA public, catalog, ops TO cks_pipeline;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public, catalog, ops TO cks_pipeline;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public, catalog, ops TO cks_pipeline;
GRANT ALL PRIVILEGES ON SCHEMA public, catalog, ops TO cks_migrator;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public, catalog, ops TO cks_migrator;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public, catalog, ops TO cks_migrator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO cks_web;
ALTER DEFAULT PRIVILEGES IN SCHEMA public, catalog, ops
    GRANT SELECT, INSERT, UPDATE ON TABLES TO cks_pipeline;

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
        THEN ROUND(100.0 * spread_profit_units / (spread_wins + spread_losses), 1)
        ELSE NULL
    END AS spread_roi,  -- assumes -110 vigorish: ROI = win_pct*(1) - loss_pct*(1.1)
    CASE
        WHEN (total_wins + total_losses) > 0
        THEN ROUND(100.0 * total_profit_units / (total_wins + total_losses), 1)
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
    p.run_id,
    p.home_team_spread_line,
    p.total_line,
    p.predicted_spread,
    p.predicted_total,
    p.predicted_spread_std_dev,
    p.predicted_total_std_dev,
    p.spread_lean,
    p.total_lean,
    p.edge_spread,
    p.edge_total,
    p.high_confidence,
    p.high_confidence_eligible,
    p.home_completed_games,
    p.away_completed_games,
    p.regime,
    p.spread_model_version,
    p.total_model_version,
    p.market_snapshot_id,
    p.created_at AS prediction_created_at,
    sr.state AS run_state,
    sr.created_at AS run_created_at
FROM selected_runs sr
JOIN predictions p ON p.run_id = sr.run_id
JOIN games g ON g.game_id = p.game_id;
