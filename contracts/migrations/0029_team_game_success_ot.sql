-- Net success rate includes overtime: offensive success counts over scrimmage plays
-- with the regulation-only rule relaxed (garbage time is still dropped). Additive and nullable:
-- retained releases carry no values (NULL), the stored rows of retained releases do
-- not change, and the immutable-projection trigger is not fired by ADD COLUMN. Their
-- entire-view readback hash does depend on POST_STAGING_NULLABLE_COLUMNS in
-- src/cks_picks_cfb/season/release.py, which lets a release staged before this
-- migration verify with these all-NULL columns left out. Only the Net success rate
-- chart reads these columns.
ALTER TABLE team_game_stats
    ADD COLUMN IF NOT EXISTS off_success_ot_n   INTEGER,
    ADD COLUMN IF NOT EXISTS off_success_ot_sum DOUBLE PRECISION;
ALTER TABLE season_release_team_game_stats
    ADD COLUMN IF NOT EXISTS off_success_ot_n   INTEGER,
    ADD COLUMN IF NOT EXISTS off_success_ot_sum DOUBLE PRECISION;
