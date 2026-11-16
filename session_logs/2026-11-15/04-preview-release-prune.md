# Preview release prune (2026-11-15)

## Outcome
13 superseded Preview releases and 14 history rows were deleted. All 25 immutability triggers are enabled again and a trial `DELETE` is still rejected. The close re-run (run `43787947160`) still failed at `step release preview` with `DiskFull ... project size limit (1024 MB)`. Production was not touched. `pg_database_size` stayed about 1000 MB, so the cap counts physical file size: pages freed by `VACUUM` do not help.

## Steps
1. Preflight: no workflow runs in progress; counts recorded; export written to `session_logs/2026-11-15/04-preview-release-prune-export.json` (13 releases, 14 history rows, per-table counts).
2. Single-transaction delete failed three times and rolled back. `ENABLE TRIGGER` rewrites `pg_trigger` rows and needs file space that the full branch lacks. The first attempt also needed `SET CONSTRAINTS ALL IMMEDIATE` (pending deferred FK events block `ALTER TABLE`).
3. With owner approval, split into two commits: (1) disable triggers and delete, commit; (2) `VACUUM pg_catalog.pg_trigger`, then enable triggers with a `DO` block asserting 4 releases, active `d842113f`, 3 history rows, 25 enabled triggers, 0 leftover rows. Triggers were disabled for about a minute on Preview with no workflows running.
4. `VACUUM (ANALYZE)` on the 25 tables: `n_dead_tup` is 0.
5. Close re-run failed with the same `DiskFull`.

## Next
Upgrade the Neon plan (Launch), then re-run `gh workflow run weekly-season-update.yml --ref dev -f mode=close-week`. Do not use `VACUUM FULL`. Each release adds about 75 MB, so a supported prune tool or the larger plan is needed long term. Production branch size is unchecked.

## Update: VACUUM FULL cascade cleared the cap
The earlier "Next" section is superseded. A smallest-first `VACUUM (FULL, ANALYZE)` cascade, run as `cks_preview_migrator` with `lock_timeout = '10s'`, shrank the Preview branch from 1018.1 MB to 353.6 MB. Each table's estimated compacted size plus 5 MB was checked against headroom before its rewrite, and every check passed. No rows changed, so no triggers fired or were disabled.

Verification after the cascade: row counts identical across all 26 `season_release*` tables (388,904 rows), 25 of 25 triggers `tgenabled = 'O'`, 4 releases with `d842113f` still present, and a trial `DELETE` on `season_releases` rolled back with "season releases are retained".

Production (`ep-noisy-king`, 518 MB, 8 releases) was left alone: its cap is separate and its releases back rollback.

### Per-table sizes (MB, tables plus indexes)
| Table | Before | After |
|---|---|---|
| `season_release_history` | 0.1 | 0.0 |
| `season_release_system_stats` | 0.1 | 0.0 |
| `season_release_matchup_data_publications` | 0.1 | 0.0 |
| `season_release_policies` | 0.0 | 0.0 |
| `season_release_site_week_selections` | 0.1 | 0.0 |
| `season_releases` | 0.2 | 0.1 |
| `season_release_team_season_roster` | 0.5 | 0.1 |
| `season_release_game_results` | 2.0 | 0.5 |
| `season_release_game_venues` | 3.8 | 0.7 |
| `season_release_games` | 5.0 | 1.1 |
| `season_release_team_game_yardage` | 3.4 | 1.1 |
| `season_release_predictions` | 5.0 | 1.3 |
| `season_release_team_game_stats` | 4.3 | 1.3 |
| `season_release_prediction_grades` | 7.3 | 1.9 |
| `season_release_prediction_market_selections` | 8.3 | 2.1 |
| `season_release_market_snapshots` | 9.8 | 2.6 |
| `season_release_team_adjusted_epa` | 9.5 | 2.9 |
| `season_release_team_resume` | 8.8 | 3.0 |
| `season_release_market_quotes` | 19.8 | 4.8 |
| `season_release_v5_rating_snapshots` | 25.3 | 5.9 |
| `season_release_market_snapshot_quotes` | 32.3 | 7.6 |
| `season_release_team_possession_adjusted` | 35.6 | 9.3 |
| `season_release_team_rating_components` | 120.2 | 33.0 |
| `season_release_team_possession_stats` | 148.2 | 39.7 |
| `season_release_team_game_measurements` | 161.6 | 42.1 |
| `season_release_team_season_stats` | 292.3 | 78.0 |

### Close outcome
`gh workflow run weekly-season-update.yml --ref dev -f mode=close-week` (run `43790541091`, started with owner approval) succeeded: `release preview` ok (73s), `release production` ok (85s). Preview afterwards: 433.8 MB, 5 releases. Each release adds about 75 MB, so Preview fills again in roughly 6 releases and Production in about the same. Follow-up, not built: a supported prune plus compaction tool, or a Neon plan upgrade.

### Week 12 live
Readback after the close (2026-11-15): `/api/health` reports `production-season-2026-0a435fd6f2499457f26d7deb`, Week 12, 66 of 66 games predicted and lined, data as of 2026-11-16T00:07:25Z; `/`, `/ratings`, `/stats` and `/model` return 200. Preview serves the same candidate with 5 releases. The scheduled run `43791819247` skipped ("week 12 has not started (already rolled over)"). First kickoff 2026-11-17T23:00Z.

Record from the new release: Week 11 spread 35-32-0 (52.2%), total 24-43-0 (35.8%). Cumulative 2026 V5 through Week 11: spread 308-312-9 (49.7%), total 293-333-2 (46.8%), including three `cfbd_retrospective` Week 6 grades that Production now carries.

Storage: the Neon console shows the project-storage "Limit reached" banner (Production 629 MB plus Preview 455 MB against 1 GB per project on the Free plan). Deferred by owner decision; each close adds about 75 MB per branch. Whether the banner blocks writes is unconfirmed.
