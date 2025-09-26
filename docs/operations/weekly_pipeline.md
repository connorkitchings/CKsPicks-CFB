# Weekly Pipeline (Manual)

This runbook defines the end-to-end weekly process for producing betting recommendations.

## Schedule

- Cadence: Wednesdays at 12:00 ET (manual trigger)
- Reason: Data is stored on an external drive; full automation is not feasible

## Scope (MVP)

- Collect last week’s play-by-play (PBP)
- Collect current week’s betting lines (spreads + totals) from CFBD
- Transform features (season-to-date, opponent-adjusted via iterative averaging)
- Train/apply model (Ridge Regression baseline)
- Generate predictions and filter to bets using thresholds

## Preconditions

- Teams must have played ≥ 4 games this season; otherwise, do not bet those games
- Training coverage for model: Train on 2019–2023 excluding 2020 (COVID); use 2024 as holdout/test.
  FBS regular season only, include Week 0

## Steps

1. Data collection

- Pull last week’s plays (FBS, regular season, include Week 0)
- Pull current week’s betting lines (spreads and totals)

1. Feature transformation

- Season-to-date aggregates per team
- Opponent adjustment via iterative averaging (4 iterations), with extra weight on last 3 games
- Include per-play and per-possession features (pace-aware)
- Add home/away control to the model (not to the stats directly)
- Tip: Use `--quiet` with the pre-aggregation CLI to suppress per-game logs on long runs

1. Modeling and predictions

- Ridge Regression baseline
- Targets: final margin (spread) and total points
- Use season-silo training; apply to current season weekly

1. Bet selection

- Compute edges: |model − line|
- Spreads: bet if edge ≥ 3.5
- Totals: bet if edge ≥ 7.5
- Only include games where both teams have ≥ 4 games played

1. Validation (post-aggregation)

- Run deep semantic validation for the current season (processed data):

```bash
./.venv/bin/python -m cfb_model.data.validation --year <YEAR> --data-type processed --deep
```

1. Outputs

- CSV report at: `reports/YYYY/CFB_weekWW_bets.csv`
- Columns (suggested):
  - season, week, game_id, game_date
  - home_team, away_team, neutral_site
  - sportsbook
  - spread_line, total_line
  - model_spread, model_total
  - edge_spread, edge_total
  - bet_spread (home/away/none), bet_total (over/under/none)
  - bet_units (e.g., 1u flat for MVP)

- Backtesting/scoring (planned):
  - Weekly and cumulative metrics written to `reports/backtests/backtest_weekly.csv` and `reports/backtests/backtest_summary.csv`

## Acceptance criteria

- Report contains only games passing the thresholds and ≥ 4 games constraint
- Reproducible with a single manual run mid-week
- Links to upstream docs:
  - Project Org → Modeling Baseline (`docs/project_org/modeling_baseline.md`)
  - CFBD Data Ingestion (`docs/cfbd/data_ingestion.md`)

---

## Prediction & Scoring (MVP commands)

Prereqs:
- Trained models at `models/ridge_baseline/<year>/ridge_*.joblib`
- Processed features present at your data root (see `CFB_MODEL_DATA_ROOT`)
- Raw games and betting_lines present for the target year

Generate weekly picks (no API usage; reads from data root):

```bash
PYTHONPATH=./src \
python3 src/cfb_model/scripts/generate_weekly_bets_clean.py \
  --year 2024 --week 5 \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --model-dir ./models/ridge_baseline \
  --output-dir ./reports
```

Score the week against final outcomes:

```bash
PYTHONPATH=./src \
python3 scripts/score_weekly_picks.py \
  --year 2024 --week 5 \
  --data-root "/Volumes/CK SSD/Coding Projects/cfb_model" \
  --report-dir ./reports
```

Run remainder of season (weeks discovered from raw games) and combine results:

```bash
PYTHONPATH=./src python3 - << 'PY'
import os, subprocess, pandas as pd
from cfb_model.data.storage.local_storage import LocalStorage
DATA_ROOT="/Volumes/CK SSD/Coding Projects/cfb_model"; REPORT_DIR="./reports"; MODEL_DIR="./models/ridge_baseline"; YEAR=2024
raw=LocalStorage(data_root=DATA_ROOT,file_format='csv',data_type='raw')
weeks=sorted(int(w) for w in pd.DataFrame.from_records(raw.read_index('games',{'year':YEAR}))['week'].dropna().unique() if int(w)>=6)
combined=[]
for wk in weeks:
  out=os.path.join(REPORT_DIR,str(YEAR),f"CFB_week{wk}_bets.csv")
  if not os.path.exists(out):
    subprocess.run(['python3','src/cfb_model/scripts/generate_weekly_bets_clean.py','--year',str(YEAR),'--week',str(wk),'--data-root',DATA_ROOT,'--model-dir',MODEL_DIR,'--output-dir',REPORT_DIR],check=True)
  subprocess.run(['python3','scripts/score_weekly_picks.py','--year',str(YEAR),'--week',str(wk),'--data-root',DATA_ROOT,'--report-dir',REPORT_DIR],check=True)
  combined.append(pd.read_csv(os.path.join(REPORT_DIR,str(YEAR),f"CFB_week{wk}_bets_scored.csv")))
all_scored=pd.concat(combined,ignore_index=True)
out_comb=os.path.join(REPORT_DIR,str(YEAR),f"CFB_weeks{weeks[0]}-{weeks[-1]}_bets_scored_combined.csv")
all_scored.to_csv(out_comb,index=False)
mask=all_scored['bet_spread'].isin(['home','away'])
print({'combined_csv':out_comb,'picks':int(mask.sum()),'wins':int(all_scored.loc[mask,'pick_win'].sum()),'hit_rate':round(float(all_scored.loc[mask,'pick_win'].mean()),3)})
PY
```
