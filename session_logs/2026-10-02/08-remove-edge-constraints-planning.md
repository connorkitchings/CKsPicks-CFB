# Session: Remove Edge Constraints Planning

## TL;DR
- **Worked On:** Investigated performance impact of removing all edge constraints (setting spread and total thresholds to 0.0) across all 215 games in Weeks 0–4; resolved user review items (Week 5 frozen run audit, Preview-first safety, pre-mutation snapshots, exact backfill script); finalized durable contract `docs/plans/2026-10-02/04-remove-edge-constraints-grade-all-games.md`.
- **Outcome:** Contract is Approved.
  - **Week 5 Audit & Close Gate:** `predictions` had 7 null spreads and 8 null totals from generation filtering, BUT `prediction_market_selections` carries all 56 spreads and 56 totals (0 "No Bet"). The web query (`getGamesForWeek`) overlays market selections, so Week 5 **already displays 56/56 spreads and 56/56 totals with a side**. The frozen run `2026w5-v5repair-20260929-p2` remains 100% immutable; close-week grading gate added to DoD to ensure all 56 spreads and 56 totals are graded post-finals without mutating the frozen prediction records.
  - **Production Safety:** Added Preview-first rehearsal requirement, row-level pre-mutation JSON snapshots, and named exact script `scripts/pipeline/backfill_v5_unconstrained_grades.py`.
  - **Re-scoring Numbers:** 16 spread grades (`7–9–0`) and 55 total grades (`30–25–0`) will be added to Weeks 0–4, moving official records to `100–112–3` (47.2%) and `112–102–0` (52.3%).
- **Plan Contract:** `docs/plans/2026-10-02/04-remove-edge-constraints-grade-all-games.md` (`Approved`)
- **Blockers:** None.
- **Next:** Execute contract with fresh Terra session or implementation step.

## Context and Findings
- Evaluated all 215 games from Weeks 0–4 against Neon `site_week_selections`, `predictions`, `prediction_market_selections`, and `game_results`.
- Read-only queries executed:
  ```sql
  SELECT count(*) FILTER (WHERE spread_lean IS NULL) AS null_spread,
         count(*) FILTER (WHERE total_lean IS NULL) AS null_total
  FROM predictions WHERE run_id = '2026w5-v5repair-20260929-p2';
  -- 7 null spreads, 8 null totals
  
  SELECT target, side, count(*) FROM prediction_market_selections
  WHERE run_id = '2026w5-v5repair-20260929-p2' GROUP BY target, side;
  -- spread: away 13, home 43 (56 total, 0 No Bet)
  -- total: over 42, under 14 (56 total, 0 No Bet)
  ```
- Because `queries.ts` overlays `prediction_market_selections` on `predictions`, there are 0 null leans displayed on `/` for Week 5.
- The 4-task execution plan covers:
  1. Setting thresholds to 0.0 in `conf/weekly_bets/` and pipeline serving builders.
  2. Implementing `scripts/pipeline/backfill_v5_unconstrained_grades.py` with `--dry-run`, `--snapshot-dir`, and `--environment`.
  3. Rehearsing on Preview first, taking a pre-mutation production dump, then executing production backfill and stats refresh.
  4. Updating `docs/status.md`, `docs/modeling/v5_status.md`, and web test assertions.

## Files Modified
- `docs/plans/2026-10-02/04-remove-edge-constraints-grade-all-games.md` - Approved contract with Week 5 audit and safety amendments
- `docs/plans/index.md` - Registered contract
- `session_logs/2026-10-02/08-remove-edge-constraints-planning.md` - This session log

## Validation
- [x] Week 5 frozen run queried read-only on Neon: zero effective nulls on web display.
- [x] Pre-mutation snapshot and Preview rehearsal gates embedded in Task 3.
- [x] Status line set to Approved.
- [x] Contract follows implementation-contract-template structure.

**tags:** ["planning", "edge-thresholds", "grading", "all-games", "v5", "week5-audit", "contract"]
