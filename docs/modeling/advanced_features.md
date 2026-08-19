# Overview: Advanced Feature Engineering

This document provides a high-level overview of advanced feature engineering concepts and summarizes how feature engineering and selection are currently handled in this project.

---

> **Path note:** Current modules live under `src/cks_picks_cfb/features/`. Some historical logs reference `src/cfb_model/...` or `src/data/aggregations/...` layouts that no longer exist.

## Understanding Advanced Feature Engineering

Advanced feature engineering is the practice of creating more predictive and nuanced variables from raw data. Where basic feature engineering might involve simple averages or counts, advanced techniques aim to capture **context, interactions, and domain-specific knowledge**.

The key goals are:

1.  **Extract Deeper Insights**: Move beyond surface-level stats (like total yards) to metrics that explain _how_ and _why_ a team is successful (like `line_yards` or `red_zone_efficiency`).
2.  **Capture Situational Performance**: Model how teams perform in high-leverage, context-dependent situations (e.g., 3rd and long, or inside their own 10-yard line).
3.  **Create Predictive Interactions**: Combine existing features to create new ones that have more predictive power than the individual components. For example, combining a team's rush rate with their success rate on rushing plays.
4.  **Incorporate Domain Knowledge**: Systematically apply expert knowledge of college football to create metrics that are known to be important for winning games.

The features we've planned—such as Rushing Analytics and Situational Efficiency—are perfect examples of this. They break down a single play into more descriptive components, allowing the model to understand the _quality_ of a team's performance, not just the quantity.

---

## Current Feature Engineering & Selection Process

### How We Engineer Features

Our current process is a robust, multi-stage pipeline that transforms raw data into model-ready features. The canonical implementation lives in `src/cks_picks_cfb/features/` (aggregations) and `scripts/pipeline/` (versioned builders).

1.  **Staged Aggregation**: We process data in sequential stages, with clear, validated outputs at each step:
    - **Plays → Enhanced Plays**: Raw play data is cleaned, normalized, and enriched with basic indicators (e.g., `success`, `explosiveness`).
    - **Enhanced Plays → Drives**: Plays are grouped into possessions to calculate drive-level outcomes.
    - **Drives → Team-Game**: Drive data is aggregated to a per-game level for each team.
    - **Team-Game → Team-Season-to-Date**: Game data is aggregated weekly to create season-to-date rolling averages.

2.  **Point-in-Time Correctness**: The pipeline is carefully designed to be **point-in-time correct**. When generating features for a given week, it only uses data from previous weeks, preventing data leakage where the model would know future outcomes.

3.  **Opponent Adjustment**: After initial aggregation, an iterative algorithm adjusts team stats based on the quality of their opponents, providing a more accurate picture of team strength.

### How We Select Features

Feature selection is config-driven (Hydra allow-lists in `conf/features/`, tracked in the [feature registry](../project_org/feature_registry.md)) with a selector module (`src/cks_picks_cfb/features/selector.py`).

1.  **Explicit allow-lists**: Feature groups declare the exact features they consume; wildcards are avoided by policy.

2.  **Implicit Selection via Model Training**: The model families we use (Ridge, CatBoost, monotone blends) have built-in mechanisms for handling a large number of features:
    - **Ridge Regression (L2 Regularization)**: This model type penalizes large coefficients, effectively reducing the influence of less important features without removing them entirely. This makes the model robust to noisy or collinear features.
    - **CatBoost / boosted trees**: Implicit feature selection at splits; less predictive features are naturally used less across the ensemble.

3.  **Post-hoc Analysis (research)**: SHAP-style importance runs only as research (`research/`), never as a production feature gate.

In summary, we currently engineer a broad set of features and rely on the properties of our chosen models to manage them, using post-hoc analysis to inform future development.
