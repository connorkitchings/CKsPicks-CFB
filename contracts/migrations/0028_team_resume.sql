-- Team résumé projection (SOS, SOR, WAA) per rating period. Additive: no existing
-- table, grant or release changes, so retained releases read back unchanged and
-- simply carry no rows here. Keyed by the period id the served v5 rating snapshots
-- use: 'preseason' or '<rating source sha256>@<cutoff ISO-8601, milliseconds, Z>'.
CREATE TABLE IF NOT EXISTS season_release_team_resume (
    release_id TEXT NOT NULL REFERENCES season_releases(release_id) ON DELETE RESTRICT,

    period_id              TEXT NOT NULL,
    cutoff_utc             TIMESTAMPTZ NOT NULL,
    post_week              INTEGER,
    team                   TEXT NOT NULL,
    overall_rank           INTEGER NOT NULL CHECK (overall_rank >= 1),
    completed_games        INTEGER NOT NULL CHECK (completed_games >= 0),
    scheduled_games        INTEGER NOT NULL CHECK (scheduled_games >= completed_games),
    wins                   INTEGER NOT NULL CHECK (wins >= 0),
    losses                 INTEGER NOT NULL CHECK (losses >= 0),
    elite_reference_size   INTEGER NOT NULL CHECK (elite_reference_size >= 1),
    elite_reference_kind   TEXT NOT NULL CHECK (elite_reference_kind IN ('top25_excluding_self', 'top25')),
    average_reference_size INTEGER NOT NULL CHECK (average_reference_size >= 1),
    sos_played_elite       DOUBLE PRECISION CHECK (sos_played_elite BETWEEN 0 AND 100),
    sos_remaining_elite    DOUBLE PRECISION CHECK (sos_remaining_elite BETWEEN 0 AND 100),
    sos_full_elite         DOUBLE PRECISION CHECK (sos_full_elite BETWEEN 0 AND 100),
    sos_played_average     DOUBLE PRECISION CHECK (sos_played_average BETWEEN 0 AND 100),
    sos_remaining_average  DOUBLE PRECISION CHECK (sos_remaining_average BETWEEN 0 AND 100),
    sos_full_average       DOUBLE PRECISION CHECK (sos_full_average BETWEEN 0 AND 100),
    sor_p                  DOUBLE PRECISION CHECK (sor_p BETWEEN 0 AND 1),
    sor                    DOUBLE PRECISION CHECK (sor BETWEEN 0 AND 100),
    sor_rank               INTEGER CHECK (sor_rank >= 1),
    waa                    DOUBLE PRECISION,
    PRIMARY KEY (release_id, period_id, team),
    CHECK ((period_id = 'preseason') = (post_week IS NULL)),
    CHECK (wins + losses = completed_games),
    CHECK ((sor_p IS NULL) = (sor IS NULL)),
    CHECK (sor_rank IS NULL OR sor IS NOT NULL),
    CHECK (sor IS NULL OR completed_games >= 3),
    CHECK (waa IS NULL OR sor IS NOT NULL)
);

DROP TRIGGER IF EXISTS immutable_projection ON season_release_team_resume;
CREATE TRIGGER immutable_projection BEFORE INSERT OR UPDATE OR DELETE ON season_release_team_resume
    FOR EACH ROW EXECUTE FUNCTION reject_season_projection_mutation();

-- Explicit revokes first, as in 0025 through 0027: default privileges would otherwise
-- leave cks_pipeline SELECT/INSERT/UPDATE and cks_web SELECT on every new table.
REVOKE ALL ON season_release_team_resume FROM PUBLIC, cks_pipeline, cks_web;
GRANT SELECT ON season_release_team_resume TO cks_web;
GRANT SELECT, INSERT ON season_release_team_resume TO cks_pipeline;
