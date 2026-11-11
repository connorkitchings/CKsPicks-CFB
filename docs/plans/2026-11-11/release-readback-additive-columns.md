# Release readback tolerates additive nullable columns

- **Status:** Implemented
- **Created:** 2026-11-11
- **Planner:** Sol
- **Approval source:** Owner approval of the 2026-11-11 stock-take plan (section 3, "Rollback is currently broken for every pre-0029 release") and the owner's 2026-11-11 choice to batch related work on one branch.
- **Implementation log:** `session_logs/2026-11-11/02-readback-additive-columns.md`
- **Commit policy:** Commit with implementation, on the current batch branch. Workers never push or open pull requests.

## Goal and acceptance

Rolling back (or re-activating) a release staged before migration 0029 must work again. Migration 0029 added the nullable columns `off_success_ot_n` and `off_success_ot_sum` to the existing table `season_release_team_game_stats`. `_readback` in `src/cks_picks_cfb/season/release.py` builds its column list from live `information_schema.columns` and hashes every row with `projection_check`, which keeps `None` as `"key":null`. A release staged before 0029 recorded a hash over rows without those keys, so its readback now differs and `_activate` (used by both `activate_release` and `rollback_release`) raises `SeasonReleaseError("entire-view projection readback differs")`. The failure is closed inside the transaction, so nothing is corrupted, but Production has no working rollback: Week 10 `production-season-2026-3921681d03fcfcb0ebfe96b6` today, and Week 11 `production-season-2026-5d50a63ef62a6751f30d7599` after the next weekly release.

Acceptance:

1. `rollback_release` to a release staged before 0029 succeeds after 0029 is applied, and the readback hash it records equals the hash that release was staged with.
2. A release staged after 0029 (real values in the new columns, or all-NULL values) still verifies against its own recorded hash, unchanged.
3. The gate stays strict: a pre-0029 release whose registered columns hold any non-NULL value fails readback with the existing error.
4. The Sunday 2026-11-15 forward activation is unaffected (its candidate is staged with the new columns).
5. A written rule for future additive `ADD COLUMN` migrations exists in `contracts/README.md`, and the 0029 comment no longer claims that retained payload hashes are unaffected without qualification.

## Baseline and constraints

- Baseline: `dev` at `dae2bd97` (after PRs #32 and #33). Verified by code reading: `_readback` (`release.py`), `_columns`, `projection_check`, `_normal`; `_activate`; the three `_readback` callers in stage (idempotent re-stage and post-insert) and in the Preview path. Migration 0027 created new tables and never met this; 0029 is the first `ADD COLUMN` on an existing `season_release_*` table.
- In scope: `src/cks_picks_cfb/season/release.py`, `tests/test_season_release_postgres.py`, a comment-only edit of `contracts/migrations/0029_team_game_success_ot.sql` (and the identical lines in `contracts/schema.sql`, see Amendments), a note in `contracts/README.md`.
- Out of scope: any SQL change (migrations are append-only), the stored rows of retained releases, the hashing function `projection_check` itself, the staging hash, the activation function in SQL, Production or Preview database writes, and running the rollback drill (a separate owner-run step after this merges).
- Constraint: the fix must not weaken the check for any table or column outside the registry. The gate must remain a full-row hash comparison.
- Compatibility: the Week 11 release is staged before 0029 and must work as a rollback target without restaging.

## Ordered changes

1. **Registry and readback (`release.py`).** Add a module constant, for example `POST_STAGING_NULLABLE_COLUMNS = {"team_game_stats": ("off_success_ot_n", "off_success_ot_sum")}`, with a comment naming migration 0029 and the rule that every future `ADD COLUMN` on a `season_release_*` table must be registered here in the same change.
   In `_readback`, per base table: read rows exactly as now and compute the full-column check. If it equals the recorded check, use it. Otherwise, only for a base that has registered columns present in the live schema: if every row has `NULL` in all registered columns, recompute the check with those keys removed from each row and use it if it equals the recorded check; if any registered value is non-NULL, do not fall back. Keep `actual != checks` and its error unchanged. The full-hash attempt always comes first, so an all-NULL post-0029 release still matches on the first attempt. Keep the change small; no new public API.
   Acceptance: items 1 to 3 above. Validation: tests in task 3.
2. **Documentation (comment only).** Correct the 0029 comment: the stored rows of retained releases do not change, but their entire-view readback depends on the registry in `release.py`; do not alter any SQL statement. Add a short rule to `contracts/README.md` under the serving contract: an `ADD COLUMN` to an existing `season_release_*` table must be nullable and registered in `POST_STAGING_NULLABLE_COLUMNS`, and its test must cover rollback to a release staged before the column existed. Check that the migration checksum or migration-history test, if one exists, still passes after the comment edit; if the comment edit changes a recorded checksum, stop and return to Sol rather than editing the test.
3. **Tests (`tests/test_season_release_postgres.py`, disposable Postgres).** The test templates apply 0029 inside `tpl_0026`, so every template carries the columns. Do not restructure the template chain. In each test, start from the `db` fixture, drop the two columns from `season_release_team_game_stats` and `team_game_stats` to recreate the pre-0029 schema, stage and activate a first release with the builder payload that has those keys removed from its `team_game_stats` rows, then re-apply `MIGRATION_0029` (already a module constant), then stage and activate a second release with the normal payload, then proceed:
   - Positive: `rollback(...)` back to the first release succeeds; the receipt and readback hash equal the first release's recorded hash; activating the second release again afterwards (roll forward) also succeeds.
   - Negative: after the same setup, set a non-NULL value in a registered column for one row of the first release (using the owner role, bypassing the immutable-projection trigger as the other negative tests do, or the established mechanism in this file), and assert the rollback raises `SeasonReleaseError` with the unchanged readback message and writes nothing (use the file's existing no-writes assertions).
   - Regression: a post-0029 release whose registered columns are all NULL still verifies, and one with real values still verifies.
   Acceptance: both new tests fail on `dev` code before task 1 and pass after. Confirm the positive test fails first by running it before applying task 1.
4. **Validation and log.** Run the checks below and write the implementation log.

## Validation

- `PYTHONPATH=src:. uv run pytest tests/test_season_release_postgres.py tests/test_season_release.py -q` (the Postgres tests need the local Postgres binaries; if they skip, report that rather than treating it as a pass).
- `uv run ruff format --check .`, `uv run ruff check .`, `make contracts-check`.
- Full Python suite: `PYTHONPATH=src:. uv run pytest tests -q -n 4`.
- `git diff --check` and `uv run mkdocs build --strict -q`.
- Stop gates: any change needed outside the in-scope files; any existing release test that must be edited to pass; a migration checksum failure.
- No Production or Preview database access is part of this work. Release to `main` is not required for an owner-run rollback (it runs locally from a clean tree), but the change goes out with the next `dev` to `main` release.

## Handoff/amendments

- Approval and resume gate: approved as stated in the header; implementation may start immediately. Production rollback and the rollback drill still need separate explicit owner approval and a mid-week window; they are not authorized by this contract.
- Next action: one worker-large subagent owns the four in-scope files and implements tasks 1 to 4 in the current worktree without committing or pushing; the orchestrator verifies, commits and later pushes once with the batch.
- Amendments: a mechanical amendment may proceed if architecture, interfaces, scope and acceptance are unchanged; a material conflict returns to Sol. Record each amendment here with reason, previous approach, revised approach and impact.

### Amendment 1 (2026-11-11, mechanical)

- **Reason:** `test_snapshot_tail_is_migrations_0025_to_0029_verbatim_matches` requires the tail of `contracts/schema.sql` to equal the migration files verbatim, so the 0029 comment change alone failed the stop gate.
- **Previous approach:** comment-only edit of the 0029 migration.
- **Revised approach:** the same comment-only edit in both `contracts/migrations/0029_team_game_success_ot.sql` and `contracts/schema.sql`; no SQL statement changed.
- **Impact:** none on architecture, interfaces or acceptance.
