# Incremental close-week rollover (narrow amendment) and Week 8→9 advance

- **Status:** In Progress
- **Created:** 2026-10-25
- **Planner:** Sol
- **Approval source:** Owner approved the presented plan in session on 2026-10-25 (narrow-amendment path C; Odds API Week 9 capture authorized at ~2 credits; Preview-only, no Production activation and no `dev`→`main` merge).
- **Implementation log:** `session_logs/2026-10-25/02-incremental-close-week-rollover.md`
- **Commit policy:** Separate plan commit; implementation commit(s) reviewed by the owner before the operational rollover. Git operations remain user-controlled.

## Goal and acceptance

A normal week close/open must fetch only the new observations from providers and reuse every retained, certified earlier-week capture. Today the only weekly entry point (`make season-revision` → `build_season_revision.py` → controller `prepare-week`) re-ingests Weeks 0..N−1 on every rollover, which the [weekly runbook](../../ops/weekly_runbook.md) has paused for routine advancement since the 2026-10-19 incident. This contract implements the **normal close/open path only** — a narrow amendment of [the incremental-ingestion draft](../2026-10-20/02-incremental-weekly-ingestion.md) (its task 2 plus the accidental-use guard of task 1 and the runbook reconciliation of task 5) — and then uses it to close Week 8 and open Week 9 on the data lake and Preview. Promotion stays provider-free (already true). The repair mode (draft task 4) and the promotion test harness (draft task 3) remain deferred to the full draft contract.

**Definition of done:**

1. `make season-close-week WEEK=N AS_OF=… PRE_WEEK_CUTOFF=… RUN_ID=…` builds `revision_manifest_w<N>_v1.json` with provider requests limited to: the season schedule refresh, the request inventory plus plays and game statistics for completed week N−1, and the explicitly run market captures. No request touches any week below N−1.
2. `make season-revision` refuses to run without an explicit `FULL_HISTORY=1` ack and prints the incremental alternative.
3. The completed-week outputs of the Week 9 rollover are unchanged from the certified Week 8 release: predictions, variances, ratings and completed-week (0–7) grades within 1e-9, and the new `plays`/`team_game_stats` Silver versions carry exactly the certified Weeks 0–7 source-capture IDs (8 each) plus the new Week 8 captures.
4. The Week 9 candidate passes all `season_verification_v2` checks, is activated on Preview with readback, and Production is untouched.
5. The runbook's weekly cadence documents the incremental path as the normal procedure; `docs/status.md` reflects the Preview-only advancement after verification.

## Baseline and constraints

- Inspected on `dev` at `5a370d5e` (worktree branch `connorkitchings/incremental-close-week`). Storage is `CFB_STORAGE_BACKEND=r2`; all commands run under `scripts/ops/with_preview_env.sh` (`CFB_ARTIFACT_ENV=preview`).
- Week state: Weeks 0–7 scored; Week 8 slate complete and awaiting ingestion. Active releases `production-season-2026-125158328e025fb89c96ce0d` / `preview-season-2026-125158328e025fb89c96ce0d` (Week 8 line refresh, pre-week-8 cutoff `2026-10-20T14:39:00Z`).
- **Carry-forward evidence (verified read-only against R2):** the certified `plays` (`90dd40851581cf0fc74707ae`) and `team_game_stats` (`17c47043c9efc7f787b55f05`) versions behind `revision_manifest_w8_v3.json` each list exactly 8 `source_capture_ids` (Weeks 0–7). The certified `byplay` manifest (`def44c3f435ae7d12701bba5`) lists `parent_versions` as four bare version IDs without dataset names; they resolve by reading each candidate dataset's manifest (`dataset` and `version_id` fields) across `DERIVED_PARENTS = ("plays", "games", "teams", "team_game_stats")`.
- **Controller mechanics (verified in source):** `_silver_from_ingestion_step` selects captures by `ingestion_run_id = ANY(["<run_id>:<key>", …])` and passes each as `--capture-id` to `scripts/pipeline/build_silver.py`; `_fetch_source_step` sets `CFB_INGESTION_RUN_ID = "<pipeline_run_id>:<key>"`, so a fresh `RUN_ID` re-fetches every week in the current loop. `new_context(command=…)` accepts any string; the name `close-week` is already taken by the legacy publishing flow, so the new command is `advance-week`.
- **Constraints carried from the draft:** dataset identity includes `code_sha` (reusing certified history means reusing Bronze capture IDs and content hashes, not byte-identical Silver files); point-in-time cutoffs, exact score reconciliation and catalog registration are unchanged; the `run_season.py` clean-tree/commit pin stays; completed-week forecasts, grades and lineage must not move.
- **Included scope:** the controller `advance-week` command, the builder's incremental mode with carried captures and the history stop gate, the Make targets, runbook/quickstart updates, focused tests, and the Week 8→9 operational rollover (Preview only). **Excluded:** the repair mode with request budgets (draft task 4), promotion test assertions (draft task 3), model code, grading, the release/projection format, and any Production or `main` action.
- **Assumptions confirmed:** parent version IDs are recoverable from the certified byplay manifest (verified); a schedule refresh may legitimately change earlier-week `games` rows — the stop gate treats that as a stop, not a silent rewrite.
- **Risks and stop gates:** a stop-gate difference halts the rollover with the affected games listed and no derived build; incomplete Week 8 finals fail exact score reconciliation (retry after finals post); new score mismatches require declared exceptions in `conf/season/2026/score_reconciliation_exceptions.json`; an interrupted controller run resumes with the same `RUN_ID` without repeating completed steps' requests.

## Ordered changes

### 1. Persist this contract and the amendment record

- **Components:** `docs/plans/2026-10-25/01-incremental-close-week-rollover.md`, [2026-10-20/02 draft](../2026-10-20/02-incremental-weekly-ingestion.md) Amendments section, `docs/plans/index.md`, planning session log.
- **Change:** record this contract as an amendment of the draft (reason: move the week forward this session; revised approach: implement the normal close/open path only; impact: repair mode and promotion harness deferred). Register in the plans index under Current Execution.
- **Acceptance:** `git diff --check` and `uv run mkdocs build --quiet` pass.

### 2. Controller `advance-week` command

- **Components:** `src/cks_picks_cfb/ops/__main__.py`.
- **Change:** a new `command == "advance-week"` branch in `build_steps` producing, in order: `ingest_schedule`; `request_inventory_week_{N−1}`, `ingest_plays_week_{N−1}`, `ingest_game_stats_week_{N−1}` (completed week only); `build_week_policy`; `build_games`; `build_outcomes`; `verify_completed_week_stability` (subprocess step, argv built from caller-provided gate arguments); `build_plays` and `build_team_game_stats` with `extra_capture_ids` merged into the run's captures. Nothing after `build_team_game_stats` (the builder truncates there anyway).
- **Interface:** `build_steps(context, conn_url=…, advance=None)` where `advance` is `None` for existing commands and for `advance-week` a mapping `{"carried_captures": {"plays": [...], "team_game_stats": [...]}, "gate": {"previous-games-ref-uri": …, "previous-outcomes-ref-uri": …, "through-week": N−2, "season": …}}`. `_silver_from_ingestion_step` gains `extra_capture_ids: Sequence[str] | None = None`; the final capture list is the deduplicated union sorted deterministically, and the extras are part of the step definition so resume identity is preserved.
- **Acceptance:** the step list for `advance-week` week 9 is exactly the eleven steps above in order; existing commands are unchanged.

### 3. Carried-capture resolution and incremental builder mode

- **Components:** `scripts/pipeline/build_season_revision.py`.
- **Change:** `--incremental` selects the incremental path and requires the previous manifest (default `revision_manifest_w{week−1}_v1.json`). New `carried_capture_ids(storage, previous)` resolves, from `inputs.byplay.uri`: the byplay manifest's `parent_versions` → the `plays` and `team_game_stats` version manifests → their `source_capture_ids`. `refresh_controller_silver` gains the `advance` argument and passes `command="advance-week"`. After the controller run, the builder executes the stop-gate comparison (imported from the gate script) before `build_derived`; a difference aborts with the affected games. `--dry-run` keeps its existing semantics.
- **Acceptance:** `make season-close-week` produces `revision_manifest_w9_v1.json` whose `inputs.byplay/drives/reconciliation` derive from the union-capture Silver; the manifest's football-input cutoffs for weeks 0–7 are byte-identical to `w8_v3`.

### 4. History stop gate

- **Components:** new `scripts/pipeline/verify_completed_week_stability.py`.
- **Change:** read the new and previous `games`/`game_outcomes` datasets by ref URI, compare all rows with `week <= through-week` keyed by `game_id` (and `team` where applicable), print every differing `game_id` with a short reason, exit non-zero on any difference. Used both as the controller subprocess step and directly by the builder.
- **Acceptance:** identical inputs pass; a changed historical row fails naming the game; differences in weeks above the through-week are ignored.

### 5. Make targets and accidental-use guard

- **Components:** `Makefile`.
- **Change:** new `season-close-week` target wrapping the builder with `--incremental` (variables `WEEK`, `AS_OF`, `PRE_WEEK_CUTOFF`, `RUN_ID`, optional `PREVIOUS_MANIFEST`). `season-revision` refuses unless `FULL_HISTORY=1`, printing that the normal rollover is `season-close-week` and that the full-history path is a repair vehicle.
- **Acceptance:** `make season-revision` without the ack exits non-zero with the guidance; `make season-close-week WEEK=9 …` reaches the builder with the expected arguments.

### 6. Documentation

- **Components:** `docs/ops/weekly_runbook.md`, `.codex/QUICKSTART.md`.
- **Change:** the weekly cadence's revision step uses `season-close-week` with the request-scope boundary stated; the full-history description moves to a history-repair subsection behind the `FULL_HISTORY=1` ack; the "execution paused" gate language is replaced by the implemented boundary (promotion remains provider-free, unchanged). `docs/status.md` and the process-review brief update only after the rollover is verified (step 8).
- **Acceptance:** `uv run mkdocs build --strict`; an operator following the runbook cannot reach a full-history fetch without the explicit ack.

### 7. Focused tests

- **Components:** `tests/`.
- **Change:** unit tests for: the `advance-week` step list and order (pure step construction); `carried_capture_ids` against fixture manifests (including a version-ID that resolves to each parent dataset); the stop-gate comparator (identical pass, single-row mismatch naming the game, above-through-week difference ignored); the Make-target guard behavior is exercised by the acceptance run of task 5. Defer the draft's full recording-fake request-scope harness to the follow-up contract.
- **Acceptance:** `uv run pytest tests/<new files>` passes; `uv run ruff format --check . && uv run ruff check .` clean.

### 8. Operational rollover: close Week 8, open Week 9 (Preview only)

- **Steps, in runbook order:**
  1. Pre-flight: confirm every Week 8 game is final; confirm Week 9's first kickoff from the refreshed schedule; set `POST_WEEK_CUTOFF` (after finals posted) and `PRE_WEEK_CUTOFF` (after the last line capture, strictly before the first Week 9 kickoff; prepare runs at/after it).
  2. Captures under the Preview wrapper: CFBD `betting_lines` for Weeks 8 and 9; Odds API Week 9 quotes with `--confirm` (owner-authorized, ~2 credits).
  3. `make season-close-week WEEK=9 AS_OF=$POST_WEEK_CUTOFF PRE_WEEK_CUTOFF=$PRE_WEEK_CUTOFF RUN_ID=w9-incremental-$(date -u +%Y%m%d%H%M)`; verify the printed request scope stayed within the boundary.
  4. Refresh `score_reconciliation_exceptions.json` for Week 8 finals (add mismatches, remove repaired games), re-pin its SHA-256 into the manifest, commit manifest + exceptions, clean tree.
  5. After the clock passes `PRE_WEEK_CUTOFF`: `make season-prepare WEEK=9 AS_OF=$PRE_WEEK_CUTOFF` — all `season_verification_v2` checks pass; no commit between prepare and the last release.
  6. Parity vs the Week 8 release: weeks 0–7 predictions, variances, ratings and grades within 1e-9; new `plays`/`team_game_stats` capture IDs for weeks 0–7 equal the certified sets.
  7. `make season-release ENV=preview RELEASE_ID=… PROJECTION_SHA=… EXPECTED_PREVIOUS=preview-season-2026-125158328e025fb89c96ce0d`; verify `make web-local ENV=preview` (Games shows Week 9 picks and Week 8 scored, Ratings, Model, `/api/health` reports Week 9).
  8. Update `docs/status.md` (Preview advanced; Production release IDs unchanged), the process-review brief, and write the implementation session log. **Not done:** Production activation, `dev`→`main` merge, any Production Neon write.
- **Acceptance:** done-definition items 3–5 above.

## Validation

- Task-level checks as listed above, plus `git diff --check` at each stage close.
- Operational evidence retained: builder request-scope output, manifest diff vs `w8_v3` (football cutoffs identical), prepare verification output, parity comparison results, Preview activation readback SHA-256, live Preview page checks.
- Recovery: an interrupted controller run resumes with the same `RUN_ID`; a failed prepare after an exceptions edit reruns from the re-pinned, recommitted manifest.

## Handoff/amendments

- **Approval and resume gate:** owner approved the narrow-amendment path on 2026-10-25; implementation and the operational rollover proceed in this session's branch. Production activation remains a separate owner decision at a later time.
- **Implementation log:** `session_logs/2026-10-25/02-incremental-close-week-rollover.md`.
- **Commit policy:** git operations remain user-controlled; proposed commits: (1) plan + amendment record, (2) implementation, (3) Week 9 manifest + exceptions (required by the runbook before prepare), (4) post-release docs + log.
- **Precise next action:** implement tasks 2–7, then run the rollover (task 8) with the owner's cutoff confirmation.
- **Amendments:** none yet. A mechanical amendment may proceed only if architecture, interfaces, scope and acceptance remain unchanged; a material conflict returns to Sol.
- **2026-10-25 — mechanical: stop-gate comparison exclusions (evidence-based).** During the first Week 9 rollover run the gate stopped on 388 completed-week differences that decompose into two inert groups: (1) provenance columns `__capture_id`/`__captured_at`/`__capture_provider`, re-stamped on every Silver build, and (2) `home_postgame_elo`/`away_postgame_elo` on exactly the 56 Week 7 games — CFBD recomputes the most recently completed week's postgame Elo as the next week finishes (pregame Elo and finals identical on every affected game; no code outside the ingester reads any `_elo` column). The gate now compares everything except this documented denylist (fail-closed: new columns are compared by default), `*_pregame_elo` stays gated, and the acceptance criterion "a changed historical row fails naming the game" is unchanged for schedule, finals and feature-relevant data. Architecture, interfaces, scope and acceptance are unchanged.
