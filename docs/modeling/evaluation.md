# Model Evaluation Criteria

**V2 Status** (as of 2025-12-05): This document defines evaluation metrics for general model development. For **V2 promotion-specific criteria**, see [`promotion_framework.md`](../process/promotion_framework.md) which defines the 5-gate system.

This document defines the success thresholds, performance metrics, and model selection criteria for the cfb_model betting system.

> 🔗 **Related**: [V2 Promotion Framework](../process/promotion_framework.md) | [Modeling Baseline](baseline.md) | [Feature Catalog](features.md)

---

## V2 Promotion Metrics (Quick Reference)

**For feature/model promotion in V2 workflow**, these specific thresholds apply:

- **Phase 2 (Features)**: +1.0% ROI improvement, 90% bootstrap confidence
- **Phase 3 (Models)**: +1.5% ROI improvement, 95% bootstrap confidence
- **Both Phases**: Volume ≥100 bets, stability (3/4 quarters positive), no degradation

**Full details**: See [`promotion_framework.md`](../process/promotion_framework.md)

The metrics below provide supporting context and additional evaluation criteria beyond the V2 gates.

---

## Success Thresholds

### Primary Success Metrics

#### 1. Hit Rate (Win Rate)

- **MVP Threshold**: ≥ 52.4% (break-even for -110 odds)
- **Target Performance**: ≥ 55% (strong profitability)
- **Excellent Performance**: ≥ 58% (exceptional system)
- **Measurement Period**: Minimum 100 bets, ideally full season
- **Calculation**: `wins / total_bets`

#### 2. Return on Investment (ROI)

- **MVP Threshold**: ≥ 3% (positive expected value)
- **Target Performance**: ≥ 10% (strong profitability)
- **Excellent Performance**: ≥ 15% (exceptional returns)
- **Measurement Period**: Full season or 200+ bets
- **Calculation**: `(total_winnings - total_wagered) / total_wagered`

#### 3. Units Won

- **MVP Threshold**: ≥ +5 units per season
- **Target Performance**: ≥ +20 units per season
- **Excellent Performance**: ≥ +40 units per season
- **Measurement Period**: Full season
- **Calculation**: Sum of individual bet outcomes in units

### Secondary Success Metrics

#### 4. Prediction Accuracy (RMSE/MAE)

- **Spread Predictions**:
  - **Acceptable**: RMSE ≤ 14 points, MAE ≤ 10 points
  - **Good**: RMSE ≤ 12 points, MAE ≤ 8 points
  - **Excellent**: RMSE ≤ 10 points, MAE ≤ 7 points
- **Total Predictions**:
  - **Acceptable**: RMSE ≤ 12 points, MAE ≤ 9 points
  - **Good**: RMSE ≤ 10 points, MAE ≤ 7 points
  - **Excellent**: RMSE ≤ 8 points, MAE ≤ 6 points

#### 5. Calibration Quality

- **Well-Calibrated**: 95% confidence intervals contain actual outcomes 90-95% of time
- **Prediction Intervals**: Should reflect true uncertainty
- **Measurement**: Reliability plots, coverage probability

#### 6. Edge Detection Ability

- **Minimum Viable**: 60% of bets with model edge ≥ 3 points show profit
- **Target**: 70% of high-edge bets (≥ 5 points) show profit
- **Measurement**: Profit rate by edge magnitude buckets

---

## Evaluation Framework

### Model Comparison Methodology

#### 1. Historical Backtesting

```python
# Backtesting framework
def evaluate_model_historical(model, years, validation_method='walk_forward'):
    \"\"\"
    Evaluate model on historical data using walk-forward validation

    Args:
        model: Trained model object
        years: List of years to evaluate (e.g., [2019, 2021, 2022, 2023])
        validation_method: 'walk_forward', 'time_series_split', or 'holdout'

    Returns:
        dict: Comprehensive evaluation metrics
    \"\"\"
    results = {
        'hit_rate': [],
        'roi': [],
        'units_won': [],
        'rmse_spread': [],
        'mae_spread': [],
        'calibration_score': [],
        'edge_accuracy': []
    }

    for year in years:
        # Load training data (all previous years)
        train_data = load_training_data(years_before=year)

        # Load test data (current year)
        test_data = load_test_data(year=year)

        # Train model on historical data
        model.fit(train_data.features, train_data.targets)

        # Generate predictions
        predictions = model.predict(test_data.features)

        # Calculate metrics
        year_results = calculate_metrics(predictions, test_data.actual)

        # Store results
        for metric, value in year_results.items():
            results[metric].append(value)

    # Aggregate results
    return aggregate_metrics(results)
```

#### 2. Cross-Validation Strategy

- **Time Series Split**: Respect temporal ordering, no data leakage
- **Walk-Forward Validation**: Train on past, predict future (mimics real usage)
- **Season-Based Splits**: Each season as separate validation fold
- **Minimum Training Window**: 3 seasons of data

#### 3. Statistical Significance Testing

```python
def statistical_significance_test(model_a_results, model_b_results, alpha=0.05):
    \"\"\"
    Test if Model A significantly outperforms Model B
    \"\"\"
    from scipy import stats

    # Paired t-test for hit rates
    hit_rate_pvalue = stats.ttest_rel(
        model_a_results['hit_rates'],
        model_b_results['hit_rates']
    ).pvalue

    # Bootstrap confidence intervals for ROI difference
    roi_diff_ci = bootstrap_confidence_interval(
        model_a_results['roi'] - model_b_results['roi'],
        confidence_level=0.95
    )

    return {
        'hit_rate_significant': hit_rate_pvalue < alpha,
        'roi_difference_ci': roi_diff_ci,
        'recommendation': 'Model A' if hit_rate_pvalue < alpha and roi_diff_ci[0] > 0 else 'Inconclusive'
    }
```

---

## Model Selection Criteria

### Tier 1: Minimum Viable Criteria (Must Pass All)

1. **Hit Rate** ≥ 52.4% over 100+ historical bets
2. **ROI** ≥ 3% over full season backtest
3. **Prediction RMSE** ≤ 14 points for spreads
4. **No Data Leakage**: Proper temporal validation
5. **Reproducible**: Same results with fixed random seed

### Tier 2: Model Comparison Criteria (Tie-Breakers)

1. **Higher Hit Rate** (primary tie-breaker)
2. **Higher ROI** (secondary tie-breaker)
3. **Better Calibration** (reliability of confidence estimates)
4. **Lower Complexity** (fewer parameters, easier to maintain)
5. **Faster Training/Inference** (operational efficiency)

### Tier 3: Advanced Criteria (Nice-to-Have)

1. **Feature Interpretability** (SHAP values, linear coefficients)
2. **Robustness** (stable performance across different seasons)
3. **Edge Case Handling** (performance on unusual games/situations)
4. **Uncertainty Quantification** (prediction intervals, confidence scores)

### Model Selection Decision Tree

```mermaid
flowchart TD
    A[Candidate Model] --> B{Tier 1 Criteria}
    B -->|Fails Any| C[REJECT MODEL]
    B -->|Passes All| D{Compare vs Current Best}
    D --> E{Hit Rate Difference}
    E -->|>2% better| F[SELECT NEW MODEL]
    E -->|<2% difference| G{ROI Difference}
    G -->|>3% better| F
    G -->|<3% difference| H{Significantly Better?}
    H -->|Yes p<0.05| F
    H -->|No| I[KEEP CURRENT MODEL]
```

---

## Evaluation Metrics Implementation

### Training Metrics (`src/models/train_model.py`)

- Each training invocation logs RMSE/MAE for both the training window and the configured holdout season into MLflow (`artifacts/mlruns/`).
- The script also writes a metrics CSV to `<model_dir>/<test_year>/metrics/metrics.csv`, capturing spread/total RMSE, MAE, and ensemble variance statistics that map directly to the success thresholds outlined above.
- Ensemble confidence values (standard deviation across members) are emitted alongside weekly predictions so the betting policy can audit variance-based gates.

### Walk-Forward Validation (`scripts/walk_forward_validation.py`)

- Hydra orchestrates walk-forward validation across the configured training and evaluation seasons. For each week, the script fits the selected models, generates predictions, and logs RMSE/MAE to MLflow with keys such as `<year>_<model>_<target>_rmse`.
- Aggregated summaries are materialized under `artifacts/reports/metrics/adjustment_iteration/` and related folders. These CSVs report hit rate, ROI, bet volume, and standard deviation thresholds for every strategy (ensemble, best_single, points_for).
- Each Hydra run persists the composed config (`.hydra/config.yaml`) inside the run directory, ensuring evaluations are fully reproducible.
- **Latest snapshot (2025-11-19):** Targeted walk-forward validation with `data.train_years=[2023]`, `data.test_year=2024`, and weeks 8–13 for both seasons compared the registered staging models (`cfb_spread_lightgbm`, `cfb_total_catboost`) against the legacy ensembles. Results (stored in `artifacts/validation/walk_forward/metrics_summary.csv`):

  | Target | Strategy (weeks 8–13) | 2023 RMSE / MAE | 2024 RMSE / MAE   | Notes                                                                                         |
  | ------ | --------------------- | --------------- | ----------------- | --------------------------------------------------------------------------------------------- |
  | Spread | Legacy ensemble       | 45.72 / 2606.8  | **16.72 / 13.45** | 2023 blow-ups reflect minimal training data; 2024 remains the benchmark.                      |
  | Spread | LightGBM best_single  | 18.81 / 14.69   | 17.98 / 14.43     | Slightly worse than ensemble on 2024 holdout; keep in staging for additional tuning.          |
  | Total  | Legacy ensemble       | 18.47 / 1061.2  | **17.14 / 13.64** | Baseline.                                                                                     |
  | Total  | CatBoost best_single  | 17.28 / 13.68   | 17.17 / 13.66     | Matches ensemble within 0.03 RMSE; acceptable candidate for promotion pending longer horizon. |

  These evaluations inform MLflow Model Registry decisions and monitoring dashboards (see `docs/reports/model_sweep_2025-11-19.md`).

- **Extended window (2019, 2021–2024; weeks 6–13):** Running the validator in two batches to avoid Hydra timeouts produced average RMSE/MAE across five seasons of 17.68/14.07 for the legacy spread ensemble vs. 18.42/14.67 for LightGBM, and 17.34/13.77 for the total ensemble vs. 17.51/13.91 for CatBoost (`artifacts/validation/walk_forward/metrics_summary_2019_2024_avg.csv`). Per-season raw metrics live beside the combined file for deeper inspection.

### Post-Season Scoring & Analysis

- Weekly predictions are scored via `scripts/score_weekly_picks.py`, producing `_scored.csv` outputs with final scores, bet outcomes, and units won/lost.
- `scripts/analysis_cli.py` provides summary commands (`summary`, `segments`, `confidence`) that compute season-level hit rate, ROI, and edge bucket performance from the scored reports.
- These artifacts drive the ROI/unit thresholds in the Success Metrics section and support decision reviews captured in `docs/decisions/decision_log.md`.

## Performance Monitoring

### Real-Time Performance Tracking

#### 1. Weekly Performance Updates

```python
def update_performance_metrics(new_results: List[Dict]) -> Dict:
    \"\"\"
    Update running performance metrics with new week's results
    \"\"\"
    # Load historical performance
    historical = load_performance_history()

    # Add new results
    updated_results = historical + new_results

    # Calculate rolling metrics
    recent_4_weeks = updated_results[-4:]
    season_to_date = updated_results

    metrics = {
        'season_hit_rate': calculate_hit_rate(season_to_date),
        'season_roi': calculate_roi(season_to_date),
        'recent_hit_rate': calculate_hit_rate(recent_4_weeks),
        'recent_roi': calculate_roi(recent_4_weeks),
        'total_units': calculate_units_won(season_to_date),
        'trend': detect_performance_trend(updated_results)
    }

    # Check for performance degradation
    if metrics['recent_hit_rate'] < 0.50:
        send_performance_alert('Hit rate below 50% in last 4 weeks', metrics)

    return metrics
```

#### 2. Model Health Monitoring

```python
def monitor_model_health(model, recent_games: pd.DataFrame) -> Dict:
    \"\"\"
    Monitor model for signs of degradation or drift
    \"\"\"
    health_metrics = {}

    # Feature drift detection
    health_metrics['feature_drift'] = detect_feature_drift(
        recent_games.features,
        historical_feature_distributions
    )

    # Prediction range check
    recent_predictions = model.predict(recent_games.features)
    health_metrics['prediction_range_normal'] = (
        recent_predictions.min() > -50 and recent_predictions.max() < 50
    )

    # Calibration check
    if len(recent_games) >= 20:
        health_metrics['calibration_maintained'] = check_calibration(
            recent_predictions, recent_games.actual
        )

    return health_metrics
```

---

## Reporting & Dashboards

### Performance Report Template

```markdown
# Weekly Model Performance Report

**Week**: {week}  
**Season**: {season}  
**Date**: {date}

## Summary Metrics

- **Hit Rate**: {hit_rate:.1%} (Season: {season_hit_rate:.1%})
- **ROI**: {roi:.1%} (Season: {season_roi:.1%})
- **Units Won This Week**: {weekly_units:+.1f}
- **Total Units**: {total_units:+.1f}

## Bet Analysis

- **Total Bets**: {total_bets}
- **Wins**: {wins} | **Losses**: {losses}
- **Average Edge**: {avg_edge:.1f} points
- **Largest Win**: {max_win:+.1f} units
- **Largest Loss**: {max_loss:+.1f} units

## Model Health

- **Prediction Accuracy**: RMSE {rmse:.1f}, MAE {mae:.1f}
- **Feature Drift**: {feature_drift_status}
- **Calibration**: {calibration_status}

## Recommendations

{recommendations}

---

_Generated automatically by cfb_model evaluation pipeline_
```

### Dashboard Visualizations

```python
# streamlit_app/pages/model_evaluation.py
def show_evaluation_dashboard():
    st.title(\"Model Performance Evaluation\")

    # Load performance data
    performance = load_performance_metrics()

    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(\"Hit Rate\", f\"{performance['hit_rate']:.1%}\",
                 f\"{performance['hit_rate_change']:+.1%}\")
    with col2:
        st.metric(\"ROI\", f\"{performance['roi']:.1%}\",
                 f\"{performance['roi_change']:+.1%}\")
    with col3:
        st.metric(\"Units Won\", f\"{performance['units']:+.1f}\",
                 f\"{performance['units_change']:+.1f}\")
    with col4:
        threshold_color = \"green\" if performance['hit_rate'] >= 0.524 else \"red\"
        st.metric(\"vs Threshold\", \"✅ Pass\" if performance['hit_rate'] >= 0.524 else \"❌ Fail\")

    # Performance over time
    st.subheader(\"Performance Trends\")
    chart_data = load_performance_history_chart()
    st.line_chart(chart_data[['hit_rate', 'roi', 'cumulative_units']])

    # Model comparison
    if st.checkbox(\"Show Model Comparison\"):
        comparison_data = load_model_comparison()
        st.dataframe(comparison_data)

    # Detailed metrics
    st.subheader(\"Detailed Analysis\")
    detailed_metrics = load_detailed_metrics()
    st.json(detailed_metrics)
```

---

## Success Criteria Validation

### MVP Success Validation Checklist

- [ ] **Hit Rate ≥ 52.4%** over minimum 100 bets
- [ ] **ROI ≥ 3%** over full season or 200+ bets
- [ ] **Prediction RMSE ≤ 14** points for spread predictions
- [ ] **Statistical Significance** vs random betting (p < 0.05)
- [ ] **Consistent Performance** across multiple seasons
- [ ] **No Data Leakage** verified through temporal validation
- [ ] **Reproducible Results** with fixed random seeds

### Performance Review Schedule

- **Daily**: Monitor hit rate and units for concerning trends
- **Weekly**: Full evaluation report with recommendations
- **Monthly**: Deep dive analysis, model health assessment
- **Seasonal**: Complete model evaluation and selection review

### Decision Triggers

- **Model Replacement**: Hit rate < 50% for 4+ consecutive weeks
- **Strategy Adjustment**: ROI < 0% for 6+ consecutive weeks
- **Feature Investigation**: RMSE increases >20% from baseline
- **Emergency Review**: Any metric drops below \"unacceptable\" threshold

---

_Last Updated: 2025-01-03_  
_Next Review: After first 4 weeks of live betting_  
_Related Decisions: OPEN-002 (Model Selection), OPEN-005 (Unit Sizing)_
