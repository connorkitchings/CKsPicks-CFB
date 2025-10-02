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

### Step 5: Outputs

- A CSV report is generated at: `reports/YYYY/CFB_weekWW_bets.csv`
- Columns include (subset):
  - Identity/context: `season`, `week`, `game_id`, `game_date`, `home_team`, `away_team`, `neutral_site`, `sportsbook`
  - Lines and predictions: `home_team_spread_line`, `total_line`, `model_spread`, `model_total`, `predicted_spread_std_dev`, `predicted_total_std_dev`
  - Edge and decisions: `edge_spread`, `edge_total`, `bet_spread`, `bet_total`
  - Kelly sizing: `kelly_fraction_spread`, `kelly_fraction_total`, `bet_units_spread`, `bet_units_total`, and aggregate `bet_units`
- Pricing retention: the pipeline retains provider row fields (e.g., odds columns) when present; when pricing is missing, the weekly generator assumes -110 for ATS/OU sizing.

---

## Prediction & Scoring (MVP commands)

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
uv run python scripts/score_weekly_picks.py \
  --year 2024 --week 5 \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --report-dir ./reports
```

Run remainder of season using the unified CLI:

```bash
python scripts/cli.py run-season \
  --year 2024 \
  --start-week 5 \
  --end-week 16 \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model"
```
```
