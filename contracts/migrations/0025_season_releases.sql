-- Additive season releases. No legacy selection or serving table is changed.
CREATE TABLE IF NOT EXISTS season_release_policies (
    environment TEXT NOT NULL CHECK (environment IN ('preview', 'production')),
    season INTEGER NOT NULL,
    model_manifest_sha256 TEXT NOT NULL CHECK (model_manifest_sha256 ~ '^[0-9a-f]{64}$'),
    workflow_version TEXT NOT NULL,
    grading_policy_sha256 TEXT NOT NULL CHECK (grading_policy_sha256 ~ '^[0-9a-f]{64}$'),
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    decision_ref TEXT NOT NULL CHECK (length(trim(decision_ref)) > 0),
    installed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (environment, season)
);
CREATE TABLE IF NOT EXISTS season_releases (
    release_id TEXT PRIMARY KEY,
    environment TEXT NOT NULL CHECK (environment IN ('preview', 'production')),
    season INTEGER NOT NULL,
    model_manifest_sha256 TEXT NOT NULL CHECK (model_manifest_sha256 ~ '^[0-9a-f]{64}$'),
    revision_manifest_sha256 TEXT NOT NULL CHECK (revision_manifest_sha256 ~ '^[0-9a-f]{64}$'),
    workflow_version TEXT NOT NULL,
    grading_policy_sha256 TEXT NOT NULL CHECK (grading_policy_sha256 ~ '^[0-9a-f]{64}$'),
    code_sha TEXT NOT NULL,
    config_sha TEXT NOT NULL,
    run_manifest_uri TEXT NOT NULL,
    run_manifest_sha256 TEXT NOT NULL CHECK (run_manifest_sha256 ~ '^[0-9a-f]{64}$'),
    verification_uri TEXT NOT NULL,
    verification_sha256 TEXT NOT NULL CHECK (verification_sha256 ~ '^[0-9a-f]{64}$'),
    active_week INTEGER NOT NULL CHECK (active_week >= 0),
    status TEXT NOT NULL DEFAULT 'staged' CHECK (status IN ('staged','active','superseded','rolled_back')),
    projection_checks JSONB NOT NULL CHECK (jsonb_typeof(projection_checks) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    activated_at TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS season_releases_one_active
    ON season_releases (environment, season) WHERE status = 'active';
CREATE TABLE IF NOT EXISTS season_release_history (
    activation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    environment TEXT NOT NULL CHECK (environment IN ('preview', 'production')),
    season INTEGER NOT NULL,
    prior_release_id TEXT REFERENCES season_releases(release_id) ON DELETE RESTRICT,
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,
    action TEXT NOT NULL CHECK (action IN ('activate', 'rollback')),
    decision_ref TEXT NOT NULL,
    readback_sha256 TEXT NOT NULL CHECK (readback_sha256 ~ '^[0-9a-f]{64}$'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS season_release_games (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    game_id              BIGINT NOT NULL,
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
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (release_id, game_id)
);

CREATE TABLE IF NOT EXISTS season_release_game_venues (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    game_id        BIGINT NOT NULL,
    venue_id       BIGINT,
    venue_name     TEXT,
    city           TEXT,
    state          TEXT,
    country_code   TEXT,
    timezone       TEXT,
    neutral_site   BOOLEAN,
    source         TEXT NOT NULL DEFAULT 'cfbd',
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (release_id, game_id)
);

CREATE TABLE IF NOT EXISTS season_release_game_results (
    completion_state TEXT NOT NULL DEFAULT 'completed',
    source_dataset_version_id TEXT,
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    game_id        BIGINT NOT NULL,
    home_points    INTEGER,
    away_points    INTEGER,
    spread_result  bet_result,
    total_result   bet_result,
    scored_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (release_id, game_id)
);

CREATE TABLE IF NOT EXISTS season_release_predictions (
    market_snapshot_id TEXT,
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    run_id                    TEXT NOT NULL,
    game_id                   BIGINT NOT NULL,
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
    regime                    TEXT NOT NULL CHECK (regime IN ('preseason', 'one_game', 'two_games', 'three_games', 'game_1', 'game_2', 'game_3', 'game_4', 'established')),
    spread_model_version      TEXT,
    total_model_version       TEXT,
    created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (release_id, run_id, game_id)
);

CREATE TABLE IF NOT EXISTS season_release_prediction_grades (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    run_id             TEXT NOT NULL,
    game_id            BIGINT NOT NULL,
    target             TEXT NOT NULL CHECK (target IN ('spread', 'total')),
    market_snapshot_id TEXT,
    market_quote_id    TEXT,
    side               TEXT NOT NULL CHECK (side IN ('home', 'away', 'over', 'under')),
    result             bet_result NOT NULL,
    profit_units       NUMERIC(10, 4) NOT NULL,
    grading_version    TEXT NOT NULL,
    graded_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (release_id, run_id, game_id, target)
);

CREATE TABLE IF NOT EXISTS season_release_market_quotes (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    quote_id       TEXT NOT NULL,
    game_id        BIGINT NOT NULL,
    provider       TEXT NOT NULL,
    captured_at    TIMESTAMPTZ NOT NULL,
    spread         DOUBLE PRECISION,
    total          DOUBLE PRECISION,
    source_capture_id TEXT,
    home_spread_price DOUBLE PRECISION,
    away_spread_price DOUBLE PRECISION,
    over_price     DOUBLE PRECISION,
    under_price    DOUBLE PRECISION,
    quote_updated_at TIMESTAMPTZ,
    source_event_id TEXT,
    CHECK (spread IS NOT NULL OR total IS NOT NULL),
    PRIMARY KEY (release_id, quote_id)
);

CREATE TABLE IF NOT EXISTS season_release_market_snapshots (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    snapshot_id          TEXT NOT NULL,
    game_id              BIGINT NOT NULL,
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
    PRIMARY KEY (release_id, snapshot_id)
);

CREATE TABLE IF NOT EXISTS season_release_market_snapshot_quotes (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    snapshot_id TEXT NOT NULL,
    quote_id    TEXT NOT NULL,
    target      TEXT NOT NULL CHECK (target IN ('spread', 'total')),
    PRIMARY KEY (release_id, snapshot_id, quote_id, target)
);

CREATE TABLE IF NOT EXISTS season_release_prediction_market_selections (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    run_id          TEXT NOT NULL,
    game_id         BIGINT NOT NULL,
    target          TEXT NOT NULL CHECK (target IN ('spread', 'total')),
    snapshot_id     TEXT NOT NULL,
    quote_id        TEXT NOT NULL,
    side            TEXT NOT NULL CHECK (side IN ('home', 'away', 'over', 'under')),
    point           DOUBLE PRECISION NOT NULL,
    price           DOUBLE PRECISION NOT NULL,
    edge            DOUBLE PRECISION NOT NULL CHECK (edge >= 0),
    policy_version  TEXT NOT NULL CHECK (length(trim(policy_version)) > 0),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (release_id, run_id, game_id, target)
);

CREATE TABLE IF NOT EXISTS season_release_system_stats (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    season         INTEGER NOT NULL,
    as_of_week     INTEGER NOT NULL,
    spread_wins    INTEGER NOT NULL DEFAULT 0,
    spread_losses  INTEGER NOT NULL DEFAULT 0,
    spread_pushes  INTEGER NOT NULL DEFAULT 0,
    total_wins     INTEGER NOT NULL DEFAULT 0,
    total_losses   INTEGER NOT NULL DEFAULT 0,
    total_pushes   INTEGER NOT NULL DEFAULT 0,
    spread_profit_units NUMERIC(12, 4) NOT NULL DEFAULT 0,
    total_profit_units  NUMERIC(12, 4) NOT NULL DEFAULT 0,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (release_id, season)
);

CREATE TABLE IF NOT EXISTS season_release_v5_rating_snapshots (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    snapshot_id TEXT NOT NULL,
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
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (release_id, snapshot_id)
);

CREATE TABLE IF NOT EXISTS season_release_team_season_stats (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    season       INTEGER NOT NULL,
    as_of_week   INTEGER NOT NULL,
    team         TEXT NOT NULL,
    role         TEXT NOT NULL CHECK (role IN ('offense', 'defense')),
    metric       TEXT NOT NULL,
    value        DOUBLE PRECISION,
    n            INTEGER NOT NULL DEFAULT 0,
    games        INTEGER NOT NULL DEFAULT 0,
    rank         INTEGER,
    cohort_size  INTEGER,
    -- Silver dataset version ids (byplay, drives, games, game_outcomes, teams)
    -- that produced the row, so a snapshot is traceable to its exact inputs.
    source_versions JSONB NOT NULL DEFAULT '{}'::jsonb
        CHECK (jsonb_typeof(source_versions) = 'object'),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (release_id, season, as_of_week, team, role, metric)
);

CREATE TABLE IF NOT EXISTS season_release_matchup_data_publications (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    publication_id              TEXT NOT NULL,
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
    PRIMARY KEY (release_id, publication_id)
);

CREATE TABLE IF NOT EXISTS season_release_team_game_measurements (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

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
    PRIMARY KEY (release_id, season, game_id, team, unit_role, measurement_id)
);

CREATE TABLE IF NOT EXISTS season_release_team_possession_stats (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

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
    PRIMARY KEY (release_id, season, as_of_week, team, role, metric)
);

CREATE TABLE IF NOT EXISTS season_release_team_possession_adjusted (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

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
    PRIMARY KEY (release_id, season, as_of_week, team, role, measurement_id)
);

CREATE TABLE IF NOT EXISTS season_release_team_rating_components (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    component_id                TEXT NOT NULL,
    v5_snapshot_id              TEXT,
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
    created_at                  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (release_id, component_id)
);

CREATE TABLE IF NOT EXISTS season_release_site_week_selections (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    run_id TEXT NOT NULL,
    selected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reason TEXT NOT NULL,
    PRIMARY KEY (release_id, season, week)
);

-- SECURITY DEFINER: the staged-release row lock (FOR KEY SHARE) needs UPDATE
-- privilege on season_releases, which the pipeline deliberately does not hold.
CREATE OR REPLACE FUNCTION reject_season_projection_mutation()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN RAISE EXCEPTION 'season release projections are immutable'; END IF;
    PERFORM 1 FROM season_releases WHERE release_id = NEW.release_id AND status = 'staged' FOR KEY SHARE;
    IF NOT FOUND THEN RAISE EXCEPTION 'projection insert requires a staged release'; END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS immutable_projection ON season_release_games;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_games
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_game_venues;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_game_venues
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_game_results;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_game_results
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_predictions;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_predictions
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_prediction_grades;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_prediction_grades
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_market_quotes;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_market_quotes
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_market_snapshots;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_market_snapshots
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_market_snapshot_quotes;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_market_snapshot_quotes
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_prediction_market_selections;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_prediction_market_selections
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_system_stats;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_system_stats
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_v5_rating_snapshots;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_v5_rating_snapshots
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_team_season_stats;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_team_season_stats
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_matchup_data_publications;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_matchup_data_publications
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_team_game_measurements;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_team_game_measurements
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_team_possession_stats;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_team_possession_stats
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_team_possession_adjusted;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_team_possession_adjusted
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_team_rating_components;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_team_rating_components
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_site_week_selections;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_site_week_selections
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();

REVOKE ALL ON season_release_policies FROM PUBLIC, cks_pipeline, cks_web;
GRANT SELECT ON season_release_policies TO cks_pipeline;
-- Explicit revokes first: the schema's ALTER DEFAULT PRIVILEGES would otherwise
-- leave cks_pipeline SELECT/INSERT/UPDATE and cks_web SELECT on every new table.
REVOKE ALL ON season_releases, season_release_history FROM PUBLIC, cks_pipeline, cks_web;
REVOKE ALL ON SEQUENCE season_release_history_activation_id_seq FROM PUBLIC, cks_pipeline, cks_web;
REVOKE ALL ON season_release_games, season_release_game_venues, season_release_game_results,
    season_release_predictions, season_release_prediction_grades, season_release_market_quotes,
    season_release_market_snapshots, season_release_market_snapshot_quotes,
    season_release_prediction_market_selections, season_release_system_stats,
    season_release_v5_rating_snapshots, season_release_team_season_stats,
    season_release_matchup_data_publications, season_release_team_game_measurements,
    season_release_team_possession_stats, season_release_team_possession_adjusted,
    season_release_team_rating_components, season_release_site_week_selections
    FROM PUBLIC, cks_pipeline, cks_web;
GRANT SELECT ON season_releases TO cks_web;
-- The pipeline stages releases; it activates only through activate_season_release().
GRANT SELECT, INSERT ON season_releases TO cks_pipeline;
GRANT SELECT ON season_release_history TO cks_pipeline;
GRANT SELECT ON season_release_games TO cks_web;
GRANT SELECT, INSERT ON season_release_games TO cks_pipeline;
GRANT SELECT ON season_release_game_venues TO cks_web;
GRANT SELECT, INSERT ON season_release_game_venues TO cks_pipeline;
GRANT SELECT ON season_release_game_results TO cks_web;
GRANT SELECT, INSERT ON season_release_game_results TO cks_pipeline;
GRANT SELECT ON season_release_predictions TO cks_web;
GRANT SELECT, INSERT ON season_release_predictions TO cks_pipeline;
GRANT SELECT ON season_release_prediction_grades TO cks_web;
GRANT SELECT, INSERT ON season_release_prediction_grades TO cks_pipeline;
GRANT SELECT ON season_release_market_quotes TO cks_web;
GRANT SELECT, INSERT ON season_release_market_quotes TO cks_pipeline;
GRANT SELECT ON season_release_market_snapshots TO cks_web;
GRANT SELECT, INSERT ON season_release_market_snapshots TO cks_pipeline;
GRANT SELECT ON season_release_market_snapshot_quotes TO cks_web;
GRANT SELECT, INSERT ON season_release_market_snapshot_quotes TO cks_pipeline;
GRANT SELECT ON season_release_prediction_market_selections TO cks_web;
GRANT SELECT, INSERT ON season_release_prediction_market_selections TO cks_pipeline;
GRANT SELECT ON season_release_system_stats TO cks_web;
GRANT SELECT, INSERT ON season_release_system_stats TO cks_pipeline;
GRANT SELECT ON season_release_v5_rating_snapshots TO cks_web;
GRANT SELECT, INSERT ON season_release_v5_rating_snapshots TO cks_pipeline;
GRANT SELECT ON season_release_team_season_stats TO cks_web;
GRANT SELECT, INSERT ON season_release_team_season_stats TO cks_pipeline;
GRANT SELECT ON season_release_matchup_data_publications TO cks_web;
GRANT SELECT, INSERT ON season_release_matchup_data_publications TO cks_pipeline;
GRANT SELECT ON season_release_team_game_measurements TO cks_web;
GRANT SELECT, INSERT ON season_release_team_game_measurements TO cks_pipeline;
GRANT SELECT ON season_release_team_possession_stats TO cks_web;
GRANT SELECT, INSERT ON season_release_team_possession_stats TO cks_pipeline;
GRANT SELECT ON season_release_team_possession_adjusted TO cks_web;
GRANT SELECT, INSERT ON season_release_team_possession_adjusted TO cks_pipeline;
GRANT SELECT ON season_release_team_rating_components TO cks_web;
GRANT SELECT, INSERT ON season_release_team_rating_components TO cks_pipeline;
GRANT SELECT ON season_release_site_week_selections TO cks_web;
GRANT SELECT, INSERT ON season_release_site_week_selections TO cks_pipeline;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'season_release_predictions_run_fk' AND conrelid = 'season_release_predictions'::regclass) THEN
  ALTER TABLE season_release_predictions ADD CONSTRAINT season_release_predictions_run_fk FOREIGN KEY (run_id) REFERENCES prediction_runs(run_id) ON DELETE RESTRICT;
 END IF;
END $$;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'season_release_prediction_grades_run_fk' AND conrelid = 'season_release_prediction_grades'::regclass) THEN
  ALTER TABLE season_release_prediction_grades ADD CONSTRAINT season_release_prediction_grades_run_fk FOREIGN KEY (run_id) REFERENCES prediction_runs(run_id) ON DELETE RESTRICT;
 END IF;
END $$;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'season_release_prediction_market_selections_run_fk' AND conrelid = 'season_release_prediction_market_selections'::regclass) THEN
  ALTER TABLE season_release_prediction_market_selections ADD CONSTRAINT season_release_prediction_market_selections_run_fk FOREIGN KEY (run_id) REFERENCES prediction_runs(run_id) ON DELETE RESTRICT;
 END IF;
END $$;
DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'season_release_site_week_selections_run_fk' AND conrelid = 'season_release_site_week_selections'::regclass) THEN
  ALTER TABLE season_release_site_week_selections ADD CONSTRAINT season_release_site_week_selections_run_fk FOREIGN KEY (run_id) REFERENCES prediction_runs(run_id) ON DELETE RESTRICT;
 END IF;
END $$;

-- Pipeline sessions are identified by session_user, which stays the login role
-- inside activate_season_release() (where current_user is the definer).
CREATE OR REPLACE FUNCTION validate_season_release_transition()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    policy season_release_policies%ROWTYPE;
    pipeline_login TEXT;
BEGIN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'season releases are retained'; END IF;
    pipeline_login := CASE WHEN NEW.environment = 'preview' THEN 'cks_preview_pipeline' ELSE 'cks_prod_pipeline' END;
    IF TG_OP = 'INSERT' THEN
        IF NEW.status <> 'staged' THEN RAISE EXCEPTION 'release must be staged first'; END IF;
        IF (session_user LIKE '%_pipeline' OR current_user LIKE '%_pipeline')
           AND (session_user <> pipeline_login OR current_user <> session_user) THEN
            RAISE EXCEPTION 'wrong release environment role';
        END IF;
        RETURN NEW;
    END IF;
    IF (to_jsonb(NEW) - 'status' - 'activated_at') IS DISTINCT FROM
       (to_jsonb(OLD) - 'status' - 'activated_at') THEN
        RAISE EXCEPTION 'release manifest and verification are immutable';
    END IF;
    IF session_user LIKE '%_pipeline' OR current_user LIKE '%_pipeline' THEN
        IF session_user <> pipeline_login THEN RAISE EXCEPTION 'wrong release environment role'; END IF;
        IF NOT ((OLD.status = 'staged' AND NEW.status = 'active')
             OR (OLD.status = 'active' AND NEW.status = 'superseded')) THEN
            RAISE EXCEPTION 'pipeline may not roll back releases';
        END IF;
        IF NEW.status = 'active' THEN
            SELECT * INTO policy FROM season_release_policies
              WHERE environment = NEW.environment AND season = NEW.season;
            IF NOT FOUND OR NOT policy.enabled
               OR policy.model_manifest_sha256 <> NEW.model_manifest_sha256
               OR policy.workflow_version <> NEW.workflow_version
               OR policy.grading_policy_sha256 <> NEW.grading_policy_sha256 THEN
                RAISE EXCEPTION 'owner policy does not authorize this release';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS season_release_transition ON season_releases;
CREATE TRIGGER season_release_transition BEFORE INSERT OR UPDATE OR DELETE ON season_releases
    FOR EACH ROW EXECUTE FUNCTION validate_season_release_transition();
CREATE OR REPLACE FUNCTION reject_season_release_history_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'season release history is append-only'; END;
$$;
DROP TRIGGER IF EXISTS season_release_history_immutable ON season_release_history;
CREATE TRIGGER season_release_history_immutable BEFORE UPDATE OR DELETE ON season_release_history
    FOR EACH ROW EXECUTE FUNCTION reject_season_release_history_mutation();

-- The only pipeline activation path. Runs as the owner so the pipeline needs no
-- UPDATE on season_releases, no INSERT on history and no policy row lock grant;
-- session_user is still the caller's login and must match the environment.
CREATE OR REPLACE FUNCTION activate_season_release(
    p_release_id TEXT, p_expected_previous_release_id TEXT, p_readback_sha256 TEXT)
RETURNS TEXT LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
DECLARE
    candidate public.season_releases%ROWTYPE;
    policy public.season_release_policies%ROWTYPE;
    previous TEXT;
BEGIN
    SELECT * INTO candidate FROM public.season_releases WHERE release_id = p_release_id;
    IF NOT FOUND THEN RAISE EXCEPTION 'release does not exist'; END IF;
    IF session_user <> (CASE WHEN candidate.environment = 'preview' THEN 'cks_preview_pipeline' ELSE 'cks_prod_pipeline' END) THEN
        RAISE EXCEPTION 'wrong release environment role';
    END IF;
    PERFORM pg_catalog.pg_advisory_xact_lock(pg_catalog.hashtextextended(
        'season-release:' || candidate.environment || ':' || candidate.season, 0));
    SELECT * INTO policy FROM public.season_release_policies
      WHERE environment = candidate.environment AND season = candidate.season FOR SHARE;
    IF NOT FOUND OR NOT policy.enabled
       OR policy.model_manifest_sha256 <> candidate.model_manifest_sha256
       OR policy.workflow_version <> candidate.workflow_version
       OR policy.grading_policy_sha256 <> candidate.grading_policy_sha256 THEN
        RAISE EXCEPTION 'owner policy does not authorize this release';
    END IF;
    SELECT * INTO candidate FROM public.season_releases WHERE release_id = p_release_id FOR UPDATE;
    IF candidate.status <> 'staged' THEN RAISE EXCEPTION 'candidate has invalid activation status'; END IF;
    SELECT release_id INTO previous FROM public.season_releases
      WHERE environment = candidate.environment AND season = candidate.season AND status = 'active' FOR UPDATE;
    IF previous IS DISTINCT FROM p_expected_previous_release_id THEN
        RAISE EXCEPTION 'active release changed since review';
    END IF;
    IF previous IS NOT NULL THEN
        UPDATE public.season_releases SET status = 'superseded' WHERE release_id = previous;
    END IF;
    UPDATE public.season_releases SET status = 'active', activated_at = pg_catalog.now()
      WHERE release_id = p_release_id;
    INSERT INTO public.season_release_history
        (environment, season, prior_release_id, release_id, action, decision_ref, readback_sha256)
      VALUES (candidate.environment, candidate.season, previous, p_release_id, 'activate',
              policy.decision_ref, p_readback_sha256);
    RETURN previous;
END;
$$;
REVOKE ALL ON FUNCTION activate_season_release(TEXT, TEXT, TEXT) FROM PUBLIC, cks_pipeline, cks_web;
GRANT EXECUTE ON FUNCTION activate_season_release(TEXT, TEXT, TEXT) TO cks_pipeline;
REVOKE ALL ON FUNCTION reject_season_projection_mutation() FROM PUBLIC, cks_pipeline, cks_web;

DO $$ BEGIN
 IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'season_release_selection_slate_fk' AND conrelid = 'season_release_site_week_selections'::regclass) THEN
  ALTER TABLE season_release_site_week_selections ADD CONSTRAINT season_release_selection_slate_fk
    FOREIGN KEY (season, week, run_id) REFERENCES prediction_runs(season, week, run_id) ON DELETE RESTRICT;
 END IF;
END $$;
