# Session: Monday kickoff-time refresh implementation

## TL;DR

- **Worked On:** The contract for refreshing "Time TBD" kickoff times on the Monday market refresh, written and implemented in one session, plus an owner-approved amendment so game metadata can be corrected in any week.
- **Outcome:** The Monday `market-refresh` run now re-fetches the CFBD schedule when the active release has placeholder (midnight Eastern) games whose real times are announced, swaps the `schedule` and `venue_games` pins together, and releases a new Week N release whose only schedule difference is metadata. Added, cancelled or moved games (or a changed `week`, team or `neutral_site`) stop the run naming game IDs. Kickoff corrections are allowed in any week and re-check grading eligibility and pre-week cutoffs. Parity allows `start_date` and venue display columns to differ only when the schedule pin changed. The completed-week stop gate has an opt-in metadata allowance used only by the Monday refresh.
- **Plan Contract:** [`docs/plans/2026-11-12/06-monday-kickoff-time-refresh.md`](../../docs/plans/2026-11-12/06-monday-kickoff-time-refresh.md) (amendment 2026-11-13)
- **Approval / Status:** Owner approved the plan 2026-11-12 and the amendment and stop-gate option B 2026-11-13. Contract stays `In Progress`.
- **Blockers:** The full controller path has not been rehearsed (parity, `season_verification_v2`, Odds quote matching). It could not run on Week 11 because the first kickoff had passed.
- **Next:** After Sunday's close, owner decides whether to push `dev` so the full controller can be rehearsed on Preview with `skip_production` on Monday 2026-11-16; otherwise 2026-11-23. The first Production use is a manual workflow run.

**tags:** ["ops", "weekly-automation", "schedule", "kickoff-time"]

## Context and Decisions

- Partial Preview rehearsal (owner-approved): `refresh-schedule` for Week 11 against `revision_manifest_w11_v2.json`, one CFBD request, completed weeks 0..9 matched. Week 11 placeholders went from 14 to 0, 44 games across later weeks got real times, game set unchanged. A new Silver `games` version is registered on Preview. Nothing released, nothing touched in Production.
- Owner decisions: do not push to `dev` before a reviewed Preview result (Monday cron would run the code); metadata fields split by effect (display-only, kickoff re-checked, model-relevant still a stop); stop gate option B (Monday refresh only).
- The worktree was first created from `main` and reset to `dev`.
- A permission denial blocked reading the Production credential for a local `plan-only` run; the owner ran it. Rehearsal commands used a Preview-only runner and redirected pushes to a throwaway local repository.

## Files Modified

- `scripts/ops/weekly_automation.py`, `src/cks_picks_cfb/ops/__main__.py`
- `scripts/pipeline/build_market_revision.py`, `scripts/pipeline/check_release_parity.py`, `scripts/pipeline/verify_completed_week_stability.py`
- `tests/test_weekly_automation.py`, `tests/test_build_market_revision.py`, `tests/test_check_release_parity.py`, `tests/test_incremental_close_week.py`, `tests/test_ops_state_machine.py`, `tests/test_kickoff_placeholder.py` (new)
- `docs/ops/weekly_runbook.md`, `docs/status.md`, `docs/plans/index.md`, `docs/plans/2026-11-12/06-monday-kickoff-time-refresh.md` (new), `session_logs/2026-10-25/01-final-site-review.md` (correction)

## Validation

- Focused tests (219 across the affected files) pass; `ruff check`, `ruff format --check`, `git diff --check` and `mkdocs build --strict` pass; `make check` passed on the full change before the final stop-gate edit and again in the worker's final run.
- Known limits: the eligibility check uses the previous manifest's retained quotes and omits the retrospective CFBD fallback lines (parity still catches a moved grade); `refresh-schedule` has no direct test beyond controller and argv tests.
