#!/bin/bash
set -e

# Check for required arguments
if [ "$#" -ne 3 ]; then
    echo "Usage: $0 <year> <week> <data_root>"
    exit 1
fi

YEAR=$1
WEEK=$2
DATA_ROOT=$3
PREV_WEEK=$((WEEK - 1))

echo "--- Starting Weekly Pipeline for Year $YEAR, Week $WEEK ---"

# --- Ingest & Process Previous Week ---
echo "\n--- Step 1: Ingesting data for previous week ($PREV_WEEK) ---"
uv run python scripts/cli.py ingest games --year "$YEAR" --week "$PREV_WEEK" --data-root "$DATA_ROOT"
uv run python scripts/cli.py ingest plays --year "$YEAR" --season-type regular --week "$PREV_WEEK" --data-root "$DATA_ROOT"

echo "\n--- Step 2: Aggregating new data into weekly stats cache ---"
uv run python scripts/cache_weekly_stats.py --year "$YEAR" --data-root "$DATA_ROOT"

# --- Review Previous Week ---
echo "\n--- Step 3: Scoring bets for previous week ($PREV_WEEK) ---"
uv run python scripts/score_weekly_picks.py --year "$YEAR" --week "$PREV_WEEK" --data-root "$DATA_ROOT" --report-dir ./reports

echo "\n--- Step 4: Publishing review for previous week ($PREV_WEEK) ---"
uv run python scripts/publish_review.py --year "$YEAR" --week "$PREV_WEEK" --report-dir ./reports --mode prod

# --- Prepare Current Week ---
echo "\n--- Step 5: Ingesting schedule and lines for current week ($WEEK) ---"
uv run python scripts/cli.py ingest games --year "$YEAR" --week "$WEEK" --data-root "$DATA_ROOT"
uv run python scripts/cli.py ingest betting_lines --year "$YEAR" --data-root "$DATA_ROOT"

echo "\n--- Step 6: Generating bets for current week ($WEEK) ---"
uv run python src/cfb_model/scripts/generate_weekly_bets_clean.py \
    --year "$YEAR" --week "$WEEK" \
    --data-root "$DATA_ROOT" \
    --model-dir ./models \
    --output-dir ./reports \
    --spread-threshold 6.0 \
    --total-threshold 6.0

echo "\n--- Step 7: Publishing picks for current week ($WEEK) ---"
uv run python scripts/publish_picks.py --year "$YEAR" --week "$WEEK" --report-dir ./reports --mode prod

echo "\n--- Weekly Pipeline for Year $YEAR, Week $WEEK Complete ---"
