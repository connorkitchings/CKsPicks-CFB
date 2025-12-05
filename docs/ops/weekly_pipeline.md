# Weekly Pipeline (The 5-Step Process)

This runbook defines the rigorous 5-step process for producing betting recommendations. This workflow ensures that every model deployed to production has passed strict validation gates.

## The 5-Step Workflow

1.  **Ingest & Process**: Clean, automated data flow to create point-in-time features.
2.  **Model & Experiment**: Train a "Champion" model on historical data (2019, 2021-2023).
3.  **2024 Baseline (The Gate)**: Validate the Champion on the 2024 season (simulated). **Must pass performance thresholds.**
4.  **2025 Actuals (Validation)**: Validate the Champion on the current 2025 season (walk-forward).
5.  **Production (Execution)**: Generate predictions for the upcoming week using the validated Champion.

---

## Step 1: Ingest & Process

Ensure the data cache is up-to-date. This creates the "Point-in-Time" feature snapshots used for both training and inference.

```bash
# Cache weekly stats for the current season (e.g., 2025)
uv run python scripts/cache_weekly_stats.py \
  --year 2025 \
  --stage adjusted \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --adjustment-iterations 0,1,2,3,4
```

> **Note**: For training (Step 2), you must also ensure 2019, 2021, 2022, and 2023 are cached.

## Step 2: Model & Experiment (Train Champion)

Train the "Points-For" Mixed Ensemble (CatBoost + XGBoost) on historical data (2019, 2021-2023). This creates the model artifacts that will be candidates for production.

```bash
# Train and save models to artifacts/models/2024 (The "Model Year")
uv run python scripts/train_points_for_production.py \
  --output-dir artifacts/models
```

**Output**: `artifacts/models/2024/points_for_home.joblib`, `points_for_away.joblib`, `metadata.json`

## Step 3: 2024 Baseline (The Gate)

**Critical Step**: Before using the model for 2025, it must prove it can beat the market on the 2024 season. This script runs the _saved_ model through the entire 2024 season without retraining.

```bash
uv run python scripts/validate_model.py \
  --year 2024 \
  --model-year 2024 \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model"
```

**Success Criteria**:

- Spread Hit Rate > 52.4% (Profitability Threshold)
- Sufficient Volume (> 5 bets/week average)

## Step 4: 2025 Actuals (Validation)

Run the same model on the current season (2025) to see how it is performing _right now_.

```bash
uv run python scripts/validate_model.py \
  --year 2025 \
  --model-year 2024 \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model"
```

**Review**:

- Is the ROI positive?
- Are there any alarming trends (e.g., failing late in the season)?

## Step 5: Production (Execution)

Only if Steps 3 & 4 are satisfactory, generate the picks for the upcoming week.

```bash
# Example: Generate picks for Week 14 of 2025 using the 2024 model
uv run python -m src.scripts.generate_weekly_bets_clean \
  --year 2025 --week 14 \
  --model-year 2024 \
  --prediction-mode points_for \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --bankroll 10000 \
  --spread-threshold 8.0 \
  --total-threshold 8.0
```

**Output**: `artifacts/reports/2025/predictions/CFB_week14_bets.csv`

---

## Scoring & Review

After the games are played, score the picks to update the "Actuals" for next week's Step 4.

```bash
uv run python scripts/score_weekly_picks.py \
  --year 2025 --week 14 \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --report-dir artifacts/reports
```
