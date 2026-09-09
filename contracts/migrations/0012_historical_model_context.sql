-- Diagnostic-only retrospective context. Never joins or writes canonical live grades.
CREATE TABLE IF NOT EXISTS historical_model_context (
    context_id             TEXT PRIMARY KEY,
    model_id               TEXT NOT NULL,
    model_name             TEXT NOT NULL,
    comparison_season      INTEGER NOT NULL,
    period_scope           TEXT NOT NULL CHECK (period_scope IN ('season', 'week')),
    comparison_week        INTEGER,
    calculation_version    TEXT NOT NULL,
    timing_class           TEXT NOT NULL CHECK (timing_class = 'historically_reconstructed'),
    usage                  TEXT NOT NULL CHECK (usage = 'post_phase5_diagnostic_only'),
    spread_wins            INTEGER NOT NULL CHECK (spread_wins >= 0),
    spread_losses          INTEGER NOT NULL CHECK (spread_losses >= 0),
    spread_pushes          INTEGER NOT NULL CHECK (spread_pushes >= 0),
    spread_compared_games  INTEGER NOT NULL CHECK (spread_compared_games >= 0),
    total_wins             INTEGER NOT NULL CHECK (total_wins >= 0),
    total_losses           INTEGER NOT NULL CHECK (total_losses >= 0),
    total_pushes           INTEGER NOT NULL CHECK (total_pushes >= 0),
    total_compared_games   INTEGER NOT NULL CHECK (total_compared_games >= 0),
    source_artifact_uri    TEXT NOT NULL,
    source_artifact_sha256 TEXT NOT NULL CHECK (length(source_artifact_sha256) = 64),
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK ((period_scope = 'season' AND comparison_week IS NULL) OR
           (period_scope = 'week' AND comparison_week >= 0)),
    CHECK (spread_wins + spread_losses + spread_pushes = spread_compared_games),
    CHECK (total_wins + total_losses + total_pushes = total_compared_games)
);

CREATE UNIQUE INDEX IF NOT EXISTS historical_model_context_season_unique
    ON historical_model_context (model_id, comparison_season, calculation_version)
    WHERE period_scope = 'season';
CREATE UNIQUE INDEX IF NOT EXISTS historical_model_context_week_unique
    ON historical_model_context (model_id, comparison_season, calculation_version, comparison_week)
    WHERE period_scope = 'week';

GRANT SELECT ON historical_model_context TO cks_web;
