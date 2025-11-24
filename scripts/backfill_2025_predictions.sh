#!/bin/bash
# Backfill 2025 predictions using the new Mixed Ensemble models (trained on 2019-2023)

set -e  # Exit on error

YEAR=2025
MODEL_YEAR=2024
START_WEEK=1
END_WEEK=13
DATA_ROOT="/Volumes/CK SSD/Coding Projects/cfb_model"

echo "Starting backfill for $YEAR (Weeks $START_WEEK-$END_WEEK)..."

# 1. Cache Weekly Stats (ensure features are up to date)
echo "Caching weekly stats for $YEAR..."
uv run python scripts/cache_weekly_stats.py \
  --year $YEAR \
  --stage both \
  --data-root "$DATA_ROOT" \
  --adjustment-iterations 0,1,2,3,4

# 2. Generate Predictions and Score
for week in $(seq $START_WEEK $END_WEEK); do
    echo "--------------------------------------------------"
    echo "Processing Week $week..."
    
    # Generate Bets
    # Using --prediction-mode points_for to use the new Mixed Ensemble
    # Using --model-year 2024 to use the models we just trained
    uv run python -m src.scripts.generate_weekly_bets_clean \
      --year $YEAR \
      --week $week \
      --model-year $MODEL_YEAR \
      --prediction-mode points_for \
      --data-root "$DATA_ROOT" \
      --model-dir artifacts/models \
      --output-dir artifacts/reports \
      --bankroll 10000 \
      --spread-threshold 8.0 \
      --total-threshold 8.0 \
      --max-weekly-exposure-fraction 0.15 \
      --max-single-bet-fraction 0.05
      
    # Score Picks (if games are final)
    # We allow this to fail (e.g. if games aren't played yet) without stopping the loop
    echo "Scoring Week $week..."
    uv run python scripts/score_weekly_picks.py \
      --year $YEAR \
      --week $week \
      --data-root "$DATA_ROOT" \
      --report-dir artifacts/reports || echo "Scoring failed for Week $week (games might not be final)"
      
done

echo "--------------------------------------------------"
echo "Backfill complete!"
