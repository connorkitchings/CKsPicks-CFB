# Session: Week 0 launch and Week 1 continuity implementation

## TL;DR

- **Worked On:** Implemented the approved Week 0 safety and Week 1 continuity contract.
- **Outcome:** Canonical Week 0 source ingestion is provider-week aware; close/scoring is bound to immutable outcomes and rejects partial finals; a resumable `prepare-week` rebuilds cumulative 2026 Silver/Gold and gates later-week publishing on an explicit prepared Gold ref.
- **Plan Contract:** `docs/plans/2026-08-21/week0-launch-week1-continuity.md`
- **Approval / Status:** User approved implementation in this task. Contract remains `In Progress` pending the intentionally deferred live Preview Week 1 rehearsal after Week 0 closes.
- **Blockers:** No code blocker. Live Preview execution must wait for completed Week 0 games and the stated approval boundary.
- **Next:** After Week 0 is frozen and closed, run `make prepare-week YEAR=2026 WEEK=1 AS_OF=<timestamp> ENV=preview`, then `make readiness` and private Preview publish using its emitted Gold ref.

## Context and Decisions

- The V4 historical baseline is preserved; `prepare-week` does not rerun model selection.
- Post-Week-0 `publish-week` requires an explicit `--prepared-gold-ref-uri`, which prevents implicit fallback to preseason Gold.
- Cancellation handling is explicit and audit-preserving: `GAME_ID:reason` is recorded in the v2 scored manifest and produces no grade.
- No production pipeline run, Vercel mode switch, or publication scope expansion was performed.

## Work Completed

- Added canonical/provider-week selection and exact game-ID response filtering to plays and game-stats ingestion.
- Added immutable outcome ref loading, checksummed reads, full frozen-slate finality checks, cancellation waivers, and `scored_run_v2` outcome lineage.
- Made `close-week` build its own run-scoped outcomes ref and require `AS_OF`.
- Added `prepare-week`, its Make target, run-scoped refs, source capture/Silver/reconciliation/combined-history/Gold steps, and target-week validation.
- Made later-week publication require and pin the prepared immutable Gold ref.
- Added prediction-mode edge explanation, CI publication-test target, runbook/roadmap/quickstart updates, and focused state-machine/ingestion/scoring tests.

## Files Modified

- `src/cks_picks_cfb/data/week_policy.py`, `plays.py`, `game_stats.py` — canonical-week resolution and exact source filtering.
- `src/cks_picks_cfb/ops/__main__.py` — immutable close path and `prepare-week` orchestration.
- `scripts/pipeline/score_weekly_bets.py`, `check_prepared_week.py`, `snapshot_week_inputs.py`, `combine_history_versions.py` — outcome-bound scoring, readiness, pinned Gold snapshots, and explicit current-season ref combination.
- `Makefile`, web/CI/docs/test files — operating interface, UI copy, CI coverage, documentation, and validation.

## Validation

- [x] `uv run pytest -q` — 367 passed, 2 skipped (known CatBoost/scikit-learn deprecation warnings remain).
- [x] `uv run ruff check .`
- [x] `make contracts-check`
- [x] `make web-lint`
- [x] `make web-typecheck`
- [x] `npm run test:publication` (from `web/`)
- [x] `make web-build`
- [x] `uv run mkdocs build` (existing documentation nav/link warnings; build succeeds)
- [x] `git diff --check`

## Amendments and Blockers

- The planned live Preview acceptance is deliberately deferred until Week 0 is complete. Strict MkDocs still reports pre-existing link/nav warnings, so it was not made a new hard failure.

## Handoff Notes

- **Resume at:** Close the approved Week 0 frozen run with an explicit cutoff; use a cancellation waiver only for a truly canceled frozen game.
- **Watch out for:** Retain the `prepare-week` run ID and pass `artifacts/<env>/pipeline-runs/<run-id>/point_in_time_matchups_ref.json` to later-week `publish-week` through `PREPARED_GOLD_REF_URI`.

**tags:** ["week0", "week1", "pipeline", "scoring", "gold", "operations"]
