# Opponent-Adjustment Analysis Workflow

**Status**: Proposed | **Version**: 1.0 | **Date**: 2025-12-05

This document specifies the process for analyzing, validating, and selecting the optimal number of iterations for the opponent-adjustment feature engineering step. Its goal is to make the adjustment process transparent and data-driven rather than relying on a fixed, unvalidated number of iterations.

This is a supplemental process to the main [Experimentation Workflow](./experimentation_workflow.md).

---

## Guiding Principles

1.  **Transparency**: The effect of opponent adjustment should not be a "black box." We must be able to see how and why a team's ratings change.
2.  **Justification**: The choice of iteration depth (e.g., 2 vs. 4 vs. 6) must be justified by its impact on model performance.
3.  **Stability**: The adjustment process should converge and produce stable, sensible ratings.

---

## The Analysis Process

This process should be run periodically (e.g., once per season) or whenever significant changes are made to the underlying feature calculations.

### Step 1: Generate Multi-Iteration Caches

The data aggregation pipeline should be configured to output the state of opponent-adjusted features after multiple iterations. The standard process will cache the adjusted values for iterations `0, 1, 2, 3, 4, 5, 6`.

-   **Iteration 0**: Raw, unadjusted statistics.
-   **Iteration 1**: First pass of adjustments.
-   ...
-   **Iteration 6**: Final pass.

This provides a complete "trace" of the adjustment process.

### Step 2: Run Iteration Analysis Script

A dedicated script, `scripts/analysis/analyze_adjustment_iterations.py`, will be created to perform two key types of analysis.

#### A. Rating Convergence Analysis (Visual)

This analysis helps build intuition and visually confirm that the adjustment process is stable.

1.  **Input**: The script will take a specific year, a key metric (e.g., `adj_off_epa_pp`), and a list of teams as input.
2.  **Process**: For each specified team, it will plot the value of the metric at each iteration (0 through 6).
3.  **Output**: A chart showing the "path" of each team's rating as it converges.
4.  **Interpretation**:
    *   Do ratings stabilize after a certain number of iterations?
    *   Are the adjustments sensible? (e.g., a team with a weak schedule should see its offensive ratings adjusted downwards).
    *   Are there any teams with oscillating or diverging ratings, which could indicate an issue?

#### B. Performance Impact Analysis (Quantitative)

This analysis determines the optimal number of iterations by measuring its impact on the baseline model's performance.

1.  **Input**: The script will leverage the main training script (`src/train.py`).
2.  **Process**: It will run a series of experiments, one for each iteration of adjustment (e.g., 0 through 6). Each experiment will train the `baseline` model (Ridge Regression) using features from that specific iteration level.
    *   **Experiment 1**: Train baseline model on Iteration 0 features.
    *   **Experiment 2**: Train baseline model on Iteration 1 features.
    *   ...and so on.
3.  **Output**:
    *   A summary table and plot comparing the holdout set performance (RMSE, Hit Rate, ROI) for each iteration level.
    *   The results will be logged to MLflow, tagged by iteration number, for detailed comparison.
4.  **Interpretation**:
    *   Which iteration level produces the best performance for the baseline model?
    *   Does performance plateau or degrade after a certain number of iterations?

### Step 3: Decision and Promotion

Based on the analysis, a decision is made on the optimal number of iterations to use for the official "benchmark" feature set.

1.  **Selection**: The iteration depth that provides the best ROI on the holdout set will be selected as the new default.
2.  **Documentation**: The decision and its supporting evidence (the output from the analysis script) will be recorded in the `decision_log.md`.
3.  **Implementation**: The `conf/features/benchmark_features.yaml` (or its equivalent) will be updated to point to the data from the selected iteration depth.

This process ensures that our choice of opponent-adjustment depth is rigorously tested and validated, forming a core part of our robust feature engineering methodology.
