# Session: Ratings Lifecycle Integration

## TL;DR

- **Worked On:** Implemented the approved ratings lifecycle contract.
- **Outcome:** `prepare-week` now fails closed on stale or incomplete projected ratings; migration 0017 requires V5 run provenance while preserving V4 rollback publishing; runbooks describe the weekly sequence.
- **Plan Contract:** `docs/plans/2026-09-27/04-ratings-lifecycle-integration.md` (Implemented).
- **Approval / Status:** User explicitly authorized the exact path and revised V5-only implementation plan in the implementation handoff.
- **Blockers:** None for code implementation. Migration 0017 was authored but not applied to Preview or production.
- **Next:** Review and commit the scoped changes. Apply migration 0017 to each live branch only in its normal migration window; the read-only pre-audit found no V5 rows lacking a rating SHA.

## Context and Decisions

- The original Draft's fixed timestamp CHECK would have affected V4 rollback publishing. The approved replacement constrains only `model_id LIKE 'v5-%'` and retains the existing 64-character SHA check.
- `prepare-week` already passes an explicit environment to its readiness child, and the ops parent resolves the database URL through environment variables. The gate uses that path so credentials never enter step definitions or command arguments.
- Preview's current rating rows use each team's last-played week, which varies within a single generation. The gate selects the latest cutoff and manifest among rows with `week < target week` and maps schedule aliases through the existing `canonical_team` contract.
- Database errors fail closed. The gate has no offline bypass. The V5 weekly operator's separate `prepare` component remains governed by its verified forecast lineage and exact release authorization.

## Work Completed

1. Added a read-only, single-generation currency and team-coverage check to `check_prepared_week.py`; the ready summary includes the cutoff and manifest SHA.
2. Added append-only migration 0017, updated canonical SQL/TypeScript schemas and the web schema copy, and tested fresh-schema and upgrade behavior against disposable PostgreSQL.
3. Updated weekly pipeline and production runbooks with the ratings refresh checkpoint and timeline labels.
4. Added focused gate tests and an ops wiring assertion.

## Files Modified

- `scripts/pipeline/check_prepared_week.py` and `tests/test_ratings_currency_gate.py` — rating gate and cases.
- `contracts/migrations/0017_require_rating_manifest.sql`, `contracts/schema.sql`, `contracts/schema.ts`, `web/src/lib/schema.ts`, and `tests/test_migration_integration.py` — V5 provenance contract and database tests.
- `tests/test_ops_state_machine.py` — environment wiring assertion.
- `docs/ops/weekly_pipeline.md`, `docs/ops/production_runbook.md`, `docs/plans/2026-09-27/04-ratings-lifecycle-integration.md`, and `docs/plans/index.md` — operator guidance and contract state.

## Validation

- [x] Scoped tests against disposable PostgreSQL: **35 passed**.
- [x] Read-only Preview Week 5 readiness check: `ready`, 215 completed games, 56 target games, cutoff `2026-09-27T14:15:00Z`, rating manifest `75e016e1b9876c940cdc98d70aebcc01472b9b1fd160ca6e8e1358d87208cae0`.
- [x] Read-only V5 provenance audits: Preview 21 rows / 0 missing SHA; production 16 rows / 0 missing SHA.
- [x] Scoped Ruff check and format check; `make contracts-check`; `uv run mkdocs build --quiet`; web TypeScript typecheck; `git diff --check`.
- [x] No live migration, publication, or production activation performed.

## Amendments and Blockers

The reviewed code follow-up records two mechanical data-shape discoveries: current snapshot weeks vary by team, and Silver schedule aliases require canonical mapping. Both preserve the approved generation and coverage checks. No remaining implementation blocker.

## Handoff Notes

- **Resume at:** User review and manual commit. Apply migration 0017 through the usual branch-specific migration workflow after the same read-only V5 null-SHA audit.
- **Watch out for:** The new gate applies only to `prepare-week`; the V5 weekly operator has a separate `prepare` component. This change does not authorize prospective Week 5 production activation.
- **Suggested commit message:** `feat: gate weekly preparation on projected ratings and require V5 provenance`

**tags:** ["ops", "ratings", "migration", "pipeline"]
