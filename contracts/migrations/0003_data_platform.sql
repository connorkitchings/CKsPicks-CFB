-- Immutable lake catalog, workflow state, canonical markets, and run grades.
-- Safe to apply after the legacy prediction-run migration.

CREATE SCHEMA IF NOT EXISTS catalog;
CREATE SCHEMA IF NOT EXISTS ops;

CREATE TABLE IF NOT EXISTS market_quotes (
    quote_id TEXT PRIMARY KEY,
    game_id BIGINT NOT NULL REFERENCES games(game_id) ON DELETE RESTRICT,
    provider TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    spread DOUBLE PRECISION,
    total DOUBLE PRECISION,
    source_capture_id TEXT,
    CHECK (spread IS NOT NULL OR total IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS idx_market_quotes_game_capture
    ON market_quotes (game_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS market_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    game_id BIGINT NOT NULL REFERENCES games(game_id) ON DELETE RESTRICT,
    captured_at TIMESTAMPTZ NOT NULL,
    spread DOUBLE PRECISION,
    total DOUBLE PRECISION,
    spread_rule TEXT,
    total_rule TEXT,
    spread_provider_count INTEGER NOT NULL DEFAULT 0 CHECK (spread_provider_count >= 0),
    total_provider_count INTEGER NOT NULL DEFAULT 0 CHECK (total_provider_count >= 0),
    source_quote_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    policy_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (game_id, captured_at, policy_version)
);
CREATE INDEX IF NOT EXISTS idx_market_snapshots_game_capture
    ON market_snapshots (game_id, captured_at DESC);

CREATE TABLE IF NOT EXISTS market_snapshot_quotes (
    snapshot_id TEXT NOT NULL REFERENCES market_snapshots(snapshot_id) ON DELETE RESTRICT,
    quote_id TEXT NOT NULL REFERENCES market_quotes(quote_id) ON DELETE RESTRICT,
    target TEXT NOT NULL CHECK (target IN ('spread', 'total')),
    PRIMARY KEY (snapshot_id, quote_id, target)
);
CREATE INDEX IF NOT EXISTS idx_market_snapshot_quotes_quote
    ON market_snapshot_quotes (quote_id);

ALTER TABLE predictions ADD COLUMN IF NOT EXISTS market_snapshot_id TEXT
    REFERENCES market_snapshots(snapshot_id) ON DELETE RESTRICT;
ALTER TABLE prediction_runs ADD COLUMN IF NOT EXISTS input_dataset_refs JSONB
    NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(input_dataset_refs) = 'array');

CREATE TABLE IF NOT EXISTS prediction_grades (
    run_id TEXT NOT NULL REFERENCES prediction_runs(run_id) ON DELETE RESTRICT,
    game_id BIGINT NOT NULL REFERENCES games(game_id) ON DELETE RESTRICT,
    target TEXT NOT NULL CHECK (target IN ('spread', 'total')),
    market_snapshot_id TEXT REFERENCES market_snapshots(snapshot_id) ON DELETE RESTRICT,
    side TEXT NOT NULL CHECK (side IN ('home', 'away', 'over', 'under')),
    result bet_result NOT NULL,
    profit_units NUMERIC(10, 4) NOT NULL,
    grading_version TEXT NOT NULL,
    graded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, game_id, target)
);
CREATE INDEX IF NOT EXISTS idx_prediction_grades_game ON prediction_grades (game_id);
CREATE INDEX IF NOT EXISTS idx_prediction_grades_run_result
    ON prediction_grades (run_id, target, result);

ALTER TABLE game_results
    ADD COLUMN IF NOT EXISTS completion_state TEXT NOT NULL DEFAULT 'completed',
    ADD COLUMN IF NOT EXISTS source_dataset_version_id TEXT;
ALTER TABLE system_stats
    ADD COLUMN IF NOT EXISTS spread_profit_units NUMERIC(12, 4) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS total_profit_units NUMERIC(12, 4) NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS catalog.ingestion_runs (
    ingestion_run_id TEXT PRIMARY KEY, provider TEXT NOT NULL, entity TEXT NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('running', 'succeeded', 'failed')),
    request JSONB NOT NULL CHECK (jsonb_typeof(request) = 'object'),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), finished_at TIMESTAMPTZ,
    error_category TEXT, error_detail TEXT
);
CREATE TABLE IF NOT EXISTS catalog.source_captures (
    capture_id TEXT PRIMARY KEY,
    ingestion_run_id TEXT REFERENCES catalog.ingestion_runs(ingestion_run_id) ON DELETE RESTRICT,
    provider TEXT NOT NULL, entity TEXT NOT NULL, captured_at TIMESTAMPTZ NOT NULL,
    effective_at TIMESTAMPTZ, request JSONB NOT NULL CHECK (jsonb_typeof(request) = 'object'),
    content_sha TEXT NOT NULL CHECK (length(content_sha) = 64), uri TEXT NOT NULL,
    row_count BIGINT NOT NULL CHECK (row_count >= 0), provider_api_version TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_source_captures_as_of
    ON catalog.source_captures (provider, entity, captured_at DESC);
CREATE INDEX IF NOT EXISTS idx_source_captures_content
    ON catalog.source_captures (content_sha);
CREATE TABLE IF NOT EXISTS catalog.schema_versions (
    dataset TEXT NOT NULL, schema_version TEXT NOT NULL,
    schema_json JSONB NOT NULL CHECK (jsonb_typeof(schema_json) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), PRIMARY KEY (dataset, schema_version)
);
CREATE TABLE IF NOT EXISTS catalog.dataset_versions (
    version_id TEXT PRIMARY KEY, dataset TEXT NOT NULL,
    tier TEXT NOT NULL CHECK (tier IN ('bronze', 'silver', 'gold')),
    schema_version TEXT NOT NULL, content_sha TEXT NOT NULL CHECK (length(content_sha) = 64),
    uri TEXT NOT NULL, manifest_uri TEXT NOT NULL, row_count BIGINT NOT NULL CHECK (row_count >= 0),
    partitions JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(partitions) = 'object'),
    as_of TIMESTAMPTZ NOT NULL, code_sha TEXT, config_sha TEXT,
    state TEXT NOT NULL CHECK (state IN ('staged', 'validated', 'failed', 'quarantined')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE (dataset, version_id)
);
CREATE INDEX IF NOT EXISTS idx_dataset_versions_as_of
    ON catalog.dataset_versions (dataset, as_of DESC);
CREATE TABLE IF NOT EXISTS catalog.dataset_dependencies (
    child_version_id TEXT NOT NULL REFERENCES catalog.dataset_versions(version_id) ON DELETE RESTRICT,
    parent_version_id TEXT NOT NULL REFERENCES catalog.dataset_versions(version_id) ON DELETE RESTRICT,
    ordinal INTEGER NOT NULL CHECK (ordinal >= 0), PRIMARY KEY (child_version_id, parent_version_id),
    UNIQUE (child_version_id, ordinal)
);
CREATE INDEX IF NOT EXISTS idx_dataset_dependencies_parent
    ON catalog.dataset_dependencies (parent_version_id);
CREATE TABLE IF NOT EXISTS catalog.quality_results (
    quality_result_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    version_id TEXT NOT NULL REFERENCES catalog.dataset_versions(version_id) ON DELETE RESTRICT,
    check_name TEXT NOT NULL, passed BOOLEAN NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(details) = 'object'),
    checked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE (version_id, check_name)
);
CREATE INDEX IF NOT EXISTS idx_quality_results_version ON catalog.quality_results (version_id);

CREATE TABLE IF NOT EXISTS ops.pipeline_runs (
    pipeline_run_id TEXT PRIMARY KEY, command TEXT NOT NULL,
    environment TEXT NOT NULL CHECK (environment IN ('preview', 'production')),
    season INTEGER NOT NULL, week INTEGER,
    state TEXT NOT NULL CHECK (state IN ('running', 'succeeded', 'failed')),
    input_refs JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(input_refs) = 'array'),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), finished_at TIMESTAMPTZ,
    error_category TEXT, error_detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_scope
    ON ops.pipeline_runs (environment, season, week, started_at DESC);
CREATE TABLE IF NOT EXISTS ops.pipeline_steps (
    pipeline_run_id TEXT NOT NULL REFERENCES ops.pipeline_runs(pipeline_run_id) ON DELETE RESTRICT,
    step_name TEXT NOT NULL, ordinal INTEGER NOT NULL CHECK (ordinal >= 0),
    state TEXT NOT NULL CHECK (state IN ('pending', 'running', 'succeeded', 'failed')),
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    input_refs JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(input_refs) = 'array'),
    output_refs JSONB NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(output_refs) = 'array'),
    started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ, error_category TEXT, error_detail TEXT,
    PRIMARY KEY (pipeline_run_id, step_name), UNIQUE (pipeline_run_id, ordinal)
);
CREATE TABLE IF NOT EXISTS ops.activation_history (
    activation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    environment TEXT NOT NULL CHECK (environment IN ('preview', 'production')),
    season INTEGER NOT NULL, week INTEGER NOT NULL,
    run_id TEXT NOT NULL REFERENCES prediction_runs(run_id) ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK (action IN ('publish', 'freeze', 'score', 'deactivate')),
    activated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(metadata) = 'object'),
    UNIQUE (run_id, action)
);
CREATE INDEX IF NOT EXISTS idx_activation_history_scope
    ON ops.activation_history (environment, season, week, activated_at DESC);
CREATE TABLE IF NOT EXISTS ops.waivers (
    waiver_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES prediction_runs(run_id) ON DELETE RESTRICT,
    waiver_type TEXT NOT NULL, reason TEXT NOT NULL CHECK (length(reason) > 0),
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_waivers_run ON ops.waivers (run_id);
CREATE TABLE IF NOT EXISTS ops.reconciliation_status (
    object_uri TEXT PRIMARY KEY, object_sha256 TEXT NOT NULL CHECK (length(object_sha256) = 64),
    status TEXT NOT NULL CHECK (status IN ('registered', 'orphaned', 'quarantined')),
    pipeline_run_id TEXT REFERENCES ops.pipeline_runs(pipeline_run_id) ON DELETE RESTRICT,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), reconciled_at TIMESTAMPTZ
);

-- Backfill reproducible legacy grades from each synthetic frozen run's own lines.
INSERT INTO prediction_grades (
    run_id, game_id, target, side, result, profit_units, grading_version
)
SELECT p.run_id, p.game_id, 'spread', p.spread_lean::text, gr.spread_result,
       CASE gr.spread_result WHEN 'win' THEN 1.0 WHEN 'loss' THEN -1.1 ELSE 0.0 END,
       'legacy_v1'
FROM predictions p JOIN game_results gr USING (game_id)
WHERE p.run_id LIKE 'legacy-%' AND p.spread_lean IS NOT NULL AND gr.spread_result IS NOT NULL
ON CONFLICT DO NOTHING;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cks_web') THEN CREATE ROLE cks_web NOLOGIN; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cks_pipeline') THEN CREATE ROLE cks_pipeline NOLOGIN; END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cks_migrator') THEN CREATE ROLE cks_migrator NOLOGIN; END IF;
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
INSERT INTO prediction_grades (
    run_id, game_id, target, side, result, profit_units, grading_version
)
SELECT p.run_id, p.game_id, 'total', p.total_lean::text, gr.total_result,
       CASE gr.total_result WHEN 'win' THEN 1.0 WHEN 'loss' THEN -1.1 ELSE 0.0 END,
       'legacy_v1'
FROM predictions p JOIN game_results gr USING (game_id)
WHERE p.run_id LIKE 'legacy-%' AND p.total_lean IS NOT NULL AND gr.total_result IS NOT NULL
ON CONFLICT DO NOTHING;
