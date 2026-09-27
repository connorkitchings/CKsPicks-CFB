# Session: Ratings Lifecycle Integration Planning

## TL;DR

- **Worked On:** Investigated the ratings lifecycle gap in the weekly operating pipeline and formulated a Sol implementation contract.
- **Outcome:** Created implementation contract `docs/plans/2026-09-27/04-ratings-lifecycle-integration.md` (Draft) and updated active contracts index.
- **Plan Contract:** `docs/plans/2026-09-27/04-ratings-lifecycle-integration.md` (Draft).
- **Approval / Status:** Draft — awaiting user authorization for Terra implementation.
- **Blockers:** None.
- **Next:** User reviews and approves the plan; fresh Terra session executes implementation.

## Context and Decisions

- **Problem:** The week lifecycle (`close` → `prepare` → `publish` → `freeze` → `score`) manages games, lines, predictions, and grades. The ratings lifecycle (`repair` → `measurements` → `rating replay` → `projection`) is separate and manually orchestrated. `prepare-week` had zero checks ensuring team ratings exist or cover completed games prior to the target week's `as_of`, creating risk of predictions generated from stale ratings.
- **Decisions:**
  1. Scope: Enforce the contract between ratings and weekly pipeline; do not automate the research steps. Label ratings by timeline (e.g. `preseason`, `post-week 0`, `post-week 1`, `post-week 2`).
  2. Failure Mode: Hard-fail `prepare-week` (`check_prepared_week.py`) if ratings do not cover all completed games prior to `as_of`.
  3. Provenance Binding: Require 64-char `rating_manifest_sha256` on new `prediction_runs` via append-only migration 0017 with a CHECK constraint.
  4. Projection: Standalone `project-v5-ratings` command formalized in runbook and documentation between `close-week` and `prepare-week`.

## Work Completed

1. Initialized session via `start-session` protocol, reviewed recent session logs and repository operational state.
2. Analyzed `src/cks_picks_cfb/ops/__main__.py`, `scripts/pipeline/check_prepared_week.py`, and `scripts/pipeline/publish_v5_ratings.py`.
3. Drafted comprehensive implementation plan at `docs/plans/2026-09-27/04-ratings-lifecycle-integration.md` following the Sol-to-Terra contract template.
4. Added the plan to `docs/plans/index.md` active contracts table.

## Files Modified

- `docs/plans/2026-09-27/04-ratings-lifecycle-integration.md` — new implementation contract.
- `docs/plans/index.md` — registered contract in active contracts index.
- `session_logs/2026-09-27/09-ratings-lifecycle-integration-planning.md` — this session log.

## Validation

- [x] Plan conforms to `.agent/skills/plan-session/assets/implementation-contract-template.md`.
- [x] `git diff --check` (clean).
- [x] Documentation build / syntax verified.

## Amendments and Blockers

- None.

## Handoff Notes

- **Resume at:** User review and authorization of `docs/plans/2026-09-27/04-ratings-lifecycle-integration.md`.
- **Watch out for:** Terra execution will create migration 0017 (`contracts/migrations/0017_require_rating_manifest.sql`) and require synchronizing `contracts/` and `web/src/lib/` (`make contracts-check`).

**tags:** ["ops", "planning", "ratings", "lifecycle", "state-machine"]
