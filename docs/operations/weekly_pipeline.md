# Weekly Pipeline (Manual)

This runbook defines the end-to-end weekly process for producing betting recommendations.

## Schedule

- Cadence: Wednesdays at 12:00 ET (manual trigger)
- Reason: Data is stored on an external drive; full automation is not feasible

## Scope (MVP)

- Collect last week’s play-by-play (PBP)
- Collect current week’s betting lines (spreads + totals) from CFBD
- **Load pre-cached, point-in-time opponent-adjusted features**
- Train/apply model (Ridge Regression baseline)
- Generate predictions and filter to bets using thresholds

## Preconditions

- Teams must have played ≥ 4 games this season; otherwise, do not bet those games.
- The weekly adjusted stats cache should be populated for the target season. If not, the prediction script will fail.

## Steps

### Step 0: Caching (Optional, One-Time)

If you have not already generated the weekly adjusted stats cache for the season, run this command once. This process can take a significant amount of time.

```bash
uv run python scripts/cache_weekly_stats.py --year 2024 --data-root "/path/to/root"
```

### Step 1: Data Collection (API-Minimizing)

- Pull last week’s plays (FBS, regular season, include Week 0). Prefer targeting the week:

```bash
python scripts/cli.py ingest games --year 2024 --season-type regular --week 5 --data-root "/path/to/root"
python scripts/cli.py ingest plays --year 2024 --season-type regular --week 5 --data-root "/path/to/root"
```

- Pull current week’s betting lines (skipped automatically if already present for the season):

```bash
python scripts/cli.py ingest betting_lines --year 2024 --season-type regular --data-root "/path/to/root"
```

### Step 2: Feature Transformation

- This step is now handled by the caching process. The prediction script will load pre-computed, point-in-time features from the `processed/team_week_adj/` directory.

### Step 3: Modeling and Predictions

- The prediction script now reads directly from the cache, making this step much faster.
- It applies the trained Ridge Regression baseline to the pre-calculated features.

### Step 4: Bet Selection

- The script computes edges (`|model − line|`) and applies the betting policy.
- Spreads: configurable threshold (default 6.0 via `--spread-threshold`)
- Totals: configurable threshold (default 6.0 via `--total-threshold`)
- Confidence filter (ensemble std dev): defaults set from sweep analysis
  - Spreads: `--spread-std-dev-threshold 3.0`
  - Totals: `--total-std-dev-threshold 1.5`
- Only include games where both teams have ≥ 4 games played.

### Step 5: Publish Picks

- After the report is generated, a publisher script is run to format the picks into a clean HTML table and email them to a pre-configured address.

```bash
# Example (script to be created)
python scripts/publish_picks.py --year 2024 --week 5
```

### Step 7: Publish Weekly Review

- After the previous week's games have been scored, a review email can be sent out summarizing the model's performance.

```bash
python scripts/publish_review.py --year 2024 --week 5
```

### Step 6: Outputs

- A CSV report is generated at: `reports/YYYY/CFB_weekWW_bets.csv`
- The pre-scored report columns are: `Year`, `Week`, `Date`, `Time`, `Game`, `Spread`, `Over/Under`, `Spread Prediction`, `Total Prediction`, `Spread Bet`, `Total Bet`.
- The scored report (`_scored.csv`) now feeds the weekly review email, which renders rows with the following columns:
  - Date, Time (explicitly in ET), Game, Line (spread text or `O/U <total>`), Model Prediction (per bet type), Bet, Final Score, Final Result (spread margin or total points), Bet Result
- Note: Report Date/Time are authored in Eastern Time (ET). The email localizes by treating Date/Time as ET (no UTC conversion).

---

## Prediction & Scoring (MVP commands)

### Current Season (2025) — Prediction Only with Prior-Year Models

To produce 2025 picks without training on 2025 data, reuse the 2024-trained ensemble models. The weekly generator loads models from `models/<year>/`, so create a symlink first:

```bash
# One-time: point models/2025 to the 2024 artifact directory
ln -s 2024 models/2025
```

Then cache weekly stats and generate picks (examples shown for weeks already played):

```bash
# Cache point-in-time adjusted stats for 2025 (reads processed team_game)
uv run python scripts/cache_weekly_stats.py --year 2025 --data-root "/Volumes/CK SSD/Coding Projects/cfb_model"

# Generate a weekly report (uses models/2025 → 2024)
uv run python src/cfb_model/scripts/generate_weekly_bets_clean.py \
  --year 2025 --week 6 \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --model-dir ./models \
  --output-dir ./reports \
  --spread-threshold 6.0 \
  --total-threshold 6.0

# Score once games are final
uv run python scripts/score_weekly_picks.py \
  --year 2025 --week 6 \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --report-dir ./reports
```

Notes:
- Do not train on 2025 data.
- If SHAP explanations error due to model wrapper incompatibility, the generator will continue without explanations (columns left blank).

### Pre-aggregations (if needed)

If raw plays and processed features need to be rebuilt:

```bash
uv run python scripts/preaggregations_cli.py --year 2024 --data-root "/Volumes/CK SSD/Coding Projects/cfb_model"
```

Prereqs:
- Trained models at `models/ridge_baseline/<year>/ridge_*.joblib`
- **Cached weekly adjusted stats** present at `processed/team_week_adj/`.
- Raw games and betting_lines present for the target year.

Generate weekly picks (no API usage; reads from data root):

```bash
uv run python src/cfb_model/scripts/generate_weekly_bets_clean.py \
  --year 2024 --week 5 \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --model-dir ./models \
  --output-dir ./reports \
  --spread-threshold 6.0 \
  --total-threshold 6.0 \
  --spread-std-dev-threshold 3.0 \
  --total-std-dev-threshold 1.5 \
  --kelly-fraction 0.25 \
  --kelly-cap 0.25 \
  --base-unit-fraction 0.02
```

Score the week against final outcomes:

```bash
# Option A (standard):
uv run python scripts/score_weekly_picks.py \
  --year 2024 --week 5 \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --report-dir ./reports

# Option B (fresh scoring utility used during 2025 Wk6 incident):
# Ensures game_id mapping, parses lines, validates 7/3 bet counts, and reads week-partitioned raw data.
uv run python score_fresh.py
```

Important:
- When reading game results, ensure the storage root points to the project root (e.g., `/Volumes/CK SSD/Coding Projects/cfb_model`) with `data_type=raw`. Weekly game results are written under `raw/games/year=<YYYY>/week=<WW>/data.csv`.
- If you accidentally point to `/data/raw/games/year=<YYYY>/data.csv`, you may read stale or aggregated rows. Use the week-partitioned file for authoritative scored results.

Run remainder of season using the unified CLI:

```bash
python scripts/cli.py run-season \
  --year 2024 \
  --start-week 5 \
  --end-week 16 \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model"
```
```
