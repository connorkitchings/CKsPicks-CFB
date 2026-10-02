-- Migration 0021: matchup data layer v2 (contract 2026-10-02/01-matchup-data-layer-v2).
--
-- Everything the V5 ratings use, per team and week, bound to the exact rating
-- manifest the site serves. Five tables, season-generic:
--   matchup_data_publications   receipt: manifests, payload hash, row counts
--   team_game_measurements      per-game log, faithful to possession_observation
--   team_possession_stats       RAW V5 metrics per as-of week (shown on matchups)
--   team_possession_adjusted    opponent-adjusted values (never read by matchups)
--   team_rating_components      rating decomposition: prior vs per-game evidence
-- No existing table is modified. Published by
-- scripts/pipeline/publish_matchup_data.py; the pipeline role cannot DELETE, so
-- the publisher refuses payloads that would leave stale rows behind.

CREATE TABLE IF NOT EXISTS matchup_data_publications (
    publication_id              TEXT PRIMARY KEY,
    season                      INTEGER NOT NULL,
    lineage                     TEXT NOT NULL CHECK (lineage IN ('intended_update', 'historical_replay')),
    rating_manifest_sha256      TEXT NOT NULL CHECK (length(rating_manifest_sha256) = 64),
    rating_manifest_uri         TEXT NOT NULL,
    measurement_manifest_sha256 TEXT NOT NULL CHECK (length(measurement_manifest_sha256) = 64),
    measurement_manifest_uri    TEXT NOT NULL,
    observations_records_sha    TEXT NOT NULL,
    as_of_weeks                 INTEGER[] NOT NULL,
    rating_scale                JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(rating_scale) = 'object'),
    row_counts                  JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(row_counts) = 'object'),
    payload_sha256              TEXT NOT NULL CHECK (length(payload_sha256) = 64),
    code_sha                    TEXT,
    environment                 TEXT NOT NULL CHECK (environment IN ('preview', 'production')),
    published_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (season, lineage, rating_manifest_sha256, payload_sha256)
);

CREATE TABLE IF NOT EXISTS team_game_measurements (
    season                      INTEGER NOT NULL,
    game_id                     BIGINT NOT NULL,
    team                        TEXT NOT NULL,
    unit_role                   TEXT NOT NULL CHECK (unit_role IN ('offense', 'defense')),
    measurement_id              TEXT NOT NULL CHECK (measurement_id IN (
        'eligible_possessions', 'offensive_possession_points', 'ppp', 'eligible_epa',
        'epa_per_possession', 'eligible_scrimmage_plays', 'plays_per_possession',
        'non_offense_points')),
    week                        INTEGER NOT NULL,
    season_type                 TEXT,
    kickoff_utc                 TIMESTAMPTZ,
    opponent                    TEXT NOT NULL,
    side                        TEXT CHECK (side IN ('home', 'away')),
    numerator                   DOUBLE PRECISION,
    denominator                 DOUBLE PRECISION,
    raw_value                   DOUBLE PRECISION,
    usable_exposure             DOUBLE PRECISION,
    exposure_unit               TEXT,
    coverage_status             TEXT NOT NULL CHECK (coverage_status IN ('observed', 'missing')),
    missing_reason              TEXT,
    quality_flags               TEXT,
    timing_class                TEXT,
    rating_usable               BOOLEAN NOT NULL DEFAULT FALSE,
    opponent_fbs                BOOLEAN,
    measurement_manifest_sha256 TEXT NOT NULL CHECK (length(measurement_manifest_sha256) = 64),
    source_versions             JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(source_versions) = 'object'),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (season, game_id, team, unit_role, measurement_id)
);
CREATE INDEX IF NOT EXISTS idx_team_game_measurements_game
    ON team_game_measurements (season, game_id, team);
CREATE INDEX IF NOT EXISTS idx_team_game_measurements_team_week
    ON team_game_measurements (season, team, week);

CREATE TABLE IF NOT EXISTS team_possession_stats (
    season                      INTEGER NOT NULL,
    as_of_week                  INTEGER NOT NULL,
    team                        TEXT NOT NULL,
    role                        TEXT NOT NULL CHECK (role IN ('offense', 'defense')),
    metric                      TEXT NOT NULL CHECK (metric IN (
        'ppp', 'epa_per_possession', 'epa_per_play', 'plays_per_possession',
        'possessions_per_game', 'non_offense_points_per_game')),
    value                       DOUBLE PRECISION,
    numerator                   DOUBLE PRECISION,
    denominator                 DOUBLE PRECISION,
    n                           DOUBLE PRECISION NOT NULL DEFAULT 0,
    games                       INTEGER NOT NULL DEFAULT 0,
    games_excluded              INTEGER NOT NULL DEFAULT 0,
    excluded                    JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(excluded) = 'array'),
    rank                        INTEGER,
    cohort_size                 INTEGER,
    as_of_cutoff                TIMESTAMPTZ,
    rating_manifest_sha256      TEXT NOT NULL CHECK (length(rating_manifest_sha256) = 64),
    measurement_manifest_sha256 TEXT NOT NULL CHECK (length(measurement_manifest_sha256) = 64),
    source_versions             JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(source_versions) = 'object'),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (season, as_of_week, team, role, metric)
);
CREATE INDEX IF NOT EXISTS idx_team_possession_stats_week
    ON team_possession_stats (season, as_of_week, team);

CREATE TABLE IF NOT EXISTS team_possession_adjusted (
    season                      INTEGER NOT NULL,
    as_of_week                  INTEGER NOT NULL,
    team                        TEXT NOT NULL,
    role                        TEXT NOT NULL CHECK (role IN ('offense', 'defense')),
    measurement_id              TEXT NOT NULL CHECK (measurement_id IN ('ppp', 'epa_per_possession')),
    raw_value                   DOUBLE PRECISION,
    adjusted_value              DOUBLE PRECISION,
    opponent_adjustment         DOUBLE PRECISION,
    adjusted_rank               INTEGER,
    cohort_size                 INTEGER,
    primary_exposure            DOUBLE PRECISION,
    games                       INTEGER NOT NULL DEFAULT 0,
    adjustment_method           TEXT NOT NULL,
    as_of_cutoff                TIMESTAMPTZ,
    rating_manifest_sha256      TEXT NOT NULL CHECK (length(rating_manifest_sha256) = 64),
    measurement_manifest_sha256 TEXT NOT NULL CHECK (length(measurement_manifest_sha256) = 64),
    updated_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (season, as_of_week, team, role, measurement_id)
);
CREATE INDEX IF NOT EXISTS idx_team_possession_adjusted_week
    ON team_possession_adjusted (season, as_of_week, team);

CREATE TABLE IF NOT EXISTS team_rating_components (
    component_id                TEXT PRIMARY KEY,
    v5_snapshot_id              TEXT REFERENCES v5_rating_snapshots(snapshot_id) ON DELETE RESTRICT,
    lineage                     TEXT NOT NULL CHECK (lineage IN ('intended_update', 'historical_replay')),
    candidate_id                TEXT NOT NULL,
    source_manifest_sha256      TEXT NOT NULL CHECK (length(source_manifest_sha256) = 64),
    snapshot_class              TEXT NOT NULL CHECK (snapshot_class IN ('preseason', 'pregame', 'current')),
    season                      INTEGER NOT NULL,
    as_of_week                  INTEGER NOT NULL,
    game_id                     BIGINT,
    cutoff_utc                  TIMESTAMPTZ NOT NULL,
    rating_team                 TEXT NOT NULL,
    team                        TEXT NOT NULL,
    unit_role                   TEXT NOT NULL CHECK (unit_role IN ('offense', 'defense')),
    rating_mean                 DOUBLE PRECISION NOT NULL,
    rating_variance             DOUBLE PRECISION NOT NULL,
    prior_mean                  DOUBLE PRECISION,
    prior_variance              DOUBLE PRECISION,
    prior_weight                DOUBLE PRECISION,
    prior_contribution          DOUBLE PRECISION,
    evidence_weight             DOUBLE PRECISION,
    process_variance            DOUBLE PRECISION,
    k                           DOUBLE PRECISION,
    usable_exposure             DOUBLE PRECISION,
    completed_games             INTEGER,
    evidence                    JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(evidence) = 'array'),
    excluded_observations       JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(excluded_observations) = 'array'),
    prior_detail                JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(prior_detail) = 'object'),
    fallback_reason             TEXT,
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_team_rating_components_snapshot
    ON team_rating_components (v5_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_team_rating_components_week
    ON team_rating_components (season, as_of_week, team);

GRANT SELECT ON matchup_data_publications, team_game_measurements,
    team_possession_stats, team_possession_adjusted, team_rating_components TO cks_web;
GRANT SELECT, INSERT, UPDATE ON matchup_data_publications, team_game_measurements,
    team_possession_stats, team_possession_adjusted, team_rating_components TO cks_pipeline;
