# Weekly Pipeline (Manual Workflow)

**Status**: V2-aligned as of 2025-12-05  
**Workflow Type**: Manual (user-driven, not automated)

This document defines the manual process for generating weekly betting recommendations using the V2 Champion Model.

---

## Overview

**All steps are performed manually by the user.** There is no automated pipeline. The V2 workflow emphasizes:

- Manual review at every stage
- User judgment for all decisions
- Dashboard as decision support (not automation trigger)

---

## Prerequisites

Before running the weekly pipeline:

1. ✅ **CFB_MODEL_DATA_ROOT** environment variable is set
2. ✅ **Champion Model** has been selected and registered in MLflow (Phase 4)
3. ✅ **External drive** is mounted and accessible
4. ✅ **Raw data** has been ingested for the current week

---

## The Weekly Process

### Step 1: Update Raw Data

**When**: Tuesday after games are final (usually ~2 days after weekend)

**Action**: Ingest latest games, plays, and betting lines

```bash
# Ingest raw data for current season
uv run python scripts/ingestion/ingest_games.py --year 2025
uv run python scripts/ingestion/ingest_plays.py --year 2025
uv run python scripts/ingestion/ingest_betting_lines.py --year 2025
```

**Verify**: Check that new games appear in `data/raw/games/year=2025/`

---

### Step 2: Run Aggregation Pipeline

**When**: After raw data is updated

**Action**: Generate processed features (byplay, drives, team_game, team_season)

```bash
# Run pipeline for 2025
uv run python scripts/pipeline/run_pipeline_generic.py --year 2025
```

**Verify**: Check `data/processed/team_season/year=2025/` has updated files

**Data Quality** (Week 3+ after validation framework is built):

```bash
# Run validation checks
uv run python scripts/validation/validate_aggregation.py --year 2025
```

---

### Step 3: Generate Weekly Predictions

**When**: After aggregation is complete, before games start

**Action**: Load Champion Model and generate predictions

```bash
# Generate predictions for upcoming week
uv run python scripts/prediction/generate_weekly_bets.py \
    --year 2025 \
    --week <WEEK_NUMBER> \
    --model-path artifacts/models/production/champion_current/
```

**Output**: `data/production/predictions/2025/CFB_week<WW>_bets.csv`

**Manual Review**:

1. Open the CSV in Excel/Numbers
2. Review each prediction:
   - Does the edge make sense?
   - Are any matchups suspicious?
   - Do the recommended bets align with your judgment?
3. Make final bet selections manually

---

### Step 4: Generate System Info & Publish Picks

**When**: After generating predictions

**Action**: Calculate historical system performance for the email report and send the picks email.

1.  **Generate System Stats** (Backtest 2024 & Current YTD):

    ```bash
    uv run python -m scripts.pipeline.generate_system_stats --config conf/weekly_bets/v2_champion.yaml
    ```

    - **Output**: `data/production/system_stats.json`

2.  **Publish Picks Email**:

    ```bash
    uv run python scripts/pipeline/publish_picks.py --year 2025 --week <WEEK_NUMBER>
    # Add --mode test to send to yourself first
    ```

    - **Output**: HTML Email sent to subscribers (or test address)

---

### Step 5: Place Bets

**When**: Before game kickoffs (manual timing)

**Action**: User places bets manually via sportsbook

**Process**:

1. Log into sportsbook
2. For each selected bet from CSV:
   - Find the game
   - Check current line (confirm it's still within acceptable range)
   - Place bet with appropriate unit size
3. Record actual bets placed (if different from recommendations)

---

### Step 6: Score Results

**When**: After games are final (Tuesday/Wednesday)

**Action**: Compare predictions to actual outcomes

```bash
# Score the week's bets
uv run python scripts/scoring/score_weekly_bets.py \
    --predictions data/production/predictions/2025/CFB_week<WW>_bets.csv \
    --output data/production/scored/2025/CFB_week<WW>_bets_scored.csv
```

**Output**: `data/production/scored/2025/CFB_week<WW>_bets_scored.csv`

---

### Step 7: Check Monitoring Dashboard

**When**: After scoring, when convenient

**Action**: Review Champion Model performance

```bash
# Launch dashboard
streamlit run dashboard/monitoring.py
```

**Review**:

1. Check alert status (🟢/🟡/🟠/🔴)
2. Review rolling 4-week ROI
3. Check hit rate trends
4. Note any feature drift warnings

**Decision**: If 🔴 RED for 2+ weeks, consider rollback (see [Rollback SOP](./rollback_sop.md))

---

## V2 Champion Model

**Current Champions** (as of 2025-12-08):

| Target | Model  | Features            | ROI   | Threshold | Config                              |
| ------ | ------ | ------------------- | ----- | --------- | ----------------------------------- |
| Spread | Linear | recency_weighted_v1 | +2.1% | 7.0 pts   | `conf/weekly_bets/v2_champion.yaml` |
| Totals | Linear | recency_weighted_v1 | +6.1% | 0.5 pts   | `conf/weekly_bets/v2_champion.yaml` |

**Model Files**:

- `models/linear_spread_target.joblib` (trained 2025-12-07)
- `models/linear_total_target.joblib` (trained 2025-12-07)

**Feature Config**: `conf/features/recency_weighted_v1.yaml`

- 8 features: EPA and SR (offense/defense) for home/away
- EWMA decay: α=0.3
- 4-iteration opponent adjustment

---

## Frequency

**Weekly Cadence** (example for Week 10):

- **Monday**: Check if new data is available
- **Tuesday**: Ingest raw data, run aggregation pipeline
- **Wednesday**: Generate predictions, review, make decisions
- **Thursday**: Place bets (if needed before Thu games)
- **Saturday**: Place remaining bets (before Sat games)
- **Sunday-Tuesday**: Games complete, score results
- **Wednesday**: Check dashboard, decide if action needed

**No automation** — all steps require user initiation.

---

## Emergency Procedures

### If Pipeline Fails

1. **Check CFB_MODEL_DATA_ROOT**: Ensure external drive is mounted
2. **Review logs**: Check console output for errors
3. **Manual fix**: Address specific error (missing data, schema changes, etc.)
4. **Re-run step**: Once fixed, re-run the failed step

### If Model Performance Degrades

1. **Check dashboard**: Confirm it's not short-term variance
2. **Review decision**: Use judgment + dashboard alerts
3. **Rollback if needed**: Follow [Rollback SOP](./rollback_sop.md)

---

## Related Documentation

- [Monitoring Dashboard](./monitoring.md) — Dashboard usage and alert interpretation
- [Rollback SOP](./rollback_sop.md) — Model rollback procedure
- [Data Quality](./data_quality.md) — Validation framework (Week 3+)
- [V2 Workflow](../process/experimentation_workflow.md) — Overall 4-phase process
- [Production Deployment](./production_deployment.md) — Phase 4 deployment criteria

---

**Last Updated**: 2025-12-08  
**Status**: V2-aligned, manual workflow
