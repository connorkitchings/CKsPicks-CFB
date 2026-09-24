-- Explicit public run ownership and truthful evidence class.
ALTER TABLE prediction_runs
    ADD COLUMN IF NOT EXISTS evidence_class TEXT NOT NULL DEFAULT 'legacy'
    CHECK (evidence_class IN ('legacy', 'pending', 'replay', 'live', 'missed'));
ALTER TABLE prediction_runs
    ADD COLUMN IF NOT EXISTS rating_manifest_sha256 TEXT
    CHECK (rating_manifest_sha256 IS NULL OR length(rating_manifest_sha256) = 64);

CREATE TABLE IF NOT EXISTS site_week_selections (
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    run_id TEXT NOT NULL REFERENCES prediction_runs(run_id) ON DELETE RESTRICT,
    selected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reason TEXT NOT NULL,
    PRIMARY KEY (season, week)
);

CREATE TABLE IF NOT EXISTS site_week_selection_history (
    selection_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    prior_run_id TEXT REFERENCES prediction_runs(run_id) ON DELETE RESTRICT,
    run_id TEXT NOT NULL REFERENCES prediction_runs(run_id) ON DELETE RESTRICT,
    reason TEXT NOT NULL,
    selected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_site_week_selection_history_week
    ON site_week_selection_history (season, week, selected_at DESC);

CREATE TABLE IF NOT EXISTS v5_release_policy (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    model_id TEXT NOT NULL,
    inference_bundle_sha256 TEXT NOT NULL CHECK (length(inference_bundle_sha256) = 64),
    first_live_season INTEGER NOT NULL,
    first_live_week INTEGER NOT NULL,
    decision_ref TEXT NOT NULL,
    approved_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS v5_rating_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    source_run_id TEXT NOT NULL,
    source_manifest_sha256 TEXT NOT NULL CHECK (length(source_manifest_sha256) = 64),
    team TEXT NOT NULL,
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    game_id BIGINT,
    snapshot_class TEXT NOT NULL CHECK (snapshot_class IN ('pregame', 'current')),
    cutoff_utc TIMESTAMPTZ NOT NULL,
    offense_rating DOUBLE PRECISION NOT NULL,
    offense_variance DOUBLE PRECISION NOT NULL,
    defense_rating DOUBLE PRECISION NOT NULL,
    defense_variance DOUBLE PRECISION NOT NULL,
    overall_rating DOUBLE PRECISION NOT NULL,
    overall_variance DOUBLE PRECISION NOT NULL,
    fallback_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_v5_rating_snapshots_team
    ON v5_rating_snapshots (season, team, cutoff_utc DESC);
CREATE INDEX IF NOT EXISTS idx_v5_rating_snapshots_current
    ON v5_rating_snapshots (season, cutoff_utc DESC)
    WHERE snapshot_class = 'current';

GRANT SELECT ON site_week_selections TO cks_web;
GRANT SELECT ON v5_rating_snapshots TO cks_web;
GRANT SELECT, INSERT ON v5_rating_snapshots TO cks_pipeline;
GRANT SELECT ON v5_release_policy TO cks_pipeline;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON v5_release_policy FROM cks_pipeline;
GRANT SELECT, INSERT, UPDATE ON site_week_selections TO cks_pipeline;
GRANT SELECT, INSERT ON site_week_selection_history TO cks_pipeline;
GRANT USAGE, SELECT ON SEQUENCE site_week_selection_history_selection_id_seq TO cks_pipeline;

-- The existing V4 serving view remains in force during migration. The
-- selection-only view is activated with the V5 site release after selections
-- have been populated and rehearsed.
