# 2026-10-08 Stage 1 completion (continuation of 2026-10-07/07)

Contract: `docs/plans/2026-10-07/04-stage1-week5-corrected-data-finalization.md` (Amendment 8). Decision brief: `docs/plans/2026-10-08/01-stage1-decision-brief.md`. Everything below is Preview-only; no Production write. (Sections 1-8 were written before the later work; the "Later work" section at the end covers the rest of the day.)

## Sequence and results (verified unless marked)

1. **Stability of Weeks 0-4.** Parents differ only in game 401856660. Derived legacy-lineage `byplay`/`reconciled_team_game` differ widely because current code differs from the code that built them (punt-return flag, `ppa_missing`); that was attributed by the 6A `silver_2026` comparison, which differs only in the LSU game. No control build was needed (user decision).
2. **6A w5 run, first attempt** (`-r1`): stopped at `states_2026` with `2026 game 401862787 differs from the lock`. Cause: the revised CFBD data moved Charlotte at Memphis from 19:30Z to 15:00Z (Bronze history: placeholder, then 19:30Z on Sep 27, then 15:00Z on Oct 7). Only that game; `-r1` left 0 objects in R2.
3. **Fix** (user-approved Option 1): `extend_lock` records an accepted kickoff revision with old/new times and the games version; refuses any other change. New run `6a-rebuild-w5-20261007-r2`: 11 stages built, verify passed, published (236 objects, catalog 49 versions), retry 0 writes. Historical content reproduces (silver 40/40, gold 50/50 apart from the `source_versions` lineage column).
4. **Comparison and LSU attribution** (read-only): ratings, observations and priors for Weeks 0-4 are unchanged; the LSU game changes 69 `ppa` values and a few play fields only.
5. **Task 4 for w5.** `-r1` built but `verify` failed: the published comparison counted the 56 added Week 5 games as unexplained and its baseline-history control failed on 4 `cutoff_utc` rows (the kickoff revision) plus 276 added rows. Fix: scope-aware comparison (`added_scope`, `kickoff_revision`), still refusing any other difference. Run `6a-task4-w5-r2`: verify passed, `all_differences_explained` true, published (39 objects, retry 0). The 95 database-only rows in `team_possession_adjusted` are the same ones, same bucket, as in the original Task 4 run (compared by count and bucket, not key by key).
6. **6B w5** (`6b-replay-w5-20261008-r1`): 12 stages, verify passed, published (112 objects, 5 Gold datasets registered, retry 0). Value-identical to the first 6B run; headline numbers in the brief.
7. **Team stats and matchup.** Corrected as-of 1-5 payload verified (receipt raw sha `ce20b9ff…`, dry run, decision ref `stage1-dry-run-not-a-release-decision`); as-of 6 candidate checked (24 values recomputed independently, 0 differences); matchup candidate/previous payloads built and diffed against Production (Production equals Preview in all four tables).
8. **Task 8.** See Amendment 8. Full Python suite: 2,107 passed, 13 skipped (without CI's `-W error`).

## Corrections and caveats

- My first Task 4 plan was fine but the stage code assumed the earlier population; the failure was found at `verify`, before any publish.
- The 11 differing team-stat cells between the old and new "after" payloads are float noise (about 1e-16), not value changes.
- **Agent-reported, not re-opened:** the map of the successor artifact chain in the brief (a read-only subagent; it said it did not open the source-lock generator or the DDL).
- The matchup candidate script was run from uncommitted code before its evidence was committed; the commit below records both.
- Evidence scripts in `stage1-evidence/` are one-off analysis, not tested tools.
- **Not done:** Task 7, week-parameterizing the successor scripts, the successor lock builder, matchup database gates, an end-to-end test for D7f, generalizing the Week-4 literals in the 6B stages.

## Commits to make (by path; user-run)

Everything under: `src/cks_picks_cfb/quality/`, `scripts/pipeline/build_team_game_dataset.py`, `tests/test_build_team_game_defaults.py`, `tests/test_quality_loaders.py`, `docs/plans/2026-10-08/`, `docs/plans/2026-10-07/04-stage1-week5-corrected-data-finalization.md`, `docs/data/known_issues.md`, `docs/status.md`, `session_logs/2026-10-08/`.

## Later work (same day; Preview only, no Production write)

9. **6B rerun with the successor bundle.** Replaying with the 6A refit bundle (B1) gave prediction changes that were mostly a bundle difference, not a data effect (brief, correction block). B2 came from the successor bridge builder run on the corrected frames (`conf/rebuild/bundle_b2_w5_v1.json`); `6b-replay-w5-20261008-r2` was built, verified and published. **Corrected earlier claims:** 27 flips and 130-136-5 belong to the superseded `-r1`.
10. **Task 7 (successor chain).** Lock builders, week-parameterized builders and verifiers, best-quote v2 serving verifier (the old one encoded the retired September policy), corrected parents for the bridge manifest. Replay set `20261008-c1` used canonical team names; Neon and the site use provider names, so it was superseded by **`20261008-c2`** (six runs, 271 games, nine provider-named teams present, release records dry-run validated, none registered).
11. **Week 6 display-only run.** First publication (`-d1`) was blocked by the venue gate, the schedule-coverage gate and canonical names; fixes were `locked_schedule(..., canonical=False)`, `seed_week_schedule.py`, and venues after the preview-state publish. `-d2` is published and selected in Preview; the site notice text was approved and verified locally. Production stays on the hold screen (user chose Option A).
12. **Cutover tooling.** Packet builder, staging tool (both with tests), Amendment 10 (Week 6 waiver in `validate_v2_packet`), packet-builder CLI, c2 evidence file.
13. **Stage 1 close-out.** 6B week generalization (policies `weeks`, `expected_counts`, `served_weeks`, `unserved_week_as_of`; reconciliation stages refuse other populations), D7f helper and tests, Amendment 11, status and brief updates.

## Corrections and caveats (later work)

- **Not exercised:** no Week 6 6B run; the 6B flow tests were not extended to a seventh week (new policy logic is unit tested). The positive path of a Week 7 packet with a real Week 5 prospective record is untested locally.
- **Agent-reported, not re-opened:** the c2 evidence file was built from retained scratchpad outputs, not re-read from R2.
- Several scripted edits needed a second pass (zsh glob, wrong interpreter, an import block rewritten before names were fixed); each was caught by ruff or the tests before it was reported.

## Commits (user-run), in order

`6cb7e871` cutover tools; `f4b2ce2b` Amendment 10, packet CLI, c2 evidence; the close-out commit lists: `src/cks_picks_cfb/rebuild/recon_*.py`, `scripts/pipeline/publish_to_db.py`, `tests/test_recon_week_policies.py`, `tests/test_publish_to_db.py`, `docs/plans/2026-10-08/`, `docs/plans/2026-10-07/04-stage1-week5-corrected-data-finalization.md`, `docs/status.md`, `session_logs/2026-10-08/`.
