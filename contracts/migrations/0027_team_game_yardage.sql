-- Team-game yardage projection (charts_v2). Additive: no existing table, grant or
-- release changes, so retained charts_v1 releases read back unchanged. The live
-- copy mirrors the release table without release_id.
CREATE TABLE IF NOT EXISTS team_game_yardage (
    season                INTEGER NOT NULL,
    game_id               BIGINT NOT NULL,
    team                  TEXT NOT NULL,
    off_yards_n           INTEGER NOT NULL,
    off_explosive_n       INTEGER NOT NULL,
    off_success_yards_n   INTEGER NOT NULL,
    off_success_yards_sum DOUBLE PRECISION NOT NULL,
    def_yards_n           INTEGER NOT NULL,
    def_explosive_n       INTEGER NOT NULL,
    def_success_yards_n   INTEGER NOT NULL,
    def_success_yards_sum DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (season, game_id, team)
);

CREATE TABLE IF NOT EXISTS season_release_team_game_yardage (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    season                INTEGER NOT NULL,
    game_id               BIGINT NOT NULL,
    team                  TEXT NOT NULL,
    off_yards_n           INTEGER NOT NULL,
    off_explosive_n       INTEGER NOT NULL,
    off_success_yards_n   INTEGER NOT NULL,
    off_success_yards_sum DOUBLE PRECISION NOT NULL,
    def_yards_n           INTEGER NOT NULL,
    def_explosive_n       INTEGER NOT NULL,
    def_success_yards_n   INTEGER NOT NULL,
    def_success_yards_sum DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (release_id, season, game_id, team)
);

DROP TRIGGER IF EXISTS immutable_projection ON season_release_team_game_yardage;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_team_game_yardage
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();

-- Explicit revokes first, as in 0025 and 0026: default privileges would otherwise
-- leave cks_pipeline SELECT/INSERT/UPDATE and cks_web SELECT on every new table.
-- The live copy is never read or written by the application, so only the owner
-- keeps access to it.
REVOKE ALL ON team_game_yardage FROM PUBLIC, cks_pipeline, cks_web;
REVOKE ALL ON season_release_team_game_yardage FROM PUBLIC, cks_pipeline, cks_web;
GRANT SELECT ON season_release_team_game_yardage TO cks_web;
GRANT SELECT, INSERT ON season_release_team_game_yardage TO cks_pipeline;
