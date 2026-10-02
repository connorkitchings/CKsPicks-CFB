-- Migration 0020: team_season_stats (pre-game team stats and national ranks).
--
-- Long format, one row per (season, as_of_week, team, role, metric).
-- `as_of_week` N means "games completed before week N's slate", so every game
-- in week N reads the same leak-free snapshot. `value` is null when the team
-- has no qualifying sample; `rank`/`cohort_size` are null below the minimum
-- games threshold. Computed from FBS-vs-FBS games, garbage time excluded, by
-- src/cks_picks_cfb/data/team_stats.py and published by
-- scripts/pipeline/publish_team_stats.py. No existing table is modified, and
-- the table holds no model or market fields.

CREATE TABLE IF NOT EXISTS team_season_stats (
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
    PRIMARY KEY (season, as_of_week, team, role, metric)
);

CREATE INDEX IF NOT EXISTS idx_team_season_stats_week
    ON team_season_stats (season, as_of_week);

GRANT SELECT ON team_season_stats TO cks_web;
GRANT SELECT, INSERT, UPDATE ON team_season_stats TO cks_pipeline;
