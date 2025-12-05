# PRD: Probabilistic Power Ratings Engine

## 1. Overview

The **Probabilistic Power Ratings (PPR)** engine is a new component in the `cfb_model` ecosystem designed to estimate team strength as a probability distribution rather than a point estimate. This enables calibrated uncertainty quantification for spread and total predictions.

## 2. Problem Statement

Current models (Points-For CatBoost/XGBoost) output point estimates for scores. While accurate on average (RMSE ~17-18), they do not inherently quantify confidence. A 3-point edge on a low-variance game (Army vs. Navy) is much more valuable than a 3-point edge on a high-variance game (USC vs. UCLA), but our current system treats them equally.

## 3. Goals

1.  **Quantify Uncertainty:** Output `rating_mean` and `rating_std` for every team for every week.
2.  **Calibrated Probabilities:** Derive `P(Cover)` and `P(Win)` directly from the posterior predictive distribution.
3.  **Data Efficiency:** Generate stable ratings early in the season using hierarchical priors (e.g., conference strength).

## 4. Technical Requirements

### 4.1. Model Architecture

- **Framework:** PyMC (v5+) or NumPyro.
- **Type:** Bayesian Hierarchical Linear Model.
- **Likelihood:** Student-T (degrees of freedom $\nu$ estimated or fixed at ~30) to handle outliers.
- **Priors:**
  - `Intercept` (Home Field Advantage): Normal(2.5, 0.5).
  - `Conference_Strength`: Hierarchical Normal distribution.
  - `Team_Strength`: Normal(`Conference_Strength`, `sigma_team`).

### 4.2. Inputs

- `games` table (historical scores).
- `teams` table (conference affiliation).
- `betting_lines` (optional, for market-implied priors).

### 4.3. Outputs

- **Artifact:** `artifacts/ratings/ppr_<year>_week<week>.nc` (NetCDF file with posterior traces).
- **CSV:** `artifacts/ratings/ppr_<year>_week<week>_summary.csv` containing:
  - `team_id`, `team_name`
  - `rating_mean`, `rating_std`
  - `offense_rating_mean`, `defense_rating_mean` (if split)
  - `hdi_3%`, `hdi_97%` (Highest Density Interval)

### 4.4. Integration

- A new script `scripts/ratings/train_ppr.py` will handle training.
- A new feature generator `src/features/ppr.py` will load these ratings as features for downstream models.

## 5. Success Metrics

- **Calibration:** The 95% High Density Interval (HDI) of the predicted spread should contain the actual result ~95% of the time.
- **Betting Performance:** A simple strategy betting on `P(Cover) > 52.4%` should yield positive ROI.

## 6. Milestones

- [ ] **Prototype:** Fit a static model on 2024 data.
- [ ] **Backtest:** Run walk-forward validation on 2019-2023.
- [ ] **Pipeline Integration:** Add to `run_pipeline.py`.
