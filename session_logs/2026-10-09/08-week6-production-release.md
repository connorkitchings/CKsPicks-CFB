# Session: Week 6 display-only release to Production (Terra)

## TL;DR
- **Worked On:** Contract `02` Tasks 1-5: Preview re-apply after the rollback rehearsal, then the Production release of the display-only Week 6 run `2026w6-v5repair-20261008-d2`.
- **Outcome:** The run is published and selected in Production (55 predictions, display-only, `pending`); matchup data verified; Weeks 0-5 unchanged. Not yet verified on the live site (needs the `dev` to `main` merge).
- **Plan Contract:** `docs/plans/2026-10-09/02-week6-display-production-release.md` (still In Progress; Amendments 5-7 appended).
- **Approval / Status:** User approved the Production sequence step by step and instructed the applies in-session; owner-role SQL and the Silver promotion and staging applies were user-run.
- **Blockers:** None. Remaining: merge to `main`, Vercel notice flag, live verification, post-finals backfill.
- **Next:** User merges `dev` into `main` and checks the live site; after finals (about Oct 11-12) run the grades-only backfill.

## Context and Decisions
- User: show the Week 6 predictions "in the exact same manner" as Weeks 0-5; already-played games and the timing contract do not matter because no Week 6 results or plays are ingested. Display-only mode kept (no freeze/close, which would mark kicked-off games missed).
- Option B (resume the release now) chosen over deferring to the Week 7 cutover. Phase 1 doc corrections to the byplay_v2 close-out were committed first.
- No new CFBD data was needed: the picks use ratings through Week 5, as-of-6 stats from completed games, and the Oct 8 16:19Z lines.

## Work Completed
- Preview: authorize, seed, venues, ratings, stats, publish (first under the wrong config, rolled back, redone with the V5 config), select, matchup, verify; local routes checked by the user.
- Code: `--only-missing` and `--supplement` for the venue publisher; `--predictions-only` for the staging tool; tests for both.
- Production: Silver promotion (user-run), staging (user-run), owner inserts (user-run, second attempt), then seed, venues, ratings, stats, publish, select and matchup (applied in-session on instruction).

## Files Modified
- `scripts/pipeline/publish_game_venues.py`, `src/cks_picks_cfb/data/game_venues.py`, `tests/test_game_venues.py`, `conf/venue_supplement_2026_w6_v1.json` (committed earlier).
- `scripts/pipeline/stage_v5_artifacts.py`, `src/cks_picks_cfb/ops/v5_artifact_staging.py`, `tests/test_v5_artifact_staging.py` (committed `f51ab320`).
- Docs: contract `02` (Amendments 5-7, checklist), `docs/status.md`, this log.

## Validation
- [x] Preview and Production read-only state checks after the applies; matchup `verify_matchup_data` VERIFIED in both.
- [x] Targeted tests (`test_game_venues`, `test_v5_artifact_staging`); ruff clean on touched files.
- [x] `make contracts-check`, strict mkdocs and `git diff --check` for the doc update.
- [ ] Live-site verification (after merge).
- [ ] Post-finals grades-only backfill.

## Handoff Notes
- **Resume at:** merge `dev` to `main`, set `CFB_DISPLAY_ONLY_NOTICE=0` in Vercel, verify the live site (Picks 55, Ratings 138, Week 6 matchups, Weeks 0-5 unchanged except the accepted lineage message on their matchup pages).
- **Watch out for:** a rollback needs the owner login (the pipeline role has no DELETE on `prediction_market_selections`); never freeze or close Week 6; the notice date shows Oct 9 (run row `created_at`).
- **Lessons:** V5 publish needs `--config conf/weekly_bets/v5_intended_update_2026.yaml` and the restricted pipeline role; check owner SQL landed on the right branch with a read-only query before proceeding.

**tags:** ["implementation", "week6", "production", "release"]
