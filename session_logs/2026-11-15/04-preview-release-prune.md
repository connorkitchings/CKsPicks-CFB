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
