# Session: 2025 Retrospective Model Context Implementation

## TL;DR

- **Worked On:** Implemented the approved diagnostic-only 2025 V4 context
  calculation, serving projection, and prediction-mode web panel.
- **Outcome:** The immutable Preview artifact, Preview serving rows, production
  serving rows, and public Vercel panel are published and independently
  verified.
- **Plan Contract:** `docs/plans/2026-09-08/2025-retrospective-model-context.md`
- **Approval / Status:** User explicitly authorized implementation; contract is
  `Implemented` after committed-SHA Preview materialization, Preview-first
  database rollout, and live UI verification.
- **Blockers:** None.
- **Next:** Continue normal weekly operations; this retrospective context is
  diagnostic-only and requires no weekly publisher interaction.

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
- Built the immutable Preview R2 artifact at
  `artifacts/research/historical-model-context/840eda828d14d8fe572d53e84eadbccdf54692ae088d75de98f95c922c51805c/runs/2026-09-08T2300Z-v1/`.
  Its dataset ref is `ed45304956b5c8a179839a7c`, content SHA
  `f33e7b43d5606a1cbe17da9c764789bf4b407dc0255b03cd7d5e3191feac5680`.
- Independently reread all 1,522 rows and the 16 aggregate periods from R2.
- Applied append-only migration `0012` to Preview and production, then
  published the same 16 artifact-backed aggregate rows to each database.
- Independently verified Preview and production season/Week 2 parity,
  reconstructed diagnostic provenance, production `current_week` remains
  `(2026, 2, 2026w2-43b25511a100)`, and the live 2026 system record remains
  independently stored as `(18-32 spreads, 19-32 totals)`.
- Verified the public prediction-mode deployment after `094407c` was pushed:
  Week 2 displays full-season spread `379-366-16` (50.9%) and total
  `398-358-5` (52.6%), with matching Week 2 values including total `28-22-0`.
  Week 0 retains the full-season context and renders “No 2025 Week 0
  comparison.” The deployed disclosure labels the references as reconstructed,
  post-season diagnostic context rather than an official pregame record.

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
- [x] Immutable Preview artifact apply and independent verification.
- [x] Preview migration and aggregate publication.
- [x] Production migration and aggregate publication after Preview parity.
- [x] Vercel deployment and live panel verification for Week 0 and Week 2.

## Amendments and Blockers

- No amendment. A repeated web build was blocked by a pre-existing `.next/lock`
  after a prior successful build; no lock file was removed. The subsequent
  deployed-page check succeeded.

## Handoff Notes

- **Resume at:** No active implementation work. The historical context should
  remain isolated from the weekly production publisher.
- **Watch out for:** Do not publish reconstructed context into
  `prediction_grades`, `system_stats`, or any canonical live-record table.

**tags:** ["historical-context", "v4", "diagnostic-only", "neon", "web"]
