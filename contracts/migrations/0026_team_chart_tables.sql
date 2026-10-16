-- Weekly team-chart projections (charts_v1). Additive: no existing table, grant or
-- release changes. Live copies mirror the release tables without release_id.
CREATE TABLE IF NOT EXISTS team_season_roster (
    season     INTEGER NOT NULL,
    team       TEXT NOT NULL,
    conference TEXT,
    PRIMARY KEY (season, team)
);

CREATE TABLE IF NOT EXISTS team_game_stats (
    season          INTEGER NOT NULL,
    week            INTEGER NOT NULL,
    game_id         BIGINT NOT NULL,
    team            TEXT NOT NULL,
    opponent        TEXT NOT NULL,
    site            TEXT NOT NULL CHECK (site IN ('home', 'away', 'neutral')),
    points_for      INTEGER NOT NULL,
    points_against  INTEGER NOT NULL,
    off_plays       INTEGER NOT NULL,
    off_success_n   INTEGER NOT NULL,
    off_success_sum DOUBLE PRECISION NOT NULL,
    off_epa_n       INTEGER NOT NULL,
    off_epa_sum     DOUBLE PRECISION NOT NULL,
    def_plays       INTEGER NOT NULL,
    def_success_n   INTEGER NOT NULL,
    def_success_sum DOUBLE PRECISION NOT NULL,
    def_epa_n       INTEGER NOT NULL,
    def_epa_sum     DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (season, game_id, team)
);

CREATE TABLE IF NOT EXISTS team_adjusted_epa (
    season                INTEGER NOT NULL,
    as_of_week            INTEGER NOT NULL,
    team                  TEXT NOT NULL,
    role                  TEXT NOT NULL CHECK (role IN ('offense', 'defense')),
    raw_epa_per_play      DOUBLE PRECISION NOT NULL,
    venue_correction      DOUBLE PRECISION NOT NULL,
    neutral_epa_per_play  DOUBLE PRECISION NOT NULL,
    opponent_adjustment   DOUBLE PRECISION NOT NULL,
    adjusted_epa_per_play DOUBLE PRECISION NOT NULL,
    venue_coefficient     DOUBLE PRECISION NOT NULL,
    venue_identified      BOOLEAN NOT NULL,
    epa_n                 INTEGER NOT NULL,
    games                 INTEGER NOT NULL,
    adjusted_rank         INTEGER NOT NULL,
    cohort_size           INTEGER NOT NULL,
    adjustment_method     TEXT NOT NULL,
    PRIMARY KEY (season, as_of_week, team, role)
);

CREATE TABLE IF NOT EXISTS season_release_team_season_roster (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    season     INTEGER NOT NULL,
    team       TEXT NOT NULL,
    conference TEXT,
    PRIMARY KEY (release_id, season, team)
);

CREATE TABLE IF NOT EXISTS season_release_team_game_stats (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    season          INTEGER NOT NULL,
    week            INTEGER NOT NULL,
    game_id         BIGINT NOT NULL,
    team            TEXT NOT NULL,
    opponent        TEXT NOT NULL,
    site            TEXT NOT NULL CHECK (site IN ('home', 'away', 'neutral')),
    points_for      INTEGER NOT NULL,
    points_against  INTEGER NOT NULL,
    off_plays       INTEGER NOT NULL,
    off_success_n   INTEGER NOT NULL,
    off_success_sum DOUBLE PRECISION NOT NULL,
    off_epa_n       INTEGER NOT NULL,
    off_epa_sum     DOUBLE PRECISION NOT NULL,
    def_plays       INTEGER NOT NULL,
    def_success_n   INTEGER NOT NULL,
    def_success_sum DOUBLE PRECISION NOT NULL,
    def_epa_n       INTEGER NOT NULL,
    def_epa_sum     DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (release_id, season, game_id, team)
);

CREATE TABLE IF NOT EXISTS season_release_team_adjusted_epa (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    season                INTEGER NOT NULL,
    as_of_week            INTEGER NOT NULL,
    team                  TEXT NOT NULL,
    role                  TEXT NOT NULL CHECK (role IN ('offense', 'defense')),
    raw_epa_per_play      DOUBLE PRECISION NOT NULL,
    venue_correction      DOUBLE PRECISION NOT NULL,
    neutral_epa_per_play  DOUBLE PRECISION NOT NULL,
    opponent_adjustment   DOUBLE PRECISION NOT NULL,
    adjusted_epa_per_play DOUBLE PRECISION NOT NULL,
    venue_coefficient     DOUBLE PRECISION NOT NULL,
    venue_identified      BOOLEAN NOT NULL,
    epa_n                 INTEGER NOT NULL,
    games                 INTEGER NOT NULL,
    adjusted_rank         INTEGER NOT NULL,
    cohort_size           INTEGER NOT NULL,
    adjustment_method     TEXT NOT NULL,
    PRIMARY KEY (release_id, season, as_of_week, team, role)
);

DROP TRIGGER IF EXISTS immutable_projection ON season_release_team_season_roster;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_team_season_roster
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_team_game_stats;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_team_game_stats
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();
DROP TRIGGER IF EXISTS immutable_projection ON season_release_team_adjusted_epa;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_team_adjusted_epa
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();

-- Explicit revokes first, as in 0025: default privileges would otherwise leave
-- cks_pipeline SELECT/INSERT/UPDATE and cks_web SELECT on every new table. The live
-- copies are never read or written by the application (chart queries use release
-- CTEs that shadow them), so only the owner keeps access to them.
REVOKE ALL ON team_season_roster, team_game_stats, team_adjusted_epa
    FROM PUBLIC, cks_pipeline, cks_web;
REVOKE ALL ON season_release_team_season_roster,
    season_release_team_game_stats,
    season_release_team_adjusted_epa
    FROM PUBLIC, cks_pipeline, cks_web;
GRANT SELECT ON season_release_team_season_roster TO cks_web;
GRANT SELECT, INSERT ON season_release_team_season_roster TO cks_pipeline;
GRANT SELECT ON season_release_team_game_stats TO cks_web;
GRANT SELECT, INSERT ON season_release_team_game_stats TO cks_pipeline;
GRANT SELECT ON season_release_team_adjusted_epa TO cks_web;
GRANT SELECT, INSERT ON season_release_team_adjusted_epa TO cks_pipeline;
