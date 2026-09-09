# Session: Week 1 Scoring Lean Fallback & Week 2 Production Publish

## TL;DR
- **Worked On:** Fixed Week 1 total bet grading omissions, upgraded scoring pipelines to grade all matchups by model lean, resolved pipeline bugs in Silver builders / ops orchestration / DB publishing, and executed `prepare-week`, `readiness`, and `publish-week` for 2026 Week 2.
- **Outcome:** Week 2 is live in production on Neon and Vercel (`2026w2-43b25511a100`, 49 FBS games with spreads/totals). Week 1 totals scoring was completed (100% graded, 86/86 total bets for Weeks 0-1).
- **Plan Contract:** N/A (fast path weekly ops cadence + scoring bugfix)
- **Approval / Status:** Completed and verified against live production.
- **Blockers:** None.
- **Next:** Monitor Week 2 kickoff (first games Friday, Sept 11 / Saturday, Sept 12) and freeze active run prior to kickoff.

## Context and Decisions
- **Model Leans vs Bet Grading:** Previously, games where model edge was below the betting threshold were marked `"No Bet"` and omitted from `prediction_grades`. Per user direction, all model leans are now evaluated and graded so full model performance is tracked.
- **Silver Outcomes & Plays Normalization:** Non-FBS games (against FCS opponents) lack mapping metadata in `games.parquet`. We updated `normalize_plays` to constrain to FBS games prior to casting/validation. In `normalize_game_outcomes`, dropped raw `week` before calling `_constrain_to_games` to prevent provider vs canonical week conflicts.
- **Foreign Key Ordering:** In `scripts/pipeline/publish_to_db.py`, `market_quotes` references `games(game_id)`. We moved the `games` upsert before `market_quotes` insertion to avoid foreign key violations.

## Work Completed
1. **Week 1 Scoring:**
   - Identified un-graded total bets for New Mexico vs Central Michigan (Win, +1.00u) and Rutgers vs UMass (Loss, -1.10u).
   - Modified `scripts/pipeline/score_weekly_bets.py` and `scripts/pipeline/score_to_db.py` to fall back to `spread_lean` / `total_lean` when `Spread Bet` / `Total Bet` is `"No Bet"`.
   - Updated `prediction_grades` and refreshed `system_stats` in Neon DB.
2. **Week 2 Pipeline Run:**
   - Executed `make prepare-week YEAR=2026 WEEK=2 AS_OF=2026-09-08T17:50:00Z ENV=preview`.
   - Passed preflight audit and readiness check: `make readiness YEAR=2026 WEEK=2 AS_OF=2026-09-08T17:50:00Z ENV=preview CONFIG=conf/weekly_bets/v4_2026.yaml PREPARED_GOLD_REF_URI=artifacts/preview/pipeline-runs/3eb4c566ac6a4700ac176e42d1df12a5/point_in_time_matchups_ref.json`.
   - Published Week 2 to production: `make publish-week YEAR=2026 WEEK=2 AS_OF=2026-09-08T17:50:00Z ENV=production CONFIG=conf/weekly_bets/v4_2026.yaml PREPARED_GOLD_REF_URI=artifacts/preview/pipeline-runs/3eb4c566ac6a4700ac176e42d1df12a5/point_in_time_matchups_ref.json`.
   - Verified live site at `https://c-ks-picks-cfb.vercel.app/` and `/api/health`.

## Files Modified
- `scripts/pipeline/publish_to_db.py` - Reordered upserts so `games` precedes `market_quotes`.
- `scripts/pipeline/score_to_db.py` - Fall back to lean column when bet is "No Bet".
- `scripts/pipeline/score_weekly_bets.py` - Fall back to lean column when bet is "No Bet".
- `src/cks_picks_cfb/data/silver/builders.py` - Constrain non-FBS plays before casting; strip unneeded raw week in outcomes.
- `src/cks_picks_cfb/ops/__main__.py` - Forward environment and unique ingestion keys; pass `games_ref_uri` to `build_outcomes`.

## Validation
- [x] Scoped lint: `uv run ruff check scripts/pipeline/score_weekly_bets.py scripts/pipeline/score_to_db.py scripts/pipeline/publish_to_db.py src/cks_picks_cfb/data/silver/builders.py src/cks_picks_cfb/ops/__main__.py`
- [x] Scoped tests: `uv run pytest tests/test_silver_reconciliation.py`
- [x] Live site health check: `curl -sS https://c-ks-picks-cfb.vercel.app/api/health`
- [x] `git diff --check`

## Handoff Notes
- **Resume at:** Run `make freeze-week YEAR=2026 WEEK=2 ENV=production` before Friday kickoff.
- **Watch out for:** Keep `.opencode/` untracked / ignored.
