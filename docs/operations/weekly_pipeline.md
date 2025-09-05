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
