# Research Memo: Probabilistic Power Ratings

## Objective

Develop a "Probabilistic Power Ratings" engine that estimates a _distribution_ of team strength rather than a single point estimate. This will allow us to:

1.  Derive calibrated confidence intervals for spread and total predictions.
2.  Quantify uncertainty in team ratings (e.g., high uncertainty for teams with few games or high variance).
3.  Improve betting edge calculation by integrating over the full outcome distribution.

## Core Concepts

### 1. Bayesian Hierarchical Model

Instead of a simple linear regression or gradient boosting model, we will use a Bayesian framework (likely PyMC or NumPyro) to model team strength.

**Model Structure:**

- **Observation:** Game Score Differential ($S_h - S_a$)
- **Likelihood:** Normal distribution (or Student-T for heavy tails)
- **Mean:** $Rating_h - Rating_a + HomeField$
- **Priors:**
  - $Rating_i \sim N(\mu_{conf}, \sigma_{conf})$ (Hierarchical prior based on conference strength)
  - $HomeField \sim N(2.5, 0.5)$

### 2. State-Space Modeling (Dynamic Ratings)

Team strength is not static; it evolves over the season. We can model this as a random walk or an autoregressive process.

$Rating_{t+1} = \alpha \cdot Rating_t + \epsilon$

This naturally handles "recency" without arbitrary weighting windows.

### 3. Implementation Plan

**Phase 1: Prototype (Sprint 6)**

- Build a simple PyMC model for 2024 data.
- Estimate static team ratings for the whole season.
- Compare posterior predictive distributions to actual game results.

**Phase 2: Dynamic Ratings (Sprint 7)**

- Implement a dynamic model (e.g., Gaussian Random Walk) to track rating evolution week-over-week.
- Backtest against 2019-2023 seasons.

**Phase 3: Integration (Sprint 8)**

- Create a `ProbabilisticRater` class that fits into our existing pipeline.
- Emit `rating_mean` and `rating_std` as features for our downstream CatBoost/XGBoost models (Hybrid Approach).

## Benefits

- **True Edge Detection:** We can calculate the probability that the true spread is > X points different from the Vegas line.
- **Data Efficiency:** Bayesian models handle small sample sizes (early season) gracefully by relying on priors.
- **Interpretability:** We can visualize the "rating envelope" for each team.

## Next Steps

1.  Draft a Product Requirement Document (PRD) for the Probabilistic Power Ratings engine.
2.  Set up a new experiment directory `experiments/probabilistic_ratings`.
3.  Install `pymc` or `numpyro` dependencies.
