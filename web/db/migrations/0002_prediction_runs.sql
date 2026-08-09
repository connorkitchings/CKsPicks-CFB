-- Add immutable prediction runs without breaking the legacy games read path.
BEGIN;

CREATE TABLE IF NOT EXISTS prediction_runs (
    run_id TEXT PRIMARY KEY,
    season INTEGER NOT NULL,
    week INTEGER NOT NULL,
    state TEXT NOT NULL CHECK (state IN ('preview', 'published', 'frozen', 'scored')),
    expected_games INTEGER NOT NULL CHECK (expected_games >= 0),
    predicted_games INTEGER NOT NULL CHECK (predicted_games >= 0),
    lined_games INTEGER NOT NULL CHECK (lined_games >= 0),
    data_as_of TIMESTAMPTZ NOT NULL,
    source_config TEXT,
    system_name TEXT,
    model_id TEXT,
    code_sha TEXT,
    config_sha TEXT,
    model_bundle_sha256 TEXT,
    artifact_uri TEXT NOT NULL,
    artifact_sha256 TEXT NOT NULL,
    validation JSONB NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(validation) = 'object'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    published_at TIMESTAMPTZ,
    frozen_at TIMESTAMPTZ,
    scored_at TIMESTAMPTZ,
    UNIQUE (season, week, run_id),
    CHECK (predicted_games <= expected_games),
    CHECK (lined_games <= expected_games)
);

CREATE INDEX IF NOT EXISTS idx_prediction_runs_week_state
    ON prediction_runs (season, week, state, created_at DESC);

CREATE TABLE IF NOT EXISTS predictions (
    run_id TEXT NOT NULL REFERENCES prediction_runs(run_id) ON DELETE RESTRICT,
    game_id BIGINT NOT NULL REFERENCES games(game_id) ON DELETE RESTRICT,
    home_team_spread_line DOUBLE PRECISION,
    total_line DOUBLE PRECISION,
    predicted_spread DOUBLE PRECISION,
    predicted_total DOUBLE PRECISION,
    predicted_spread_std_dev DOUBLE PRECISION,
    predicted_total_std_dev DOUBLE PRECISION,
    spread_lean lean_side,
    total_lean total_side,
    edge_spread DOUBLE PRECISION,
    edge_total DOUBLE PRECISION,
    high_confidence BOOLEAN NOT NULL DEFAULT FALSE,
    high_confidence_eligible BOOLEAN NOT NULL DEFAULT FALSE,
    home_completed_games INTEGER NOT NULL DEFAULT 0 CHECK (home_completed_games >= 0),
    away_completed_games INTEGER NOT NULL DEFAULT 0 CHECK (away_completed_games >= 0),
    regime TEXT NOT NULL CHECK (regime IN ('preseason', 'one_game', 'two_games', 'three_games', 'established')),
    spread_model_version TEXT,
    total_model_version TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (run_id, game_id)
);

CREATE INDEX IF NOT EXISTS idx_predictions_game_id ON predictions (game_id);
CREATE INDEX IF NOT EXISTS idx_predictions_run_confidence
    ON predictions (run_id, high_confidence) WHERE high_confidence = TRUE;

ALTER TABLE current_week
    ADD COLUMN IF NOT EXISTS active_run_id TEXT REFERENCES prediction_runs(run_id) ON DELETE RESTRICT;

-- Preserve pre-migration published rows as immutable synthetic legacy runs.
INSERT INTO prediction_runs (
    run_id, season, week, state, expected_games, predicted_games, lined_games,
    data_as_of, source_config, system_name, model_id, artifact_uri,
    artifact_sha256, validation, published_at, frozen_at, scored_at
)
SELECT
    'legacy-' || season || '-w' || week,
    season,
    week,
    CASE WHEN bool_and(gr.game_id IS NOT NULL) THEN 'scored' ELSE 'frozen' END,
    COUNT(*)::INTEGER,
    COUNT(*) FILTER (
        WHERE predicted_spread IS NOT NULL AND predicted_total IS NOT NULL
    )::INTEGER,
    COUNT(*) FILTER (
        WHERE home_team_spread_line IS NOT NULL AND total_line IS NOT NULL
    )::INTEGER,
    MAX(g.updated_at),
    MAX(source_config),
    MAX(system_name),
    MAX(model_id),
    'legacy://database/' || season || '/week/' || week,
    repeat('0', 64),
    '{"synthetic_legacy_run": true}'::jsonb,
    MAX(g.updated_at),
    MAX(g.updated_at),
    CASE WHEN bool_and(gr.game_id IS NOT NULL) THEN MAX(g.updated_at) ELSE NULL END
FROM games g
LEFT JOIN game_results gr USING (game_id)
GROUP BY season, week
ON CONFLICT (run_id) DO NOTHING;

INSERT INTO predictions (
    run_id, game_id, home_team_spread_line, total_line,
    predicted_spread, predicted_total, predicted_spread_std_dev,
    predicted_total_std_dev, spread_lean, total_lean, edge_spread,
    edge_total, high_confidence, high_confidence_eligible, regime,
    spread_model_version, total_model_version
)
SELECT
    'legacy-' || season || '-w' || week,
    game_id, home_team_spread_line, total_line,
    predicted_spread, predicted_total, predicted_spread_std_dev,
    predicted_total_std_dev, spread_lean, total_lean, edge_spread,
    edge_total, high_confidence, high_confidence, 'established',
    model_id, model_id
FROM games
ON CONFLICT (run_id, game_id) DO NOTHING;

UPDATE current_week
SET active_run_id = 'legacy-' || season || '-w' || week
WHERE id = 1 AND active_run_id IS NULL
  AND EXISTS (
      SELECT 1 FROM prediction_runs
      WHERE run_id = 'legacy-' || current_week.season || '-w' || current_week.week
  );

CREATE OR REPLACE VIEW active_game_predictions AS
WITH selected_runs AS (
    SELECT DISTINCT ON (pr.season, pr.week)
        pr.run_id, pr.season, pr.week, pr.state, pr.created_at
    FROM prediction_runs pr
    LEFT JOIN current_week cw
      ON cw.id = 1 AND cw.season = pr.season AND cw.week = pr.week
    WHERE pr.run_id = cw.active_run_id OR pr.state IN ('frozen', 'scored')
    ORDER BY pr.season, pr.week,
             (pr.run_id = cw.active_run_id) DESC,
             (pr.state IN ('frozen', 'scored')) DESC,
             pr.created_at DESC
)
SELECT
    g.game_id, g.season, g.week, g.start_date, g.home_team, g.away_team,
    p.*, sr.state AS run_state, sr.created_at AS run_created_at
FROM selected_runs sr
JOIN predictions p ON p.run_id = sr.run_id
JOIN games g ON g.game_id = p.game_id;

COMMIT;
