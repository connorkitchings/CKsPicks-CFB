# System Stats Generation Workflow

## Overview

The **System Info** table in the weekly betting email requires accurate, historical performance data for the currently deployed model system. This data includes:

1.  **Last Year's Full Record** (Backtested on the deployed system).
2.  **Last Year's Specific Week Record** (Backtested for the exact same week #).
3.  **Current Year YTD Record** (System-generated backtest, usually preferred over manual tracking for consistency).

This workflow ensures these numbers are generated automatically using the exact same configuration (features, alpha, thresholds) as the prediction models.

## The Script: `generate_system_stats.py`

Located at: `scripts/pipeline/generate_system_stats.py`

This script performs the following actions:

1.  **Loads Configuration**: Reads `conf/weekly_bets/v2_champion.yaml` (or specified config) to determine:
    - `spread_edge_threshold` & `total_edge_threshold`
    - `features.alpha`
    - Feature set (e.g., `matchup_v1`).
2.  **Historical Backtest (Walk-Forward)**:
    - Trains models on data prior to `training.test_year` (e.g., 2024).
    - Predicts for `training.test_year`.
    - Calculates betting records and ROI based on the thresholds.
3.  **Current YTD Backtest**:
    - Trains models on data prior to `training.deploy_year` (e.g., 2025).
    - Predicts for `training.deploy_year`.
    - Calculates YTD records.
4.  **Output**: Saves a JSON file to `data/production/system_stats.json`.

## Usage

### Weekly Pipeline Integration

This script should be run **after** data ingestion and **before** publishing picks. It ensures the email context is populated.

```bash
uv run python -m scripts.pipeline.generate_system_stats --config conf/weekly_bets/v2_champion.yaml
```

**Optional Arguments:**

- `--week <N>`: Override the week number from the config (useful if running for a specific past week).

### Output File Structure (`data/production/system_stats.json`)

```json
{
  "2024_full": {
    "spread": {"wins": 179, "losses": 174, "roi": -0.032, ...},
    "total": {"wins": 388, "losses": 310, "roi": 0.061, ...}
  },
  "2024_week_16": {
    "spread": {...},
    "total": {...}
  },
  "2025_ytd": {
    "spread": {...},
    "total": {...}
  }
}
```

## Dependencies

- **Config**: `conf/weekly_bets/v2_champion.yaml` must define `models`, `training`, and `features`.
- **Data**: Requires processed data for the training years defined in the config.

## Troubleshooting

- **Missing Features**: Ensure `conf/features/matchup_v1.yaml` (or equivalent) is correctly structured.
- **Empty Output**: Check if data for the historical year (e.g., 2024) is fully ingested and recency features are calculated.
