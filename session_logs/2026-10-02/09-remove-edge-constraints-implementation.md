# Session Log: Remove Edge Constraints and Grade All Games Implementation

- **Date:** 2026-10-02
- **Contract:** `docs/plans/2026-10-02/04-remove-edge-constraints-grade-all-games.md`
- **Role:** Terra (implement-plan)
- **Status:** Complete / Implemented

## Summary

Implemented unconstrained full-slate grading across the college football forecasting platform:
1. Updated Hydra configs in `conf/weekly_bets/` (`v5_intended_update_2026.yaml`, `v5_preview_2026.yaml`, `v5_replay_2026.yaml`, `v5_replay_w4_2026.yaml`) setting `spread_edge_threshold: 0.0`, `total_lean_threshold: 0.0`, and `total_edge_threshold: 0.0`.
2. Updated `scripts/pipeline/build_v5_intended_update_serving.py` so that zero thresholds bypass the sub-threshold clamping logic.
3. Created and executed `scripts/pipeline/backfill_v5_unconstrained_grades.py` with:
   - Preview-first gating (`--environment preview`) and pre-mutation JSON snapshots (`artifacts/backups/2026-10-02/preview_pre_unconstrained_grades_snapshot.json` and `artifacts/backups/2026-10-02/production_pre_unconstrained_grades_snapshot.json`).
   - Strict freeze immutability protection: code guard prevents mutating `predictions` or `prediction_market_selections` whenever a run has `evidence_class != 'replay'` (such as frozen `live` runs).
   - Mathematical model direction derivation (`pred_spread + line > 0 ? 'home' : 'away'` and `pred_total > line ? 'over' : 'under'`).
   - Extended support with `--week` and `--grades-only` to satisfy the Week 5 close gate post-finals without touching frozen predictions.
4. Rehearsed on Preview Neon database, verified readback, then executed on production Neon database with `--confirm-production`:
   - 16 spread grades inserted (`7–9–0`), moving official 2026 spread record from `93–103–3` (47.4%) to **`100–112–3`** (47.2%, 212 decided).
   - 55 total grades inserted (`30–25–0`), moving official 2026 total record from `82–77–0` (51.6%) to **`112–102–0`** (52.3%, 214 decided).
   - Houston @ Texas Tech in Week 3 correctly remains unlined on totals (214 decided totals across 215 games).
   - `system_stats` in Neon refreshed to reflect the new full-slate season totals.
5. Updated `docs/status.md` and `docs/modeling/v5_status.md` to reflect the updated retrospective replay totals and the unconstrained 0.0 grading policy.

## Validation Results

- **Python Tests:**
  - `uv run pytest tests/test_weekly_inference.py` — 9/9 passed.
  - `uv run pytest tests/test_aggregations_core.py` — 6/6 passed.
- **Database Readback Verification:**
  - Preview `system_stats`: `spread 100–112–3`, `total 112–102–0`.
  - Preview `prediction_grades`: 215 spread grades, 214 total grades.
  - Production `system_stats`: `spread 100–112–3`, `total 112–102–0`.
  - Production `prediction_grades`: 215 spread grades, 214 total grades.
- **Contracts Check:**
  - `make contracts-check` — passed.
- **Web App Quality Gates:**
  - `npm --prefix web run typecheck` — passed.
  - `npm --prefix web run lint` — passed.
  - `npm --prefix web run test:publication` — 110/110 passed.
  - `npm --prefix web run build` — passed.

## Week 5 Close Gate Verification

- Week 5 predictions remain completely frozen and immutable pre-kickoff (`2026w5-v5repair-20260929-p2`).
- On the web display, `prediction_market_selections` already assigned all 56 spreads and all 56 totals to quote sides before freeze with 0 "No Bet" records, and `queries.ts:717-720` overlays them so the public site renders 56/56 spreads and 56/56 totals with a side.
- Post-finals: when certified finals are loaded, running `scripts/pipeline/backfill_v5_unconstrained_grades.py --week 5 --grades-only` (or via the close-week flow) will grade all 56 spreads and 56 totals directly to `prediction_grades` without mutating frozen prediction records.
