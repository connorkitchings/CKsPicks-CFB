# Session: Data-quality Task 1 (check library, receipts, CLI)

## TL;DR
- **Worked On:** Task 1 of `docs/plans/2026-10-04/01-pipeline-data-quality-gates.md` and the Window 1 venue fix that blocked the receipt.
- **Outcome:** `src/cks_picks_cfb/quality/` (check registry, severity policy, deterministic immutable receipts, CLI), Make targets, 9 tests. Venue publisher can pin a Silver venues version. No data checks are registered yet.
- **Approval / Status:** User authorized Task 1 on 2026-10-04 (Window 1 code in `850ca38`). Task 4 stays held until the Preview venue dry run passes on the pin and the Window 1 receipt is signed off.

## Decisions (recorded as Amendment 1 in the contract)
- CLI is standalone (`python -m cks_picks_cfb.quality`), not an `ops` subcommand.
- `utils/validation.py` left in place, not ported; removal is a separate prune after Tasks 2–3.

## Venue finding (verified, read-only)
Silver `venues` is one version per capture year; the publisher took the last created (`ac36e3e4`, year 2025). `b569d242e8c4c53b416bfe14` (year 2026) covers all 8 missing venue IDs. `--venues-version` pins it; pinned dry run: 271/271 cities, 269 states. This is also a Task 2 candidate check: a dataset with many same-`as_of` versions needs an explicit pin or a coverage assertion.

## Validation
- Full suite: 1654 passed, 9 skipped. `ruff check .` clean. `mkdocs build` clean. `make quality-check` passes (0 checks).
- Not run: Preview venue write; CI wiring (Task 6).

## Files
- New: `src/cks_picks_cfb/quality/{__init__,checks,receipt,__main__}.py`, `tests/test_quality_library.py`.
- Edited: `Makefile`, `.gitignore` (`artifacts/quality/`), `scripts/pipeline/publish_game_venues.py`, `tests/test_game_venues.py`, the contract, the Window 1 log.

## Pre-start verification for Tasks 2 and 3 (user stipulation 3)
- **Verified (2026-10-04):** every sampled survey reference lands on the construct the survey named: `schema_contracts.py` 205/221/2018/2166 (`DatasetSchemaError`, `DatasetSchema`, `schema_for`, `validate_frame`); `market_integrity.py` 49/56; `the_odds_api.py` 79 (unmatched events absent), 309/320 (price taken as `price`, no actual-versus-default flag); `fetch_odds_api_market_quotes.py` 128/141/171 (`unmatched` list, skipped warning, `unmatched_events` count); `reconciliation.py` 40/56/92/157/212; `team_stats.py` 109/240/284/314; `game_venues.py` 49/93/107; `enrichment.py` 126; `possession_measurements.py` 199/314/434. Earlier verified: `lake.py:219-222`, `utils/validation.py` unreferenced, `require_reconciled` callers, `publish_to_db.py:868`.
- **Still agent-reported, not re-read:** the Gold/audit/operational references (`evidence_audit.py`, `audit/checks.py`, `check_prepared_week.py`, `audit_market_quote_coverage.py`, `ops/data_audit.py`). Re-read these at the start of Task 3.
- **Ingestion shape for Task 2:** CFBD entities are ingested by `scripts/data/ingest_season.py` through per-entity ingesters (`data/{teams,venues,games,plays,game_stats,betting_lines,...}.py`); captures are recorded in `catalog.source_captures` and `catalog.source_request_attempts` (`data/catalog.py`), with an immutable-capture conflict check at `catalog.py:380-398`. Bronze checks can therefore run over catalog capture rows plus the Silver dataset they feed, with no new capture format.
- **Task 2 candidate checks (to register at `warn`, promote after receipt review):** capture completeness (every requested entity/season/week has a completed attempt); games-per-week against the pinned schedule; plays-per-completed-game floor and drives present; key uniqueness (`game_id`, `play_id`); required-column presence and null rate for score, period, clock, yards, PPA; PPA missingness recorded before any fill; Odds API unmatched-event count and per-quote price presence; **same-`as_of` multi-version datasets** (e.g. `venues`: 14 validated versions in Preview, each a different year) must be pinned or coverage-checked, which would have caught the 10 missing cities.

## Task 2 progress (Bronze ingestion checks) — started 2026-10-04 under user authorization
- **Library change:** a check can return `skipped(reason)` when its input is absent. Skipped is neither pass nor fail, never blocks, and is counted separately in the receipt summary, so a run with no data cannot look clean. CLI output now prints `skipped`.
- **New:** `src/cks_picks_cfb/quality/ingest.py`, nine checks, all `warn`: `ingest.versions_pinned`, `capture_completeness`, `games_vs_schedule`, `completed_games_have_scores`, `plays_and_drives_per_completed_game`, `ppa_coverage`, `odds_unmatched_events`, `quote_price_presence`, `schema_contract`. Contexts are injected DataFrames/sets, so tests need no cloud or database access (`tests/test_quality_ingest.py`).
- **Not duplicated:** `validate_frame` already raises on missing columns, nulls in required fields and duplicate keys at write time; `ingest.schema_contract` only records that result per dataset in the receipt.
- **Real-catalog run of `versions_pinned` (verified, read-only SELECT on both catalogs, no pins supplied):** first version flagged 11 of 26 Preview Silver datasets, too noisy because season-partitioned datasets are selected by season. Refined to flag only versions at the newest `as_of` that a season filter cannot separate (empty or overlapping `seasons`). Result: Preview `game_outcomes` 3, `legacy_market_references` 7, `offseason_context_family` 3, `schedule_revisions` 7, `team_aliases` 6, `venues` 10; production `game_outcomes` 2, `legacy_market_references` 7, `market_quotes` 2, `market_snapshots` 2, `reconciled_team_game` 6, `schedule_revisions` 7, `team_aliases` 6, `venues` 5 (numbers are version counts). **Only `venues` is proven harmful** (it caused the 10 missing cities). The others are candidates to review: they may be harmless rebuilds of identical content, which this check does not compare. They stay `warn`.
- **Not done in Task 2:** a loader that builds the run context from the catalog and Silver for the CLI (today `--stage ingest` yields all-skipped), real-data evidence for the play, drive, score and PPA checks, and wiring each ingester to call its checks before writing. Exit condition for promoting any check to `block` is a reviewed real receipt.

## Task 2 loader and first real Preview receipt (2026-10-04, read-only)
- **Loader:** `src/cks_picks_cfb/quality/loaders.py` builds the ingest context from the catalog (read-only connection), Silver (`games`, `plays`, `drives`) and Neon (`games` as the published schedule, `market_quotes` for prices). The CLI uses it when `--stage ingest --year Y --environment E` is given; `--pin dataset=version_id` is repeatable and is recorded in the receipt identity. Datasets absent from the catalog are left out, so their checks report `skipped`. Tests use fakes (`tests/test_quality_loaders.py`).
- **Two false signals found and fixed on the first real run (verified):** (1) Silver `games` has 761 FBS-involved games and Neon publishes 271, so 490 "extra" games failed the check; extras are now reported, not failed, and the meaningful result is missing = 0. (2) Silver `market_quotes` (CFBD) has no price columns; prices live on the Neon table, so the price check now reads Neon and skips when a source has no price columns.
- **Receipt** `ingest`, Preview, 2026, `--pin venues=b569d242e8c4c53b416bfe14` (local, git-ignored): 9 checks, 2 failed (both `warn`), 3 skipped, not blocked. Inputs: games `31a337df…`, plays `eda5263c…`, drives `862815e2…`.

| Check | Result | Observed |
|---|---|---|
| completed_games_have_scores | pass | 215 completed, 0 null scores |
| games_vs_schedule | pass | 0 missing, 0 duplicates, 490 extra (reported) |
| plays_and_drives_per_completed_game | pass | 215 completed; 0 without plays, 0 below the 60-play floor, 0 without drives |
| ppa_coverage | pass (recorded) | 9,594 of 38,401 plays have no PPA. This counts every play type, so kickoffs and penalties are included; it is not the eligible-play figure (155) from the investigation |
| quote_price_presence | **FAIL (warn)** | 753 quotes, 0 with any of the four price columns. Matches the 753-row count and the all-null prices already in known issues #11 |
| versions_pinned | **FAIL (warn)** | unpinned multi-version datasets at the newest as_of: `game_outcomes` (3), `legacy_market_references` (7), `offseason_context_family` (3), `schedule_revisions` (7), `team_aliases` (6). `venues` cleared by the pin. Candidates to review, not proven harmful |
| capture_completeness, odds_unmatched_events, schema_contract | skipped | inputs not yet wired |

- **Promotion rule:** no check is promoted to `block` yet. Candidates after review: `completed_games_have_scores`, `games_vs_schedule` (missing/duplicates), `plays_and_drives_per_completed_game`.
- **Still open in Task 2:** inputs for `capture_completeness` (from `catalog.source_request_attempts`), `odds_unmatched_events` (from the capture JSON) and `schema_contract`; calling each ingester's checks before it writes; a review of the five `versions_pinned` candidates.

## Sequencing update (2026-10-04)
Window 1 was closed for implementation by the user; Task 4 (publish-boundary assertions) is unblocked. Task 3 is next by the user's instruction.

## Task 3 progress (Silver invariants and gate 6) — started 2026-10-04 on the user's authorization
- **Gold/audit references re-read (verified):** `evidence_audit.py` 203/241/449/626/794/901/948, `audit/checks.py` 57/459, `check_prepared_week.py` 120/207, `audit_market_quote_coverage.py` 49, `ops/data_audit.py` 31/181/301 all land on the constructs the survey named. No claim from the survey was wrong in the references checked.
- **Gate 1 premise corrected (verified):** the standard Silver build `scripts/pipeline/build_team_game_dataset.py` already calls `reconcile_completed_games` and `require_reconciled`, and persists every comparison as the `source_reconciliation` Silver dataset. It was not research-only. What was missing was surfacing it in a receipt, which `silver.reconciliation_recorded` now does.
- **New:** `src/cks_picks_cfb/quality/silver.py`, seven checks, all `warn`: `reconciliation_recorded`, `score_stream_monotone`, `drive_numbering`, `plays_and_drives_same_games`, `points_identity`, `ppa_missing_flag`, `completed_game_refresh_pinned` (gate 6). `loaders.build_silver_context`/`load_silver_context` build the context read-only (byplay, drives, games, source_reconciliation, previous games version, `catalog.source_captures`); the CLI loads it for `--stage silver --year Y --environment E`. Tests: `tests/test_quality_silver.py` plus a loader test.
- **Three of my first-run results were wrong and were fixed before reporting (verified against real data):** `play_number` restarts in each drive, so plays must be ordered by drive then play (first run showed 97.9% regressions); drive numbers are one sequence per game that can appear under both teams when possession changes inside a drive, so the right invariant is a contiguous union per game and uniqueness per offense (first run showed 2,261 duplicates, then 215 gap games).
- **First real Preview receipt** (silver, 2026, read-only; inputs byplay `443019a9`, drives `862815e2`, games `31a337df`, previous games `e3ead581`, reconciliation `fdb566b1`): 7 checks, 3 failed (all `warn`), 0 skipped, not blocked.

| Check | Result | Observed |
|---|---|---|
| reconciliation_recorded | pass | 215 games, all `exact_match`, 0 blocking |
| drive_numbering | pass | 215 games, 0 duplicate keys, 0 gap games |
| plays_and_drives_same_games | pass | 0 on either side |
| completed_game_refresh_pinned (gate 6) | pass | 58 changed completed games between the 2026-09-20 and 2026-09-27 versions: 0 corrections, 58 new completions; all cite catalogued captures with sha, object sha, uri and time |
| score_stream_monotone | **FAIL** | 133 of 430 team-games (30.9%) in 105 of 215 games have a decreasing running score. Matches the "about a third" in known issue 1; I did not use a different method, so this is a re-derivation under my ordering, not independent confirmation |
| ppa_missing_flag | **FAIL** | the Silver byplay version has no `ppa_missing` column (built before Window 1); expected until the Window 2 Silver rebuild |
| points_identity | **FAIL** | 4 team-games where drive points exceed the final score: UTEP (401856664) 1 vs 0, Fresno State (401858436) 2 vs 0, Northern Illinois (401858426) 1 vs 0, Rice (401859184) 1 vs 0. New, not yet investigated; candidates for the 5A sizing |

- **Gate 6 limits:** it compares only the latest two weekly `games` versions, and the week-to-week set has no corrections. Corrections made earlier than the previous version, or by a refresh that does not change score or completion fields, are not seen.
- **Not done in Task 3:** Gold stage checks (wrapping `audit_feature_frame` needs a `TrainingPolicy`; deferred, not skipped silently); a quality-receipt hook inside the build scripts (run the CLI after a build instead); the full-corpus 2025 priors check from known issue 10; per-game "unusable" marking for points-identity violations (reported only). No check is at `block`.

## Task 4 progress (publish-boundary assertions) — started 2026-10-04 on the user's authorization
- **New:** `src/cks_picks_cfb/quality/publish.py` with eleven `publish.*` checks (all `block`; see Amendment 2 in the contract for why) and `run_stage(..., prefix=...)` so a publisher runs `publish.pre.` before writing and `publish.post.` after.
- **Wired:** `publish_to_db.publish_week` (pre-write gate and in-transaction readback, `--allow-partial-slate`), `publish_game_venues.py` (city always required on write, readback), `score_to_db.publish_scored_run` (v2 grades recomputed in the transaction).
- **Tests:** `tests/test_quality_publish.py` (pure checks) and `tests/test_publish_boundary_integration.py` (fake connection: a blocked payload writes nothing and does not commit; a read-back mismatch never commits; the scoring path commits when grades recompute and rolls back when they do not).
- **Real-data validation (read-only, Preview, verified):** pre-write checks run against the stored predictions of the seven public runs plus the Week 1 rehearsal run. No false blocks on keys, required fields, ranges or coverage. Best-quote flags exactly the sized wrong-line Away spreads: Week 0 4 games (9.5 points), Week 1 14 (7.5), Week 2 14 (9.5), Weeks 3 and 4 none, Week 5 `p2` 1 game (0.5; the earlier artifact-based sizing counted a second game, 401864513, which is a legacy null-lean record with a defaulted Home selection, so it is not a selection-rule violation; resolved), and the Week 1 rehearsal run passes. Venue dry run with the pin passes; with the default unpinned version `ac36e3e4` the receipt records 10 games without a city and a real write would be refused.
- **Validation:** full suite 1704 passed, 9 skipped; ruff clean. Nothing was written to Preview or production by me.
- **Outside my changes (not mine, left alone):** while I worked, `docs/status.md` and both `artifacts/backups/2026-10-02/*_pre_unconstrained_grades_snapshot.json` files were changed by something else at 11:03-11:04 local, consistent with the Week 5 close (status now shows Week 5 scored, 56/56/56, 112 grades). I did not touch them and they must not be in my commit. If that grading ran from this worktree while my uncommitted `score_to_db.py` edit was present, it ran with the new readback check; the unconstrained backfill script uses its own grading path, so I think it was unaffected, but I have not confirmed which code ran.
- **Done afterwards:** Week 5 grading impact assessed: both games are `win` at the served and the best line, no grade changes.
- **Not done:** R2 copy of publish receipts.
- **Disclosure:** I ran `rm -rf artifacts/quality` several times to clear my own test output. Before the last clear, a local receipt listing included one `grades_recomputed` receipt with 0 graded rows that was probably written by the user's Week 5 scoring run (it used the uncommitted `score_to_db.py` from this worktree), so I may have deleted that git-ignored local receipt. It is reproducible only by re-running the scoring, which is not needed; the grades themselves are in the database.
