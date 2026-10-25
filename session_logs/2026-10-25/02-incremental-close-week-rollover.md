# Session: Incremental close-week rollover (Week 8 close, Week 9 open, Preview only)

## TL;DR

- **Worked On:** Implemented the normal close/open path (`advance-week`, carried captures, history stop gate, `season-close-week` target and the `FULL_HISTORY=1` guard) and ran the Week 8→9 rollover with it.
- **Outcome:** Preview advanced to `preview-season-2026-7a59b8a92d0f7a85ca0a377b` (Week 8 scored, Week 9 picks, as of 2026-10-25T16:00:00Z, 56/56 predicted, 30 lined); Production unchanged (`production-season-2026-125158328e025fb89c96ce0d`). Contract marked Implemented.
- **Plan Contract:** [`docs/plans/2026-10-25/01-incremental-close-week-rollover.md`](../../docs/plans/2026-10-25/01-incremental-close-week-rollover.md)
- **Approval / Status:** Owner approved the narrow-amendment path on 2026-10-25 (Odds API Week 9 capture authorized at ~2 credits; Preview-only, no Production activation, no `dev`→`main` merge). Implemented and verified.
- **Blockers:** None. Mid-week market refresh recommended before Tuesday's 23:00Z kickoff to top up Week 9 line coverage (30/56).
- **Next:** Owner decision on Production activation of the Week 9 release and the `dev`→`main` merge; optional owner-triggered mid-week market refresh (~2 credits).

**tags:** ["data", "pipeline", "weekly-operations", "preview-release"]

## Context and Decisions

- Branch `connorkitchings/incremental-close-week` (worktree), based on `dev` at `5a370d5e`; all data commands under `zsh scripts/ops/with_preview_env.sh` with `CFB_STORAGE_BACKEND=r2`.
- Week state at start: Weeks 0–7 scored; Week 8 slate complete; active releases `production-season-2026-125158328e025fb89c96ce0d` / `preview-season-2026-125158328e025fb89c96ce0d`.
- Carry-forward evidence (read-only R2): certified `plays` (`90dd40851581cf0fc74707ae`) and `team_game_stats` (`17c47043c9efc7f787b55f05`) each carry exactly 8 Week 0–7 source-capture IDs; byplay parents resolve by reading each candidate dataset's manifest.
- Cutoffs: `POST_WEEK_CUTOFF=2026-10-25T15:00:00Z`, `PRE_WEEK_CUTOFF=2026-10-25T16:00:00Z`, `RUN_ID=w9-incremental-202610251459`. Week 9 first kickoff Tuesday 2026-10-27T23:00Z.
- Stop-gate comparison (mechanical amendment): excludes provenance columns (`__capture_id`, `__captured_at`, `__capture_provider`) and `*_postgame_elo` (CFBD recomputes the most recent completed week's postgame Elo as the next week finishes; pregame Elo and finals stay identical; no code outside the ingester reads any `_elo` column). `*_pregame_elo` stays gated. Verified 2026-10-25: exactly the 56 Week 7 games moved on postgame Elo while pregame/finals stayed byte-identical.

## Work Completed

### Implementation (tasks 2–7)
- `advance-week` controller command in `src/cks_picks_cfb/ops/__main__.py`: schedule refresh, Week-8-only request inventory/plays/game stats, games/outcomes, stop gate, plays/team_game_stats from the union of carried certified captures and the new week's captures. `_silver_from_ingestion_step` gained `extra_capture_ids` (part of the step definition; catalog-presence guard).
- `scripts/pipeline/build_season_revision.py --incremental`: `carried_capture_ids()` resolves the carry set from the certified byplay manifest's parents; `refresh_controller_silver` accepts `advance`.
- `scripts/pipeline/verify_completed_week_stability.py`: stop gate reading controller refs from R2 storage; compares completed weeks 0..N−2 `games`/`game_outcomes` and names any differing game.
- `Makefile`: new `season-close-week`; `season-revision` refuses without `FULL_HISTORY=1`.
- Runbook, QUICKSTART, AGENTS.md: incremental path documented as normal procedure; full-history path moved behind the ack.
- Focused tests: `tests/test_incremental_close_week.py` (carried-capture resolution, stop-gate comparator incl. scope boundaries) and `tests/test_ops_state_machine.py` (advance-week step plan/order). 53 focused tests pass; `make test` baseline unchanged (same 16 pre-existing `dev` failures).

### Operational rollover (task 8)
- Line captures: CFBD Week 8 betting lines (112 records), CFBD Week 9 (30 records), Odds API Week 9 (40 quotes / 10 events, ~2 credits authorized). 21 of 56 Week 9 events did not match the Oct 20 schedule snapshot (kickoff drift); deferred to the mid-week market refresh.
- `make season-close-week WEEK=9 … RUN_ID=w9-incremental-202610251459`: completed in ~75s; stop gate passed; new Silver versions `plays` `99bd36ab9e8000bd79da11a8`, `team_game_stats` `526968d2bea09ea423e3055b` (8 certified + 1 new capture each). Manifest `revision_manifest_w9_v1.json` (revision_id `season-2026-w9-preview-r1`).
- Score reconciliation: prepare surfaced two Week 8 mismatches (Ole Miss 3 vs 27, Eastern Michigan 0 vs 20); added to `score_reconciliation_exceptions.json` (45 entries), re-pinned SHA-256 into the manifest, recommitted.
- `make season-prepare WEEK=9 AS_OF=2026-10-25T16:00:00Z`: passed all 24 `charts_v2` checks. Candidate `season-2026-7a59b8a92d0f7a85ca0a377b`, serving-projections SHA-256 `ebd6531221636113227ae9198805bc27eabb6bd6e039c7ee21e40eb9d64d5bf2`.
- Parity vs the certified Week 8 release: predictions, variances, ratings, current ratings and completed-week grades for weeks 0–7 identical within 1e-9 (only `source_ref`/`run_id` identity columns differ). Capture-ID sets for weeks 0–7 fully carried.
- `make season-release ENV=preview … EXPECTED_PREVIOUS=preview-season-2026-125158328e025fb89c96ce0d`: activated with readback SHA-256 `de7659e0b6d0f8f211b968281ea2461b7afa158a7a2a0b76efd419739bb5db42`. Web smoke test: `/api/health` reports Week 9, 56/56 predicted, 30 lined, data as of 2026-10-25T16:00:00Z; `/`, `/ratings`, `/stats`, `/model` all 200.

## Files Modified

- `src/cks_picks_cfb/ops/__main__.py` — `advance-week` command; `extra_capture_ids` on `_silver_from_ingestion_step`.
- `scripts/pipeline/build_season_revision.py` — `--incremental`, `carried_capture_ids()`, `advance` handoff.
- `scripts/pipeline/verify_completed_week_stability.py` — new stop gate.
- `Makefile` — `season-close-week`; guarded `season-revision`.
- `tests/test_incremental_close_week.py`, `tests/test_ops_state_machine.py` — new tests.
- `docs/ops/weekly_runbook.md`, `.codex/QUICKSTART.md`, `AGENTS.md` — incremental path documented.
- `conf/season/2026/revision_manifest_w9_v1.json`, `score_reconciliation_exceptions.json` — Week 9 pinned inputs.
- `docs/status.md`, `docs/planning/weekly-operations-process-review.md`, `docs/plans/...` — status and contract updates.

## Validation

- [x] Focused tests: 53 pass (incremental close week + ops state machine + season revision + market revision).
- [x] `uv run ruff format --check .` and `uv run ruff check .` clean.
- [x] `uv run mkdocs build --strict` clean.
- [x] `git diff --check` clean.
- [x] Stop gate: "Completed weeks 0..7 match the previous certified revision."
- [x] Parity vs certified Week 8 release: weeks 0–7 predictions/variances/ratings/grades within 1e-9.
- [x] Capture-ID equality: weeks 0–7 certified sets fully carried (8 each) plus 1 new Week 8 capture each (9 total).
- [x] Preview activation readback SHA-256 `de7659e0b6d0f8f211b968281ea2461b7afa158a7a2a0b76efd419739bb5db42`.
- [x] Web smoke test against Preview: health reports Week 9; all four tabs 200.

## Amendments and Blockers

- Mechanical amendment recorded in the contract: stop-gate comparison excludes provenance and postgame-Elo columns (evidence-based, architecture/interfaces/scope/acceptance unchanged).
- No blockers. Mid-week market refresh recommended before Tuesday's 23:00Z kickoff to top up Week 9 line coverage.

## Handoff Notes

- **Resume at:** Session complete (Preview only). Owner decisions pending: Production activation of `preview-season-2026-7a59b8a92d0f7a85ca0a377b` and the `dev`→`main` merge; optional mid-week market refresh (~2 credits).
- **Watch out for:** Production activation requires owner approval and independent Preview proof; the `dev`→`main` merge releases the four-tab site. Do not run `make season-revision` without `FULL_HISTORY=1`.