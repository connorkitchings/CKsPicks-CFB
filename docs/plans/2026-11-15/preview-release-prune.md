# Prune superseded Preview releases

**Goal:** Free Neon space on the Preview branch (1003 MB of the 1024 MB Free-plan cap) so the Week 11 to 12 close can stage a release.

**Owner decisions (2026-11-15):** keep 4 Preview releases (`d842113f` active, `aca7b33d`, `5d50a63e`, `3921681d`); delete the 13 Weeks 7 to 9 releases and the 14 history rows that reference them; export the deleted release and history rows to the repo first. Production is untouched.

**Method:** As `cks_preview_migrator`, disable the 25 immutability triggers, delete the 13 releases' rows from the 23 projection tables, the history table and `season_releases`, run `SET CONSTRAINTS ALL IMMEDIATE`, then re-enable the triggers; `VACUUM (ANALYZE)` the 25 tables; verify triggers, row counts and that a trial `DELETE` is still rejected. Re-run the close with the owner's go-ahead.

**Stop condition:** if the re-run still hits `DiskFull`, stop and move to the Launch plan. Do not use `VACUUM FULL`.
