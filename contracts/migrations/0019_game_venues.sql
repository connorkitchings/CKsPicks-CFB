-- Migration 0019: game_venues (venue, city and state per game).
--
-- Additive and independent of prediction runs: `games` is overwritten by every
-- publish run, and runs are immutable once frozen, so venue facts live in their
-- own table keyed by game_id. A missing row simply means "location unknown";
-- the web app tolerates both a missing table and a missing row.
--
-- Populated by scripts/pipeline/publish_game_venues.py from the Silver `games`
-- (venue_id, neutral_site) and `venues` (name, city, state, country_code,
-- timezone) datasets. No existing table or row is modified.

CREATE TABLE IF NOT EXISTS game_venues (
    game_id        BIGINT PRIMARY KEY REFERENCES games(game_id) ON DELETE RESTRICT,
    venue_id       BIGINT,
    venue_name     TEXT,
    city           TEXT,
    state          TEXT,
    country_code   TEXT,
    timezone       TEXT,
    neutral_site   BOOLEAN,
    source         TEXT NOT NULL DEFAULT 'cfbd',
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_game_venues_venue_id
    ON game_venues (venue_id);

GRANT SELECT ON game_venues TO cks_web;
GRANT SELECT, INSERT, UPDATE ON game_venues TO cks_pipeline;
