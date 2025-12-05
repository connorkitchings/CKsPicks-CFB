# Production Directory

This directory contains all Phase 4 production artifacts.

## Structure

- `predictions/` - Weekly betting recommendations
- `scored/` - Post-game results
- `monitoring/` - Dashboard and performance tracking data

## Weekly Predictions

**Path**: `predictions/<YEAR>/week<WW>_bets.csv`

Example: `predictions/2025/week01_bets.csv`

**Contents**: Game predictions, recommended bets, edges, confidence

## Scored Results

**Path**: `scored/<YEAR>/week<WW>_scored.csv`

Example: `scored/2025/week01_scored.csv`

**Contents**: Actual outcomes, wins/losses, units won/lost

## Monitoring

- `performance_log.csv` - Rolling performance metrics
- `dashboard_data.json` - Streamlit dashboard cache
- `alerts/` - Alert history (Yellow/Orange/Red)

## Workflow

1. **Generate** (`weekly_pipeline.md` Step 3):

   ```bash
   uv run python scripts/prediction/generate_weekly_bets.py --week 10
   # → predictions/2025/week10_bets.csv
   ```

2. **Score** (Step 5):

   ```bash
   uv run python scripts/scoring/score_weekly_bets.py --week 10
   # → scored/2025/week10_scored.csv
   ```

3. **Monitor** (Step 6):
   ```bash
   streamlit run dashboard/monitoring.py
   # Reads: monitoring/performance_log.csv
   ```

## .gitignore

- **Include**: predictions/ (reproducibility)
- **Exclude**: scored/, monitoring/\*.csv (generated)

---

**Related**: [Weekly Pipeline](../docs/ops/weekly_pipeline.md) | [Monitoring](../docs/ops/monitoring.md)
