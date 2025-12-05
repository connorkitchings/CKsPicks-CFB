# Points-For Model Architecture

## Overview

The **Points-For Model** is the current production architecture for the CFB Model (as of November 2025). Instead of predicting the spread or total directly, this approach predicts the final score for each team independently.

## Core Concept

The fundamental hypothesis is that predicting a team's offensive output ("Points For") is a more stable and learnable task than predicting the difference between two teams (Spread) or the sum of their scores (Total).

By modeling `Home Points` and `Away Points` as separate target variables, we can:

1.  **Capture Pace Effects**: A fast-paced team contributes to higher scores for _both_ sides (more possessions). Independent scoring models naturally capture this if pace features are included.
2.  **Correlate Outcomes**: The spread and total are mathematically linked. If Team A scores a lot, the Total goes up _and_ the Spread likely moves in their favor. Predicting scores unifies these derived markets.
3.  **Simplify Debugging**: If a prediction is wrong, we can see exactly which team over/underperformed their expected output.

## Architecture

### Inputs (Features)

The model uses a "Standard" feature set (approx. 80-100 features) including:

- **Opponent-Adjusted Efficiency**: EPA/play, Success Rate, Yards/Play (adjusted for opponent strength).
- **Pace Metrics**: Seconds/Play, Plays/Game.
- **Recency Weights**: Weighted averages emphasizing the last 3 games.
- **Interaction Terms**: Explicit interactions between Offense and Defense (e.g., `Off_Passing_EPA * Def_Passing_Allowed_EPA`).

### Targets

- **Target 1**: `home_score` (Regression)
- **Target 2**: `away_score` (Regression)

### Algorithm

We use **CatBoostRegressor** for both targets.

- **Ensembling**: Each "model" is actually an ensemble of 5 CatBoost models trained with different random seeds to reduce variance.
- **Loss Function**: RMSE (Root Mean Squared Error).

## Inference

To generate a betting prediction for a game:

1.  **Predict Scores**:
    $$ \hat{S}_{home} = Model_{home}(Features) $$
    $$ \hat{S}_{away} = Model_{away}(Features) $$

2.  **Derive Markets**:

    - **Predicted Spread**: $$ \hat{Spread} = \hat{S}_{away} - \hat{S}_{home} $$ (Note: Negative spread usually favors the home team in betting conventions, but check specific implementation).
    - **Predicted Total**: $$ \hat{Total} = \hat{S}_{home} + \hat{S}_{away} $$

3.  **Calculate Edge**:
    - Compare $\hat{Spread}$ and $\hat{Total}$ to the market lines to find value.

## Advantages vs. Direct Prediction

| Feature              | Points-For                                                     | Direct Spread/Total                                  |
| :------------------- | :------------------------------------------------------------- | :--------------------------------------------------- |
| **Coherence**        | Spread and Total are always consistent.                        | Spread and Total models might contradict each other. |
| **Interpretability** | "Team A will score 35, Team B will score 21"                   | "Team A covers -7" (Harder to say _how_)             |
| **Flexibility**      | Can derive Moneyline probabilities (via Poisson/distribution). | Requires separate Moneyline model.                   |
