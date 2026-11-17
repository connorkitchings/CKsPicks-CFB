# Session: Near-kickoff line capture implementation

## TL;DR

- **Worked On:** Contract 1, near-kickoff line capture (analysis only): entity decision, capture path, workflow, runbook.
- **Outcome:** Near-kickoff captures register under a distinct Bronze entity, `market_quotes_near_kickoff`, that no revision, prepare, snapshot, grading or site path selects. A GitHub workflow with primary and backup slots is added behind a repository variable.
- **Plan Contract:** [`docs/plans/2026-11-12/01-near-kickoff-line-capture.md`](../../docs/plans/2026-11-12/01-near-kickoff-line-capture.md)
- **Approval / Status:** Owner approved implementation 2026-11-12 ("yes, go ahead with contract 1").
- **Blockers:** None for the code. The workflow cannot run until the `dev` to `main` release and the owner sets `CFB_NEAR_KICKOFF_CAPTURE_ENABLED`.
- **Next:** Owner review, commit and pull request into `dev`; after release, enable the variable and run the confirmed Preview capture check.

**tags:** ["odds-api", "closing-line", "automation"]

## Context and Decisions

### Task 1 finding: entity, not label (no migration, no verification change)

How captures are selected today:

- `scripts/pipeline/build_season_revision.py::season_market_capture_ids` (used by `build_season_revision.py` and `build_market_revision.py`) selects `catalog.source_captures` rows with `state = 'registered'` and `(provider = 'cfbd' AND entity = 'betting_lines' AND request year matches)` or `(provider = 'the_odds_api' AND entity = 'market_quotes' AND captured calendar year matches)`. The filter is on the **entity string**; no label or request field is consulted, so a label inside `market_quotes` would be ingested.
- `scripts/pipeline/build_week_market_snapshot.py` selects a controller run's captures by `ingestion_run_id` plus `entity = 'market_quotes'` / `'betting_lines'`, and `market_captures` refuses any capture whose `(provider, entity)` is not in `MARKET_SOURCES = {("cfbd","betting_lines"), ("the_odds_api","market_quotes")}`.
- `src/cks_picks_cfb/season/inputs.py` does not select captures. It reads the `market_quotes` Silver dataset refs pinned in the revision manifest (`r["market_quotes"]`), which are built only from the capture ids above.
- Other readers keyed on the entity string: `src/cks_picks_cfb/quality/loaders.py::latest_odds_capture` (`entity = 'market_quotes'`). `src/cks_picks_cfb/ops/__main__.py` (the Odds API soft-fail step) selects by the controller's own `ingestion_run_id` (`<pipeline_run_id>:market_quotes`) and `provider`, so a separately named run is not picked up.

Decision: new Bronze entity `market_quotes_near_kickoff`, provider `the_odds_api`. Code paths that would ingest it: none.

Stop gate check: `catalog.ingestion_runs.entity` and `catalog.source_captures.entity` are free `TEXT NOT NULL` columns (migration 0003); the only CHECK constraints concern `state`. Bronze paths are keyed `provider=/entity=/content_sha=`. No Silver contract, schema contract or dataset is registered for the new entity (it stays Bronze only), so no schema migration and no change to verification rules is needed. Gate not triggered.

## Work Completed

- Added `NEAR_KICKOFF_ENTITY` / `MARKET_QUOTES_ENTITY` and let the adapter accept both; `fetch_odds_api_market_quotes.py --near-kickoff` registers under the new entity (default unchanged).
- Added `scripts/ops/near_kickoff_slot.py` (`decide_slot`, `completed_slot_ids`): slot = Eastern kickoff day in Weeks 12 to 15; skips Sunday/Monday, no-kickoff days, passed kickoffs, already-captured slots, and more than two midweek slots per week.
- Added `.github/workflows/near-kickoff-capture.yml` (Preview credentials, variable `CFB_NEAR_KICKOFF_CAPTURE_ENABLED`, concurrency group `near-kickoff-capture`, primary and backup crons, run id `near-kickoff-<slot>-<run>-<attempt>`).
- Runbook section, status line, contract status and plans index updated.

## Files Modified

- `src/cks_picks_cfb/data/the_odds_api.py`, `scripts/data/fetch_odds_api_market_quotes.py`
- `scripts/ops/near_kickoff_slot.py`, `.github/workflows/near-kickoff-capture.yml`, `tests/test_near_kickoff_capture.py`
- `docs/ops/weekly_runbook.md`, `docs/status.md`, `docs/plans/index.md`, `docs/plans/2026-11-12/01-near-kickoff-line-capture.md`

## Validation

- Targeted tests (new file, existing Odds API/revision/ops-step tests): 54 passed, including the real-Postgres check that `season_market_capture_ids` excludes a near-kickoff capture.
- `make check`: ruff, contracts, quality and pytest (2441 passed, 24 skipped) and mkdocs strict passed; the final web step failed with `eslint: command not found` (web dependencies not installed in this worktree, unrelated).
- `git diff --check` clean; `uv run mkdocs build --strict --quiet` exit 0.
- Not done: dry run and confirmed Preview capture (need DATABASE_URL and provider access; no provider calls were made).

## Amendments and Blockers

- **Real Preview confirmed capture (2026-11-12).** Registered 1 event and 2 quotes as capture `d0d3d98e91ab4d51ad56c22845f3d9e3` under entity `market_quotes_near_kickoff`. The weekly `market_quotes` entity is unchanged at 13 captures, last `2026-11-08T17:58Z`. The `cks_preview_pipeline` role was verified to have INSERT/UPDATE on `catalog.ingestion_runs` and INSERT/SELECT on `catalog.source_captures` (this closes the privilege check flagged under Handoff Notes). Only 1 of 66 week games matched, which is expected for a capture nine days before kickoff, but the script had printed all 559 unmatched board events and exited successfully.
- **Workflow environment.** The orchestrator added `environment: season-production` to the workflow so the environment secret `PREVIEW_PIPELINE_DATABASE_URL` resolves.
- **Matched-games safeguard (owner approved).** In near-kickoff mode only: expected games are the stored-schedule games kicking off later on the slot's Eastern day (`expected_slot_game_ids` in `scripts/ops/near_kickoff_slot.py`); if fewer than `MIN_MATCH_RATIO` (0.80) have quotes the script exits non-zero with counts, ratio and threshold. No expected games means no failure. `--min-match-ratio` overrides (0 disables, for manual early captures). Decision: register the capture, then fail the run: the capture is immutable evidence and credits are spent, but the ingestion run is marked `failed` (`MatchRatioBelowThreshold`) so the slot stays open and the backup slot retries. The unmatched-events warning is now a count plus at most 5 sample names in near-kickoff mode; weekly mode output is byte-identical. Tests added in `tests/test_near_kickoff_capture.py` (ratio below, at and above threshold, no expected games, override 0, truncated output, weekly output unchanged, and `main()` with fakes for register-then-fail).

## Handoff Notes

- **Resume at:** Owner review.
- **Watch out for:** a backup run after a failed ratio check registers a second capture for the same slot (by design; captures never overwrite).
