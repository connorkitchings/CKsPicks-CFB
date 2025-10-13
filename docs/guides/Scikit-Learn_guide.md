# Scikit-learn in Practice: The CFB Model

This guide provides a quick reference for how this project uses `scikit-learn` to predict college football game outcomes, connecting core concepts to our specific implementation.

## Core scikit-learn Concepts

### The Estimator API

All scikit-learn algorithms we use follow a consistent interface:

- **`fit(X, y)`**: Trains the model.
- **`predict(X)`**: Generates predictions.
- **`transform(X)`**: Used by preprocessors like `StandardScaler`.

### Installation & Setup

This project uses `uv` for environment and package management.

```bash
# Install all dependencies, including scikit-learn
uv sync --extra dev

# Activate the virtual environment
source .venv/bin/activate
```

## Problem Framing: Regression

This project frames the prediction problem as **regression**, which provides more granular information than simple win/loss classification.

-   **Spread Model Target**: `Home Score - Away Score` (the final margin).
-   **Total Model Target**: `Home Score + Away Score` (the total points).

## Data Structure

-   **Features Matrix (X)**: A `pandas.DataFrame` where each row is a game and columns are features. For our main spread model, features are structured with `home_*` and `away_*` prefixes. For our totals model, we use **differential features** (e.g., `diff_adj_off_epa_pp` = `home_adj_off_epa_pp` - `away_adj_off_epa_pp`).
-   **Target Vector (y)**: A `pandas.Series` containing the score margin or total for each game.

## Feature Engineering

This project's key features are opponent-adjusted, point-in-time correct metrics. The full list and their definitions are maintained in the **[Feature Catalog](../project_org/feature_catalog.md)**.

High-value features include:
-   Opponent-Adjusted EPA (Expected Points Added)
-   Opponent-Adjusted Success Rates
-   Pace and possession-aware metrics like `plays_per_game` and `off_finish_pts_per_opp`.
-   Momentum features (e.g., `metric_last_3`).

## Data Preprocessing Workflow

### 1. Time-Aware Splitting (CRITICAL)

To prevent data leakage, we **never** use a random `train_test_split`. All training and testing is split by time, typically by season.

-   **Training Window**: `2019,2021,2022,2023`
-   **Holdout/Test Year**: `2024`

This is implemented in our training scripts, like `src/cfb_model/models/train_model.py`.

### 2. Scaling and Pipelines

While most of our models do not require scaling, it is critical for some. We use `sklearn.pipeline.Pipeline` to prevent data leakage during preprocessing, especially for models sensitive to feature scale.

**Project Example (`HuberRegressor`):**
```python
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import HuberRegressor

# As seen in our training script, this prevents data leakage
huber_pipeline = Pipeline([
    ('scaler', StandardScaler()),
    ('model', HuberRegressor(epsilon=1.35))
])

# The pipeline is then fit on the training data
huber_pipeline.fit(X_train, y_train)
```

## Model Selection: Ensemble Architecture

This project uses an **ensemble** approach to improve stability and reduce variance. The final prediction is an average of the predictions from several diverse models. See the **[Modeling Baseline](../project_org/modeling_baseline.md)** for more details.

### Spread Model Ensemble

-   `sklearn.linear_model.Ridge(alpha=0.1)`
-   `sklearn.linear_model.ElasticNet(alpha=0.1, l1_ratio=0.5)`
-   `sklearn.linear_model.HuberRegressor(epsilon=1.35)` (within a `Pipeline`)

### Total Model Ensemble

-   `sklearn.ensemble.RandomForestRegressor(n_estimators=200, max_depth=8, ...)`
-   `sklearn.ensemble.GradientBoostingRegressor(n_estimators=200, learning_rate=0.1, ...)`

## Model Evaluation

Our primary success metric is **hit rate** (>52.4%), not just prediction accuracy (RMSE/MAE). See **[Model Evaluation Criteria](../project_org/model_evaluation_criteria.md)**.

### Cross-Validation

For robust evaluation and hyperparameter tuning, we use `sklearn.model_selection.TimeSeriesSplit` to respect the temporal order of the data.

```python
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV

# Example from scripts/optimize_hyperparameters.py
cv_splitter = TimeSeriesSplit(n_splits=5)

grid_search = GridSearchCV(
    estimator=model,
    param_grid=param_grid,
    cv=cv_splitter,
    scoring='neg_root_mean_squared_error'
)
```

## Hyperparameter Tuning

We use `GridSearchCV` with our time-series cross-validator to systematically find the best parameters. This process is implemented in `scripts/optimize_hyperparameters.py`.

## Model Persistence & Deployment

### Save Trained Model

We use `joblib` to save the entire trained model (or pipeline) to disk.

```python
import joblib

# Models are saved to the models/<year>/ directory
model_path = 'models/2024/spread_ridge.joblib'
joblib.dump(trained_model, model_path)
```

### Load and Make Predictions

The weekly prediction script (`src/cfb_model/scripts/generate_weekly_bets_clean.py`) loads all models in an ensemble, generates predictions from each, and averages the results.

## Common Pitfalls in This Project

1.  **Data Leakage**: The biggest risk. Solved by using strict time-based splits for all training and validation, and by generating features in a point-in-time correct manner.
2.  **Ignoring Opponent Adjustments**: Raw stats are misleading. All our core features are opponent-adjusted.
3.  **Forgetting Scaling**: Iterative models like `HuberRegressor` may fail to converge without feature scaling. Using a `Pipeline` is the safest way to apply it.
4.  **Incorrect Betting Logic**: A subtle but critical bug was fixed where model spreads were compared to raw lines instead of expected margins. Always ensure `predicted_margin > -vegas_line`.

## Data Sources

-   **Primary**: [CollegeFootballData.com](https://collegefootballdata.com/) API, accessed via the `cfbd` Python client.