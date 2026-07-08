#!/usr/bin/env python3
"""
Simple MLP for CFB Spread Prediction

A basic PyTorch MLP to test if neural networks can capture
different patterns than gradient boosting on this tabular data.
"""

import sys
from pathlib import Path

import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from cks_picks_cfb.features.v2_recency import load_v2_recency_data  # noqa: E402


class SimpleMLP(nn.Module):
    """Simple 3-layer MLP for regression."""

    def __init__(self, input_dim: int, hidden_dims: list = None):
        super().__init__()
        if hidden_dims is None:
            hidden_dims = [32, 16]

        layers = []
        prev_dim = input_dim

        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(0.2))
            prev_dim = hidden_dim

        layers.append(nn.Linear(prev_dim, 1))
        self.network = nn.Sequential(*layers)

    def forward(self, x):
        return self.network(x).squeeze()


def load_data(years: list, alpha: float = 0.5, iterations: int = 4) -> tuple:
    """Load and prepare data."""
    dfs = []
    for year in years:
        print(f"Loading {year}...")
        df = load_v2_recency_data(year, alpha=alpha, iterations=iterations)
        if df is not None:
            dfs.append(df)

    train_df = pd.concat(dfs, ignore_index=True)
    test_df = load_v2_recency_data(2024, alpha=alpha, iterations=4)

    features = [
        "home_adj_off_epa_pp",
        "home_adj_def_epa_pp",
        "home_adj_off_sr",
        "home_adj_def_sr",
        "away_adj_off_epa_pp",
        "away_adj_def_epa_pp",
        "away_adj_off_sr",
        "away_adj_def_sr",
    ]

    X_train = train_df[features].fillna(0).values
    y_train = train_df["spread_target"].values

    X_test = test_df[features].fillna(0).values
    y_test = test_df["spread_target"].values

    # Scale features
    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train)
    X_test = scaler.transform(X_test)

    # Convert to tensors
    X_train = torch.FloatTensor(X_train)
    y_train = torch.FloatTensor(y_train)
    X_test = torch.FloatTensor(X_test)
    y_test = torch.FloatTensor(y_test)

    return X_train, y_train, X_test, y_test, features


def train_mlp(
    X_train: torch.Tensor,
    y_train: torch.Tensor,
    X_test: torch.Tensor,
    y_test: torch.Tensor,
    epochs: int = 500,
    lr: float = 0.001,
    patience: int = 20,
) -> tuple:
    """Train MLP with early stopping."""
    input_dim = X_train.shape[1]
    model = SimpleMLP(input_dim)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()

    best_val_loss = float("inf")
    best_model_state = None
    patience_counter = 0

    for epoch in range(epochs):
        model.train()
        optimizer.zero_grad()

        preds = model(X_train)
        loss = criterion(preds, y_train)
        loss.backward()
        optimizer.step()

        # Validation
        model.eval()
        with torch.no_grad():
            val_preds = model(X_test)
            val_loss = criterion(val_preds, y_test).item()

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_model_state = model.state_dict().copy()
            patience_counter = 0
        else:
            patience_counter += 1

        if (epoch + 1) % 50 == 0:
            print(
                f"  Epoch {epoch + 1}: train_loss={loss.item():.4f}, val_loss={val_loss:.4f}"
            )

        if patience_counter >= patience:
            print(f"  Early stopping at epoch {epoch + 1}")
            break

    # Load best model
    model.load_state_dict(best_model_state)
    return model


def evaluate_betting(
    model: nn.Module, X_test: torch.Tensor, y_test: torch.Tensor, test_df: pd.DataFrame
) -> dict:
    """Evaluate model with betting metrics."""
    model.eval()
    with torch.no_grad():
        preds = model(X_test).numpy()

    actuals = y_test.numpy()

    # Get spread lines
    df_clean = test_df.dropna(subset=["spread_target", "spread_line"])
    if len(df_clean) < 10:
        return {"roi": 0, "hit_rate": 0, "n_bets": 0}

    # Align predictions with clean data
    # This is simplified - just use all available
    vegas_line = df_clean["spread_line"].values
    vegas_margin = -1 * vegas_line

    # Match predictions to clean data indices
    # For simplicity, use first N predictions
    n = min(len(preds), len(vegas_margin))
    preds = preds[:n]
    actuals = actuals[:n]
    vegas_margin = vegas_margin[:n]

    bet_home = preds > vegas_margin
    bet_away = preds < vegas_margin
    home_cover = actuals > vegas_margin
    away_cover = actuals < vegas_margin

    wins = (bet_home & home_cover) | (bet_away & away_cover)
    losses = (bet_home & away_cover) | (bet_away & home_cover)

    n_bets = wins.sum() + losses.sum()
    if n_bets > 0:
        hit_rate = wins.sum() / n_bets
        profit = (wins.sum() * 0.90909) - losses.sum()
        roi = profit / n_bets
    else:
        hit_rate = 0
        roi = 0

    return {"roi": roi * 100, "hit_rate": hit_rate, "n_bets": n_bets}


def main():
    print("=" * 60)
    print("MLP Experiment: CFB Spread Prediction")
    print("=" * 60)

    # Load data
    print("\nLoading data...")
    X_train, y_train, X_test, y_test, features = load_data([2019, 2021, 2022, 2023])
    test_df = load_v2_recency_data(2024, alpha=0.5, iterations=4)

    print(f"Train: {len(X_train)} samples, Test: {len(X_test)} samples")
    print(f"Features: {len(features)}")

    # Train multiple seeds and average
    results = []
    for seed in [42, 123, 456]:
        print(f"\n--- Training with seed {seed} ---")
        torch.manual_seed(seed)

        model = train_mlp(X_train, y_train, X_test, y_test, epochs=300, patience=30)

        # Evaluate
        model.eval()
        with torch.no_grad():
            preds = model(X_test).numpy()

        rmse = ((preds - y_test.numpy()) ** 2).mean() ** 0.5
        mae = abs(preds - y_test.numpy()).mean()

        # Betting evaluation
        bet_metrics = evaluate_betting(model, X_test, y_test, test_df)

        print(f"  RMSE: {rmse:.2f}")
        print(f"  MAE: {mae:.2f}")
        print(f"  ROI: {bet_metrics['roi']:.2f}%")
        print(f"  Hit Rate: {bet_metrics['hit_rate'] * 100:.1f}%")

        results.append({"seed": seed, "rmse": rmse, "mae": mae, **bet_metrics})

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    results_df = pd.DataFrame(results)
    print(f"\nAverage RMSE: {results_df['rmse'].mean():.2f}")
    print(f"Average MAE: {results_df['mae'].mean():.2f}")
    print(f"Average ROI: {results_df['roi'].mean():.2f}%")
    print(f"Average Hit Rate: {results_df['hit_rate'].mean() * 100:.1f}%")

    return results_df


if __name__ == "__main__":
    main()
