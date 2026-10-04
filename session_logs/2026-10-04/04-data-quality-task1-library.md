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
