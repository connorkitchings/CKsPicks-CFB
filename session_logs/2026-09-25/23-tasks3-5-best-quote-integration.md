# Session: Tasks 3–5 Best-Quote Line Selection Pipeline & Web Integration

## TL;DR
- **Worked On:** Tasks 3, 4, and 5 of `docs/plans/2026-09-25/03-permanent-best-quote-line-selection.md`:
  - Created read-only audit CLI `scripts/pipeline/audit_market_quote_coverage.py`.
  - Updated `market_grading.py` to allow CFBD unpriced quotes to default to standard -110.0 American odds (`require_price=False` default) while supporting explicit prices (`require_price=True`).
  - Integrated `select_best_quote()` into `weekly.py`, `v5_serving.py`, `generate_weekly_bets.py`, `generate_v5_weekly_bets.py`, and `generate_v5_replay_weekly_bets.py`, writing selection lineage into prediction artifacts and manifest validation blocks.
  - Updated `publish_to_db.py` to insert verified selections into `prediction_market_selections` and reject point mismatches.
  - Updated `score_to_db.py` and `backfill_replay_grades.py` to link grades to `market_quote_id`, price, and `model_side_best_quote_v1`.
  - Updated `web/src/lib/queries.ts` to read selected line/side/edge from `prediction_market_selections` via COALESCE, preserving fallback for legacy runs, and updated `web/src/app/page.tsx` footnote copy.
- **Outcome:** The entire best-quote line selection pipeline (selection, artifact generation, database publication, grading, and web serving) is implemented and verified.
- **Plan Contract:** `docs/plans/2026-09-25/03-permanent-best-quote-line-selection.md`
- **Approval / Status:** In Progress (Amendment 2 recorded; Tasks 1–5 and 7 complete; Task 6 operational runs pending).
- **Blockers:** None.
- **Next:** User executes git commit; proceed to Task 6 (Preview rehearsal with migration 0016 applied to Preview Neon branch, followed by historical replacement runs).

## Context and Decisions
- **CFBD Odds Ingestion:** CFBD only captures spread/total points without bookmaker moneyline/juice prices (`NULL` odds columns). Defaulting unpriced quotes to standard `-110.0` American odds ensures all 2,526 historical quotes are eligible for selection, preventing false rejections while still supporting explicit prices from The Odds API.
- **Immutability & Safety:** Existing historical runs and grades remain untouched. All new runs record `best_quote_selection_policy: "model_side_best_quote_v1"`.

## Work Completed
- Built `scripts/pipeline/audit_market_quote_coverage.py`.
- Updated `src/cks_picks_cfb/models/market_grading.py` and `tests/test_market_grading.py` (45 unit tests).
- Integrated quote selection in `src/cks_picks_cfb/inference/weekly.py`, `src/cks_picks_cfb/inference/v5_serving.py`, `scripts/pipeline/generate_weekly_bets.py`, `scripts/pipeline/generate_v5_weekly_bets.py`, `scripts/pipeline/generate_v5_replay_weekly_bets.py`.
- Added unit tests in `tests/test_weekly_inference.py`.
- Integrated target selection inserts and validation in `scripts/pipeline/publish_to_db.py`.
- Integrated `market_quote_id` and pricing in `scripts/pipeline/score_to_db.py` and `scripts/pipeline/backfill_replay_grades.py`.
- Updated web queries in `web/src/lib/queries.ts` and footnote in `web/src/app/page.tsx`.

## Files Modified
- `scripts/pipeline/audit_market_quote_coverage.py` - Created read-only audit CLI tool
- `src/cks_picks_cfb/models/market_grading.py` - Updated `_side_price()` and `select_best_quote()` with `require_price` option
- `tests/test_market_grading.py` - Added tests for `require_price` and quote selection
- `src/cks_picks_cfb/inference/weekly.py` - Added best-quote selection and edge calculation against selected quote
- `src/cks_picks_cfb/inference/v5_serving.py` - Forwarded `market_quotes` to inference
- `scripts/pipeline/generate_weekly_bets.py` - Read and passed `market_quotes` ref
- `scripts/pipeline/generate_v5_weekly_bets.py` - Read and passed `market_quotes` ref and manifest validation
- `scripts/pipeline/generate_v5_replay_weekly_bets.py` - Supported `market_quotes` refs and manifest validation
- `scripts/pipeline/publish_to_db.py` - Inserted selections into `prediction_market_selections` with point verification
- `scripts/pipeline/score_to_db.py` - Linked grades to `market_quote_id` and price
- `scripts/pipeline/backfill_replay_grades.py` - Supported `market_quote_id` in replay backfills
- `web/src/lib/queries.ts` - Read from `prediction_market_selections` via COALESCE
- `web/src/app/page.tsx` - Updated footnote copy
- `docs/plans/2026-09-25/03-permanent-best-quote-line-selection.md` - Recorded Amendment 2 and updated DoD

## Validation
- [x] Scoped tests: `PYTHONPATH=src uv run pytest tests/test_market_grading.py tests/test_weekly_inference.py` (51 passed)
- [x] Full Python suite: `PYTHONPATH=src uv run pytest -q` (1,439 passed, 2 skipped)
- [x] Web suite: `npm run lint && npm run typecheck && npm run test:publication && npm run build` (all passed, 0 errors)
- [x] Contracts sync: `make contracts-check` (passed)
- [x] Ruff formatting and check: `uv run ruff check .` and `uv run ruff format --check .` (passed on all changed files)
- [x] `git diff --check` (passed, 0 whitespace errors)

## Handoff Notes
- **Resume at:** Propose commit to user; then execute Task 6 (run Preview database migration 0016, generate test replay run with best-quote selection on Preview).
- **Watch out for:** Never mutate existing scored production runs or grades.
