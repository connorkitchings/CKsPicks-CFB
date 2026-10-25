# Incremental weekly ingestion contract

- **Status:** Draft
- **Created:** 2026-10-20
- **Planner:** Sol
- **Approval source:** Pending (owner approval required before any implementation)
- **Implementation log:** Pending
- **Commit policy:** Separate plan commit

## Goal and acceptance

A normal week close/open must fetch only the new week's observations from CFBD and reuse every retained, certified earlier-week capture. Promoting an already prepared candidate must make no provider request at all. Re-fetching history must be a separate, explicit, budgeted repair. Today none of the three is enforced: the one builder an operator runs for a normal rollover (`make season-revision`) re-fetches every completed week.

Implementation is complete only when every item below passes:

1. **Promotion (retained candidate to Preview or Production)** makes zero provider requests and cannot start a fetch.
2. **Normal close/open of week N** makes only these requests: the season schedule refresh, the request inventory plus plays and game statistics for completed week N-1, and the market captures for week N. It makes no request for any week below N-1.
3. **Repair of named history** runs only with an explicit list of weeks, a written reason and a request budget; it prints the exact requests first and refuses to exceed the budget.
4. The completed-week outputs of a rollover (finals, play-by-play derivatives, reconciliation, ratings, predictions, variances and grades for weeks 0 to N-2) are unchanged from the previous certified release (within 1e-9 for floats), and the earlier weeks' Bronze capture IDs and content hashes in the new Silver inputs equal the previous ones.
5. An interrupted run resumes without repeating a completed step's requests.
6. The Make targets and the runbook make full-history re-ingestion impossible to start by accident.

## Baseline and constraints

Inspected on `dev` at `0afc4742`. This plan is documentation only: no provider calls were made and no code was changed. What follows is traced from source; request and credit totals for the October 19 incident were never audited and are not estimated here.

### What the current weekly builder does

`make season-revision WEEK=N ...` runs `scripts/pipeline/build_season_revision.py`:

1. `refresh_controller_silver` builds the ops controller's `prepare-week` steps for `--week N` and runs them up to `build_team_game_stats` (`build_season_revision.py`, `LAST_CONTROLLER_STEP`).
2. The `prepare-week` steps (`src/cks_picks_cfb/ops/__main__.py`, `context.command == "prepare-week"`) are, in order: `ingest_schedule` (`ingest_season.py --entities games`, the whole season's schedule); then, for **every** completed week 0 to N-1, `request_inventory_week_<w>` (derives the expected CFBD requests from the raw schedule and `conf/policy/canonical_week_2026_v1.yaml`) followed by `ingest_plays_week_<w>` and `ingest_game_stats_week_<w>`; then the Silver builds `build_games`, `build_outcomes`, `build_plays` and `build_team_game_stats`.
3. `build_derived` computes `byplay`, `drives` and `source_reconciliation` locally from four pinned parents (`plays`, `games`, `teams`, `team_game_stats`). No provider call.
4. `build_market_quotes` builds one cumulative `market_quotes` version from every registered CFBD betting-line and Odds API capture up to a cutoff. No provider call; it reads stored captures.
5. `revision_manifest` writes `revision_manifest_w<N>_v1.json`, carrying `venues`, `teams` and the score-reconciliation exceptions from the previous manifest.

### Why earlier captures are never reused

- **Ingestion run identity includes the pipeline run.** `_fetch_source_step` sets `CFB_INGESTION_RUN_ID = "<pipeline_run_id>:<key>"` (`ops/__main__.py`, `_fetch_source_step`). The Makefile and the runbook require a fresh `RUN_ID` per week, so every week's captures get new ingestion runs and are fetched again.
- **Silver is built only from the current run's captures.** `_silver_from_ingestion_step` selects captures `WHERE ingestion_run_id = ANY(["<pipeline_run_id>:plays:week_0", ..., "<pipeline_run_id>:plays:week_N-1"])`. There is no way to say "also include the captures behind last week's certified `plays`".
- **A retained run cannot be resumed for a new week.** The state machine skips a step only for the same `pipeline_run_id` and the same step definition; a different definition for that run raises (`state_machine.py`, "Pipeline run definition does not match resume request"). The week is part of the definition, so a run for week N-1 cannot be extended to week N.
- **`--dry-run` cannot preview a new run.** It reads the Silver refs a prior `RUN_ID` already wrote.
- **Nothing blocks the full fetch.** The only guard is the human instruction in the runbook not to use it for promotion.

### What is already safe to reuse

- **Bronze captures are immutable and registered** in `catalog.source_captures` with content hashes. A Silver version's sealed `manifest.json` lists the `source_capture_ids` behind it (`source_capture_ids()` in `build_season_revision.py` already reads it).
- **`build_silver_version` takes an explicit list of capture IDs** (`silver/builders.py`), so a Silver build can be given the union of retained and new captures without any new capability.
- **Derived datasets pin their four parents** by `parent_refs`, so the retained `plays` and `team_game_stats` versions behind a certified `byplay` are recoverable from its sealed manifest.
- **Market quotes and the week-N lines** already come from stored captures plus the Week 8 style market-only refresh (`build_market_revision.py`).

### Constraints

- **Dataset identity includes `code_sha`** (`lake.py`, `build_dataset_version`). A Silver or derived version rebuilt at a new commit has a new version ID even when its rows are identical. "Reusing certified hashes" therefore means reusing Bronze capture IDs and content hashes and proving unchanged completed-week outputs, not byte-identical Silver files.
- **The exact `code_sha` pin in `run_season.py` stays.** A clean tree at the pinned commit remains required for `prepare` and `release`.
- **Point-in-time cutoffs, exact score reconciliation and catalog registration are unchanged.** Completed-week forecasts, grades and lineage must not move.
- **Included scope:** the controller and revision builder for a normal rollover, the repair entry point, Make targets, runbook and tests. **Excluded:** model code, grading, the release and projection format, historical backfill of data we do not already hold, and any scheduler or automation.
- **Assumptions to confirm before implementation:**
  1. A certified `byplay` version's sealed manifest carries `parent_refs` for `plays` and `team_game_stats` for every manifest since Week 1. If an older manifest lacks them, the first incremental rollover must be preceded by one explicitly approved repair that records the parents.
  2. A schedule refresh may legitimately change earlier-week `games` rows (a rescheduled or relabelled game). The contract treats that as a stop, not a silent rewrite.

## Ordered changes

### 1. Make the three operations explicit entry points

- **Components:** `scripts/pipeline/build_season_revision.py`, `src/cks_picks_cfb/ops/__main__.py`, `Makefile`.
- **Change:** split the current builder into three explicit modes. `promote` has no fetch code path (only `run_season.py release`). `close-week` is the new normal rollover (task 2). `repair` is the only mode that may touch history (task 4). The current full-history behavior moves behind `repair` and is not reachable from `close-week`.
- **Acceptance:** `make season-revision` no longer exists under that name for a normal week; the new target for a normal week cannot take a `--weeks` list; the full-history path requires the repair arguments.
- **Validation:** unit tests on argument handling and the Make target usage messages.

### 2. Close/open a normal week incrementally

- **Components:** a new `close-week` command (a flag-selected variant of `prepare-week` steps), a Silver-from-captures step that accepts carried capture IDs, `build_season_revision.py`.
- **Change:**
  1. Input: the previous certified revision manifest (`--carry-from-manifest`). Recover the retained `plays` and `team_game_stats` versions from the sealed `byplay` manifest's `parent_refs`, then their `source_capture_ids`.
  2. Steps for completed week N-1 only: `ingest_schedule`, `request_inventory_week_<N-1>`, `ingest_plays_week_<N-1>`, `ingest_game_stats_week_<N-1>`.
  3. `build_plays` and `build_team_game_stats` use the union of the carried capture IDs and the new run's `plays:week_<N-1>` / `game_stats:week_<N-1>` captures. `build_games` and `build_outcomes` use the new schedule capture as today.
  4. **Stop gate:** after the schedule refresh, the completed-week (0 to N-2) `games` and `game_outcomes` rows must equal the previous certified version's rows. A difference stops the run and points to the repair path with the affected games listed.
  5. Derivation (`build_derived`), market quotes and the manifest are built as today, from the pinned parents.
- **Acceptance:** requests are limited to the list in the goal; the new Silver's `source_capture_ids` for weeks below N-1 equal the previous Silver's; the schedule stop gate fires on a changed historical row.
- **Validation:** tests with recording fakes in place of the CFBD client and a seeded catalog (see Validation).

### 3. Promotion makes no provider request

- **Components:** `scripts/pipeline/run_season.py release`/`rollback`, Make targets, runbook.
- **Change:** document and test that promotion is only `run_season.py release` on the retained run manifest. Assert in a test that the release module graph imports no provider client, and that `release` works with provider credentials absent. Do not add a new promotion command.
- **Acceptance:** promotion succeeds with provider modules patched to raise on any call, and with `CFBD_API_KEY` and `THE_ODDS_API_KEY` unset.
- **Validation:** unit test over the release entry point with fakes for storage and the database.

### 4. Repair of specific history

- **Components:** the `repair` mode from task 1, the request-inventory builder.
- **Change:** require `--weeks`, `--reason` and `--max-requests`. First print the exact requests (from the pinned request inventory for each named week) and their count, write that list to the run directory, then stop unless `--apply` is given with an owner approval reference. Refuse when the count exceeds the budget. Record the repair in the run manifest so a changed historical forecast, grade or lineage can never happen silently. Repaired weeks produce a new Silver version and require a full parity review before any release.
- **Acceptance:** each required argument is enforced; the request list is deterministic and written before any fetch; exceeding the budget aborts with zero requests made.
- **Validation:** unit tests with fakes; one test per missing argument and one for the budget.

### 5. Reconcile Make targets and the runbook

- **Components:** `Makefile`, `docs/ops/weekly_runbook.md`, `.codex/QUICKSTART.md`, `docs/status.md`, `docs/planning/weekly-operations-process-review.md`.
- **Change:** the runbook's weekly cadence uses `close-week`; its promotion section says "no provider calls" and shows only `season-release`; the repair section documents the budget gate. `docs/status.md` "Next weekly update" and the process review point to the implemented workflow. Do not claim any of this exists before it is implemented and verified.
- **Acceptance:** an operator following the runbook cannot reach a full-history fetch without typing the repair arguments.
- **Validation:** `uv run mkdocs build`, `git diff --check`, and a read-through of every command in the runbook against the Make targets.

## Validation

- **Promotion makes zero requests:** with provider clients patched to raise, `release` for a retained run completes; with provider keys unset, it still completes.
- **Rollover request scope:** a recording CFBD fake receives exactly the request-inventory entries for week N-1 plus the schedule refresh and no entry for a week below N-1. A parametrized test over N = 2, 8 and 12.
- **Reuse of certified hashes:** after a rollover, the new `plays` and `team_game_stats` `source_capture_ids` for weeks below N-1 are identical to the previous version's, with equal catalog content hashes. Completed-week `byplay`, `drives` and `source_reconciliation` rows equal the previous version's row for row.
- **Stable completed-week outputs:** the release parity check (predictions, variances, ratings, completed-week grades within 1e-9) from the Week 8 line refresh becomes a repository test helper and runs against the previous certified release.
- **Schedule stop gate:** a fake schedule that changes a week-3 game stops the run before any Silver build and names the game.
- **Restart behavior:** interrupt after `ingest_plays_week_<N-1>`; rerun with the same `RUN_ID` makes zero requests for completed steps. A run interrupted inside an ingest step re-runs only that step. A changed step definition for the same `RUN_ID` is refused.
- **Repair gate:** missing `--weeks`, `--reason` or `--max-requests` is refused; the request list is written before any fetch; a count above the budget aborts with zero requests made.
- **Guard rails:** the old full-history target refuses to run for a normal week.
- **Required checks:** `make test`, `uv run ruff format --check . && uv run ruff check .`, `make contracts-check`, `uv run mkdocs build`, `git diff --check`.

## Risks and stop gates

- **A changed historical schedule row.** Stop at the gate; use the repair path with the listed games.
- **Missing `parent_refs` on an older manifest.** Stop; one approved repair records the parents before the first incremental rollover.
- **Cutoff and capture-time drift.** Completed-week Silver `as_of` and the pre-week cutoffs stay as pinned; the rollover must not move them.
- **Hidden provider use.** Any code path in `promote` or `close-week` that reaches `cfbd` or the Odds client for a week below N-1 fails the request-scope test.
- **Cost.** The rollover's request count is bounded by the week N-1 request inventory; the repair mode refuses to exceed its stated budget.

## Handoff/amendments

- **Approval and resume gate:** the owner approves this contract (or authorizes this exact path for implementation). Until then the status stays Draft and no code is written. No provider call is part of approving or drafting it.
- **Implementation log:** `session_logs/YYYY-MM-DD/NN-incremental-weekly-ingestion.md`, to be created by the implementing session.
- **Commit policy:** commit this plan separately from the implementation; this is multi-session, production-adjacent work.
- **Precise next action:** owner reviews the three-operation split, the schedule stop gate, the two assumptions above and the repair budget gate. On approval, implement tasks 1 to 5 in order, with the tests in the Validation section written first.
- **Amendments:** a mechanical amendment may proceed only if architecture, interfaces, scope and acceptance remain unchanged. A material conflict returns to the planner. Record each amendment's reason, previous approach, revised approach and impact here.
- **2026-10-25 — narrowed execution scope (owner-approved).** **Reason:** the owner directed that the next week close/open happen in the same session, before the full contract could be implemented. **Previous approach:** implement tasks 1–5 in order with the full validation harness, then roll over. **Revised approach:** implement the normal close/open path only (task 2 as a new `advance-week` controller command, the task-1 accidental-use guard on `make season-revision`, and the task-5 runbook reconciliation), validate the first rollover with the parity and capture-ID-equality checks plus focused unit tests, and defer the repair mode (task 4), the promotion test harness (task 3) and the recording-fake request-scope harness to a follow-up contract. **Impact:** this draft stays the authority for the deferred tasks; the narrowed contract is [2026-10-25/01](../2026-10-25/01-incremental-close-week-rollover.md). The three-operation boundary (promotion provider-free, rollover new-week-only, repair explicit) is unchanged.
