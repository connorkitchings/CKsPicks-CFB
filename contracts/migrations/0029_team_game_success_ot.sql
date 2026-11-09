-- Net success rate includes overtime: offensive success counts over scrimmage plays
-- with the regulation-only rule relaxed (garbage time is still dropped). Additive and nullable:
-- retained releases carry no values (NULL), existing columns and payload hashes of
-- retained releases do not change, and the immutable-projection trigger is not
-- fired by ADD COLUMN. Only the Net success rate chart reads these columns.
ALTER TABLE team_game_stats
    ADD COLUMN IF NOT EXISTS off_success_ot_n   INTEGER,
    ADD COLUMN IF NOT EXISTS off_success_ot_sum DOUBLE PRECISION;
ALTER TABLE season_release_team_game_stats
    ADD COLUMN IF NOT EXISTS off_success_ot_n   INTEGER,
    ADD COLUMN IF NOT EXISTS off_success_ot_sum DOUBLE PRECISION;
