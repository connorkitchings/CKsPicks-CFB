# Overview: Advanced Feature Engineering

This document provides a high-level overview of advanced feature engineering concepts and summarizes how feature engineering and selection are currently handled in this project.

---

## Understanding Advanced Feature Engineering

Advanced feature engineering is the practice of creating more predictive and nuanced variables from raw data. Where basic feature engineering might involve simple averages or counts, advanced techniques aim to capture **context, interactions, and domain-specific knowledge**.

The key goals are:

1.  **Extract Deeper Insights**: Move beyond surface-level stats (like total yards) to metrics that explain *how* and *why* a team is successful (like `line_yards` or `red_zone_efficiency`).
2.  **Capture Situational Performance**: Model how teams perform in high-leverage, context-dependent situations (e.g., 3rd and long, or inside their own 10-yard line).
3.  **Create Predictive Interactions**: Combine existing features to create new ones that have more predictive power than the individual components. For example, combining a team's rush rate with their success rate on rushing plays.
4.  **Incorporate Domain Knowledge**: Systematically apply expert knowledge of college football to create metrics that are known to be important for winning games.

The features we've planned—such as Rushing Analytics and Situational Efficiency—are perfect examples of this. They break down a single play into more descriptive components, allowing the model to understand the *quality* of a team's performance, not just the quantity.

---

## Current Feature Engineering & Selection Process

### How We Engineer Features

Our current process is a robust, multi-stage pipeline that transforms raw data into model-ready features. The canonical implementation for this is located in `src/cfb_model/data/aggregations/`.

1.  **Staged Aggregation**: We process data in sequential stages, with clear, validated outputs at each step:
    *   **Plays → Enhanced Plays**: Raw play data is cleaned, normalized, and enriched with basic indicators (e.g., `success`, `explosiveness`).
    *   **Enhanced Plays → Drives**: Plays are grouped into possessions to calculate drive-level outcomes.
    *   **Drives → Team-Game**: Drive data is aggregated to a per-game level for each team.
    *   **Team-Game → Team-Season-to-Date**: Game data is aggregated weekly to create season-to-date rolling averages.

2.  **Point-in-Time Correctness**: The pipeline is carefully designed to be **point-in-time correct**. When generating features for a given week, it only uses data from previous weeks, preventing data leakage where the model would know future outcomes.

3.  **Opponent Adjustment**: After initial aggregation, an iterative algorithm adjusts team stats based on the quality of their opponents, providing a more accurate picture of team strength.

### How We Select Features

Our current feature selection strategy is straightforward but effective for the baseline models.

1.  **Comprehensive Feature Set**: The `build_feature_list()` function (located in `src/cfb_model/models/features.py`) programmatically gathers all available numeric features from the processed dataset. It primarily excludes non-numeric ID columns and raw count-based stats that have been superseded by rate-based or opponent-adjusted versions.

2.  **Implicit Selection via Model Training**: The models we use (Ridge, RandomForest) have built-in mechanisms for handling a large number of features:
    *   **Ridge Regression (L2 Regularization)**: This model type penalizes large coefficients, effectively reducing the influence of less important features without removing them entirely. This makes the model robust to noisy or collinear features.
    *   **Random Forest**: By nature, this model performs implicit feature selection. At each split in each tree, it considers a random subset of features, and features that are more predictive will naturally be chosen more often across the ensemble.

3.  **Feature Importance Analysis (SHAP)**: Although not used for *pre-model feature selection*, we use SHAP (SHapley Additive exPlanations) *after* prediction to understand which features are most influential in the model's decisions for a given week. This provides valuable insights and helps guide future feature engineering efforts.

In summary, we currently engineer a broad set of features and rely on the properties of our chosen models to manage them, using post-hoc analysis to inform future development.
