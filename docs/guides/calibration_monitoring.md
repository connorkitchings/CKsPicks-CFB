# Weekly Calibration Monitoring

## Overview

The calibration monitoring script (`scripts/monitor_calibration.py`) tracks model prediction bias, drift, and calibration quality to ensure production models remain accurate over time.

## Usage

### Basic Usage

Monitor the current season:

```bash
uv run python scripts/monitor_calibration.py --year 2024
```

### Monitor Specific Weeks

Check calibration for a specific week range:

```bash
uv run python scripts/monitor_calibration.py --year 2024 --start-week 10 --end-week 13
```

### Monitor Single Week

Analyze a single week in detail:

```bash
uv run python scripts/monitor_calibration.py --year 2024 --start-week 12 --end-week 12
```

## Metrics Tracked

### Calibration Metrics

For each prediction target (home points, away points, spread, total):

- **Bias (Mean Error)**: Average prediction error (positive = over-predicting, negative = under-predicting)
- **RMSE**: Root mean squared error
- **MAE**: Mean absolute error
- **Std Error**: Standard deviation of errors

### Drift Detection

Automatically alerts if:

- **Bias Drift**: `|current_bias - baseline_bias| > 1.0 points`
- **RMSE Degradation**: `current_rmse - baseline_rmse > 1.5 points`

### Weekly Breakdown

Shows per-week calibration metrics to identify temporal patterns or specific problematic weeks.

## Interpreting Results

### Example Output

```
=== CALIBRATION METRICS ===

Spread (Derived):
  Bias (Mean Error): +1.80 points
  RMSE: 18.69
  MAE: 14.45

=== DRIFT DETECTION ===

Spread Alerts:
  ⚠️  BIAS DRIFT: 1.80 points (threshold: 1.00)

=== RECOMMENDATIONS ===

📊 Consider recalibration: Spread bias is +1.80 points
```

### Action Items

1. **Bias < 0.5 points**: ✅ No action needed
2. **Bias 0.5-1.0 points**: 📊 Monitor closely, consider recalibration if persistent
3. **Bias > 1.0 points**: ⚠️ Recalibration recommended

### Recalibration Process

If systematic bias is detected:

1. Calculate the bias value from monitoring output
2. Update model configuration to apply bias correction
3. Re-run monitoring to confirm correction
4. Document the change in `docs/decisions/decision_log.md`

## Integration with Weekly Pipeline

### Recommended Schedule

Run calibration checks weekly after predictions are generated:

```bash
# Generate predictions
uv run python scripts/generate_weekly_bets_hydra.py

# Check calibration
uv run python scripts/monitor_calibration.py --year 2024
```

### Automated Monitoring (Future)

Consider adding to CI/CD or scheduled jobs:

```bash
# In GitHub Actions or cron
0 14 * * WED uv run python scripts/monitor_calibration.py --year $(date +%Y)
```

## Baseline Values

Current baselines (from 2024 validation):

- **Spread RMSE**: 18.69
- **Total RMSE**: 17.18
- **Expected Bias**: ~0 points (calibrated models)

## Troubleshooting

### Missing Features Warning

If you see warnings about missing features, the script automatically adds them as zeros. This is expected if comparing models trained with different feature sets.

### Data Not Found

Ensure the data path is correct in the script:

```python
"/Volumes/CK SSD/Coding Projects/cfb_model"
```

Update this path if your data is stored elsewhere.

### Model Loading Errors

Ensure models are registered in MLflow registry with "Production" stage:

```bash
# Check registered models
mlflow models list -n points_for_home
```

## Future Enhancements

- Confidence interval tracking
- Betting performance correlation
- Automated slack/email alerts
- Historical calibration trend visualization
