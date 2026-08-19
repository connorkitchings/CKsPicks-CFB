# V2 Quick Start Guide for Operators

> **⚠️ SUPERSEDED (historical reference).** Weekly operations now run through
> the ops state machine (`make publish-week` / `freeze-week` / `close-week`)
> — see the [Production Runbook](../ops/production_runbook.md). This guide's
> sportsbook/bankroll workflow does not reflect the display-only 2026 product.

**Purpose:** Step-by-step guide for weekly betting operations  
**Time Required:** ~30 minutes per week  
**Prerequisites:** Repository cloned, environment configured

---

## Weekly Workflow (Monday/Tuesday)

### Step 1: Update Week Number

Edit `conf/weekly_bets/v2_champion.yaml`:

```yaml
year: 2025
week: X  # <-- Update this to current week
```

### Step 2: Generate Predictions

```bash
cd /Users/connorkitchings/Desktop/Repositories/ckspicks-cfb
source .env
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py
```

**Output:** `data/production/predictions/2025/CFB_week{X}_bets.csv`

### Step 3: Review Predictions

Open the CSV and look for:
- **Spread Bet** column: Home/Away/No Bet
- **Spread Confidence**: High (edge ≥ 8.0) or Medium (edge ≥ 0.0)
- **Total Bet**: Over/Under/No Bet
- **Edge values**: Higher is better

**Sample output:**
```csv
Game,Spread Bet,Spread Confidence,Total Bet,edge_spread,edge_total
Alabama @ Georgia,Home,High,Over,8.5,2.1
Texas @ Oklahoma,Away,Medium,No Bet,3.2,0.8
```

### Step 4: Place Bets

1. Open your sportsbook
2. Find games with "High" confidence (edge ≥ 8.0) - these are priority bets
3. Place bets according to recommendations
4. Record bets placed in tracking spreadsheet

**Betting Rules:**
- **High Confidence** (edge ≥ 8.0): Full Kelly stake
- **Medium Confidence** (edge 0.0-8.0): Half Kelly stake
- **No Bet** (edge < 0.0): Skip

---

## Post-Game Workflow (Monday)

### Step 5: Score Results

After all games complete:

```bash
PYTHONPATH=. uv run python scripts/pipeline/score_weekly_bets.py --year 2025 --week X
```

**Output:** Updated tracking with actual results

### Step 6: Update Dashboard

```bash
streamlit run dashboard/monitoring.py
```

Check:
- Weekly ROI
- Hit rate
- Cumulative performance
- Alert status

---

## Emergency Procedures

### If Model Seems Broken

1. **Check validation is running:**
   ```bash
   ps aux | grep train.py
   ```

2. **Run quick sanity check:**
   ```bash
   PYTHONPATH=. uv run python -c "
   from cks_picks_cfb.features.v2_recency import load_v2_recency_data
   df = load_v2_recency_data(2025, alpha=0.3, for_prediction=True)
   print(f'Loaded {len(df)} games')
   print(df[['home_team', 'away_team', 'week']].head())
   "
   ```

3. **If issues persist:** Check [Production Guide](production_guide.md) troubleshooting section

### If Need to Rollback

See [Production Guide](production_guide.md) "Rollback Procedures" section.

Quick emergency rollback:
```bash
cp models/backup/linear_spread_target_{DATE}.joblib models/linear_spread_target.joblib
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py
```

---

## Common Commands

```bash
# Generate predictions for specific week
PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py --year 2025 --week 10

# Score specific week
PYTHONPATH=. uv run python scripts/pipeline/score_weekly_bets.py --year 2025 --week 10

# Run health checks
make health

# Check git status
git status

# View MLflow experiments
mlflow ui --backend-store-uri file:///Users/connorkitchings/Desktop/Repositories/ckspicks-cfb/artifacts/mlruns
```

---

## File Locations

- **Predictions:** `data/production/predictions/2025/`
- **Models:** `models/`
- **Config:** `conf/weekly_bets/v2_champion.yaml`
- **Logs:** `artifacts/hydra_outputs/`
- **Tracking:** MLflow UI

---

## Key Contacts

- **Issues:** connor.kitchings@gmail.com
- **Repository:** https://github.com/connorkitchings/CKsPicks-CFB

---

## Quick Reference

| Task | Command |
|------|---------|
| Generate bets | `PYTHONPATH=. uv run python scripts/pipeline/generate_weekly_bets.py` |
| Score results | `PYTHONPATH=. uv run python scripts/pipeline/score_weekly_bets.py --year 2025 --week X` |
| View dashboard | `streamlit run dashboard/monitoring.py` |
| Run validation | `PYTHONPATH=src uv run python -m cks_picks_cfb.train experiment=v2_champion_validation` |
| Health check | `make health` |

---

**Remember:**
- Always update the week number in config before generating predictions
- High confidence bets (edge ≥ 8.0) have the best historical performance
- Check the dashboard weekly to monitor for degradation
- Document any issues in the decision log
