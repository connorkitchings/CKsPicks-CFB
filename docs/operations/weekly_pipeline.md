# Weekly Pipeline (Manual)

This runbook defines the end-to-end weekly process for producing betting recommendations.

> NOTE (2025-10-20): Pipeline updates are being designed to support a unified points-for model. Refer to `docs/planning/points_for_model.md` before modifying workflow steps.

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

If you have not already generated the weekly stats caches for the season, run these commands once. This is now a two-stage process.

**Stage 1: Non-Adjusted Weekly Aggregates**

This creates a weekly season-to-date aggregation of team stats _before_ opponent adjustment.

```bash
uv run python scripts/cache_weekly_stats.py \
  --year 2024 \
  --stage running \
  --data-root "/path/to/root"
```

**Stage 2: Opponent-Adjusted Weekly Stats**

This reads the non-adjusted data from Stage 1, applies the opponent-adjustment algorithm, and saves the final model-ready features. Use `--adjustment-iterations` to emit multiple depths (e.g., raw snapshot plus 1–4 adjustment rounds).

```bash
uv run python scripts/cache_weekly_stats.py \
  --year 2024 \
  --stage adjusted \
  --data-root "/path/to/root" \
  --adjustment-iterations 0,1,2,3,4
```

Tip: pass `--stage both` to run both steps in one command once the raw `team_game` partitions are in place. Adjust the iteration list as needed; the weekly generator defaults to iteration `4` when no override is supplied.

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

- This step is now handled by the caching process. The prediction script will load pre-computed, point-in-time features from the `processed/team_week_adj/iteration=<depth>/` directory (default depth = 4 iterations).

### Step 3: Modeling and Predictions

- The prediction script now reads directly from the cache, making this step much faster.
- It applies the trained Ridge Regression baseline to the pre-calculated features. To evaluate alternate adjustment depths, pass `--adjustment-iteration <n>` to `generate_weekly_bets_clean`; omit the flag to use the default four-pass adjustment. Mixed-depth experiments are also supported via `--offense-adjustment-iteration` and `--defense-adjustment-iteration`, which override the offensive and defensive feature depths independently.

### Step 4: Bet Selection

- The script computes edges (`|model − line|`) and applies the betting policy.
- Spreads: configurable threshold (default 8.0 via `--spread-threshold`)
- Totals: configurable threshold (default 8.0 via `--total-threshold`)
- Confidence filter (ensemble std dev): defaults set from sweep analysis
  - Spreads: `--spread-std-dev-threshold 2.0`
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

Pass `--dry-run` to skip SMTP delivery and save HTML/text previews under
`artifacts/reports/<year>/email_previews/`.

Need quick performance snapshots? Use the consolidated analysis CLI:

```bash
# Hit rates and volume
uv run python scripts/analysis_cli.py summary reports/2024/CFB_season_2024_all_bets_scored.csv

# Confidence sweep
uv run python scripts/analysis_cli.py confidence reports/2024/CFB_season_2024_all_bets_scored.csv --bet-type spread
```

### Step 6: Outputs

- A CSV report is generated at: `reports/YYYY/CFB_weekWW_bets.csv`
- The pre-scored report columns are: `Year`, `Week`, `Date`, `Time`, `Game`, `Spread`, `Over/Under`, `Spread Prediction`, `Total Prediction`, `Spread Bet`, `Total Bet`.
- The scored report (`_scored.csv`) now feeds the weekly review email, which renders rows with the following columns:
  - Date, Time (explicitly in ET), Game, Line (spread text or `O/U <total>`), Model Prediction (per bet type), Bet, Final Score, Final Result (spread margin or total points), Bet Result
- Note: Report Date/Time are authored in Eastern Time (ET). The email localizes by treating Date/Time as ET (no UTC conversion).

---

## Known Data Caveats

- The CollegeFootballData feed occasionally lists FCS opponents (for example, Portland State) with the same metadata shape as FBS programs. Downstream summaries such as the `analysis` CLI leaderboards or scatter plots can therefore still show 12 games for teams that played an FCS opponent unless the raw classifications are corrected manually. Double-check opponent classification when auditing regular-season aggregates and adjust findings accordingly.

---

## Prediction & Scoring (MVP commands)

### Current Season (2025) — Prediction Only with Prior-Year Models

To produce 2025 picks without training on 2025 data, reuse the 2024-trained ensemble models. The weekly generator loads models from `artifacts/models/<year>/`, so create a symlink first:

```bash
# One-time: point artifacts/models/2025 to the 2024 artifact directory
ln -s 2024 artifacts/models/2025
```

Then cache weekly stats and generate picks (examples shown for weeks already played):

```bash
# Cache point-in-time adjusted stats for 2025 (reads processed team_game)
uv run python scripts/cache_weekly_stats.py --year 2025 --data-root "/Volumes/CK SSD/Coding Projects/cfb_model"

# Generate a weekly report (uses artifacts/models/2025 → 2024)
uv run python -m src.scripts.generate_weekly_bets_clean \
  --year 2025 --week 6 \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --model-dir ./artifacts/models \
  --output-dir artifacts/reports \
  --bankroll 10000 \
  --spread-threshold 8.0 \
  --total-threshold 8.0 \
  --max-weekly-exposure-fraction 0.15 \
  --max-single-bet-fraction 0.05

# Score once games are final
uv run python scripts/score_weekly_picks.py \
  --year 2025 --week 6 \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --report-dir artifacts/reports
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

- Trained models at `artifacts/models/ridge_baseline/<year>/ridge_*.joblib`
- **Cached weekly adjusted stats** present at `processed/team_week_adj/iteration=4/` (or the desired iteration depth).
- Raw games and betting_lines present for the target year.

Generate weekly picks (no API usage; reads from data root):

```bash
uv run python -m src.scripts.generate_weekly_bets_clean \
  --year 2024 --week 5 \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --model-dir ./artifacts/models \
  --output-dir artifacts/reports \
  --bankroll 10000 \
  --spread-threshold 8.0 \
  --total-threshold 8.0 \
  --spread-std-dev-threshold 3.0 \
  --total-std-dev-threshold 1.5 \
  --max-weekly-exposure-fraction 0.15 \
  --max-single-bet-fraction 0.05
```

Points-for evaluation: once `artifacts/models/<year>/points_for_home.joblib` and `points_for_away.joblib` exist (see `scripts/train_points_for_models.py`), add `--prediction-mode points_for` and optional `--points-for-spread-std` / `--points-for-total-std` arguments to generate a comparative report without disturbing the legacy ensemble flow.

Each generator run now emits a companion `CFB_weekXX_bets_metadata.json` file beside the CSV. This metadata records the bankroll, threshold overrides, risk caps (5% single bet / 15% weekly exposure by default), and the resolved data/model paths used for that slate—save it with the report for reproducibility and policy audits.

Score the week against final outcomes:

```bash
# Option A (standard):
uv run python scripts/score_weekly_picks.py \
  --year 2024 --week 5 \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --report-dir artifacts/reports

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

```

## Session Closing Checklist (AI Assistant)

When ending an AI-assisted session with code/doc changes:

1. Capture a TL;DR and session details in `session_logs/YYYY-MM-DD/NN.md` using the template in `docs/guides/ai_session_templates.md`.
2. Summarize accomplishments, blockers, and next steps in the final assistant message.
3. Remind the user to review `git status`, `git add`, `git commit`, and `git push` with a proposed commit message if changes were made.
4. Recommend running `uv run ruff format . && uv run ruff check .`, `uv run pytest -q`, and (if docs changed) `uv run mkdocs build --quiet`.
