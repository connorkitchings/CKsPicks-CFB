# Session: Release readback tolerates additive nullable columns

## TL;DR

- **Worked On:** Rollback to any release staged before migration 0029 failed readback; wrote the contract and fixed it.
- **Outcome:** `_readback` accepts the hash without registered post-staging nullable columns, only when every registered value is NULL. A new registry `POST_STAGING_NULLABLE_COLUMNS` in `src/cks_picks_cfb/season/release.py` holds `team_game_stats: off_success_ot_n, off_success_ot_sum`. Three new Postgres tests cover rollback and roll-forward, a non-NULL value that must still fail, and post-0029 releases (real and all-NULL values).
- **Plan Contract:** [`docs/plans/2026-11-11/release-readback-additive-columns.md`](../../docs/plans/2026-11-11/release-readback-additive-columns.md)
- **Approval / Status:** Owner-approved stock-take plan; contract Implemented, with one mechanical amendment.
- **Blockers:** None
- **Next:** Owner merges the PR; then run the never-yet-run Production rollback drill in a mid-week window, from a clean tree containing the fix.

**tags:** ["release", "rollback", "migration"]

## Context and Decisions

- The positive test failed on the old code with "entire-view projection readback differs" before the fix (red first).
- Amendment: the 0029 comment correction had to be made in `contracts/schema.sql` too, because a test requires the schema tail to match the migrations verbatim.
- After a rollback a release has status `rolled_back`; roll-forward uses `rollback_release` again, not `activate_release`.
- Work was batched on one branch with the documentation hygiene follow-ups, per the owner's choice.

## Work Completed

- Implemented by a worker subagent in this worktree; diff and tests verified by the orchestrator.

## Files Modified

- `src/cks_picks_cfb/season/release.py`, `tests/test_season_release_postgres.py`
- `contracts/README.md`, `contracts/migrations/0029_team_game_success_ot.sql`, `contracts/schema.sql` (comments and rule only)
- `docs/status.md`, `docs/plans/2026-11-11/release-readback-additive-columns.md`

## Validation

- [x] `tests/test_season_release_postgres.py` and `tests/test_season_release.py`: passed; full Python suite 2388 passed, 24 skipped (before the comment amendment); Postgres file re-run after it: 118 passed, 12 skipped (web-dependency skips)
- [x] `ruff format --check`, `ruff check`, `make contracts-check`, `mkdocs build --strict`, `git diff --check`
- [ ] Web lint and `make web-e2e` not run (no `node_modules`; no web change)
- [ ] No Production or Preview database was touched; the rollback drill is not yet run.
