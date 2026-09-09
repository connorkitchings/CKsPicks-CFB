# Session: 2025 Retrospective Model Context Implementation

## TL;DR

- **Worked On:** Implemented the approved diagnostic-only 2025 V4 context
  calculation, serving projection, and prediction-mode web panel.
- **Outcome:** The code checkpoint is ready for a user-managed commit. The
  pinned Preview calculation independently reproduced the required 1,522-row
  population and full-season/Week 2 parity without writing R2 or Neon.
- **Plan Contract:** `docs/plans/2026-09-08/2025-retrospective-model-context.md`
- **Approval / Status:** User explicitly authorized implementation; contract
  remains `In Progress` pending committed-SHA Preview materialization and
  Preview-first database/UI rollout.
- **Blockers:** Immutable apply, migration, and publication must use the
  committed code SHA; the user controls the required commit.
- **Next:** Commit this checkpoint, then run Task 4 Preview dry-run/apply,
  migration, aggregate publication, and visual verification.

## Work Completed

- Added `historical_model_context` contracts that pin the 2025 V4 replay,
  locked feature mapping, and reconstructed diagnostic market references.
- Confirmed against Preview R2 that the calculation yields 1,522 rows over 761
  games; full season is spread 379-366-16 and total 398-358-5; Week 2 is
  spread 26-22-2 and total 28-22-0.
- Added immutable builder and diagnostic-only aggregate publisher CLIs.
- Added append-only migration `0012_historical_model_context.sql`, canonical
  SQL/TypeScript schema updates, and read-only web access.
- Added a prediction-mode-only historical context panel with explicit
  reconstructed-line disclosure and Week 0 unavailable behavior.
- Added focused unit coverage for configuration guarding and W-L-P aggregation.

## Files Modified

- `src/cks_picks_cfb/models/historical_model_context.py`
- `scripts/pipeline/build_historical_model_context.py`
- `scripts/pipeline/publish_historical_model_context.py`
- `conf/weekly_bets/v4_2025_retrospective_context.yaml`
- `contracts/migrations/0012_historical_model_context.sql`
- `contracts/schema.sql`, `contracts/schema.ts`, `web/src/lib/schema.ts`
- `web/src/lib/queries.ts`, `web/src/app/page.tsx`,
  `web/src/components/HistoricalModelContext.tsx`, and UI fixtures
- `tests/test_historical_model_context.py`

## Validation

- [x] Preview R2 read-only calculation: exact 2025 population and expected aggregates.
- [x] Focused tests: `2 passed`.
- [x] Ruff format/check for changed Python files.
- [x] `make contracts-check`.
- [x] Web typecheck.
- [x] Web production build completed successfully once.
- [x] `git diff --check`.
- [ ] Immutable Preview artifact apply and independent verification (requires committed code SHA).
- [ ] Preview migration/publish and UI verification (requires committed checkpoint).
- [ ] Production rollout (requires Preview parity and explicit next-stage execution).

## Amendments and Blockers

- No amendment. A repeated web build was blocked by a pre-existing `.next/lock`
  after a prior successful build; no lock file was removed.

## Handoff Notes

- **Resume at:** Commit the implementation checkpoint, then materialize the
  immutable Preview artifact under the contract's run-stamped prefix.
- **Watch out for:** Do not publish reconstructed context into
  `prediction_grades`, `system_stats`, or any canonical live-record table.

**tags:** ["historical-context", "v4", "diagnostic-only", "neon", "web"]
