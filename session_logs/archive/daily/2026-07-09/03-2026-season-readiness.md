# Session: 2026 Season Readiness

## TL;DR
- **Worked On:** Implemented the 2026 season readiness plan for weekly operations, cold-start predictions, and cloud-backed scoring.
- **Completed:** Added separate pregame/postgame Make targets, fixed scoring to read final scores from configured storage/R2, added prior-season cold-start prediction seeding, suppressed high-confidence flags for early-season ineligible games, and refreshed the 2026 runbook.
- **Blockers:** No code blockers found. 2026 data is not fully available yet from CFBD/providers: rosters, coaches, recruiting, rankings, external ratings, betting lines, plays, and game stats remain availability-dependent.
- **Next:** Commit this work, then run real R2/Neon operations when ready. User is comfortable using R2/Neon now, but Week 1 data readiness still depends on provider publication.

## Changes Made
- **Makefile:** Added `publish-week` for pregame publishing and `close-week` for postgame scoring/stat refresh. `weekly` now aliases `publish-week`.
- **Prediction pipeline:** Added prior-season `processed/team_week_adj` seeding for early-season/cold-start prediction rows in `src/cks_picks_cfb/features/v2_recency.py`.
- **High-confidence eligibility:** Added `high_confidence_eligible` to generated prediction CSVs and taught `publish_to_db.py` to suppress `high_confidence` when eligibility is false.
- **Scoring pipeline:** Updated `score_weekly_bets.py` to load final scores via `get_storage().read_index("raw/games", ...)` instead of the local-storage shim, and to fail loudly on missing predictions or scores.
- **Config/docs:** Updated `conf/weekly_bets/v2_champion.yaml` as a 2026 display fallback and rewrote `docs/ops/weekly_pipeline.md`; refreshed README and `.codex/QUICKSTART.md`.
- **Tests:** Added `tests/test_score_weekly_bets.py` and extended `tests/test_publish_to_db.py`.

## Testing
- [x] `uv run ruff format .` - 99 files unchanged
- [x] `uv run ruff check .` - all checks passed
- [x] `uv run pytest -q` - 196 passed
- [x] `uv run python contracts/validation.py` - passed earlier this session
- [x] `uv run python scripts/pipeline/preflight.py --year 2026 --week 1` - passed earlier this session against R2 + Neon
- [x] `npm run lint` - passed earlier this session
- [x] `npm run build` - passed earlier this session
- [x] `npm run typecheck` - passed after build regenerated `.next/types`
- [x] 2026 Week 1 probe produced 99 prediction rows with finite spread/total values and `high_confidence_eligible=false`
- [x] Cloud scoring probe succeeded using a temporary 2025 Week 15 prediction CSV and real R2 final scores

## Technical Details
- Week 1 cold-start now uses latest 2025 `processed/team_week_adj` rows when 2026 `processed/team_game` is absent or a team has fewer than 4 current-season games.
- The current model config remains a display fallback, not a validated betting-edge model. It should not be promoted as a new champion without fresh walk-forward validation.
- The exact artifact scoring probe from the plan (`2025 week 15 --from-artifact`) could not run because R2 only has `artifacts/production/predictions/year=2025/CFB_week16_bets.csv`. The script now exits cleanly for missing artifacts.

## Notes for Next Session

**Resume at:**
- Review and commit the readiness changes.

**Context:**
- R2/Neon use is acceptable now.
- 2026 teams, venues, and games are present in R2.
- 2026 rosters, coaches, recruiting, rankings, external ratings, betting lines, plays, and game stats are not fully ready yet.
- `make publish-week YEAR=2026 WEEK=1` will mutate R2/Neon; run when ready to publish a real slate.

**Watch out for:**
- Do not interpret early-season high-confidence counts as a bug; eligibility is intentionally false until both teams have at least 4 current-season games.
- `make close-week` should only be run after CFBD has final scores and completed-game data.
- If a historical scored artifact is needed for backfill, first ensure the corresponding durable prediction artifact exists in R2.

**Next steps:**
1. Commit changes.
2. Re-run `make ingest-season YEAR=2026 ENTITIES=rosters,coaches,recruiting,rankings,games` when CFBD data becomes available.
3. Run `make publish-week YEAR=2026 WEEK=1` after Week 1 lines are available and a real publish is desired.
4. Resume modeling with 2025-inclusive walk-forward validation after ops is stable.

**tags:** ["2026-season", "weekly-pipeline", "r2", "neon", "cold-start", "scoring", "docs"]
