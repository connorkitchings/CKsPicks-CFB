"""Read-only decomposition of the totals error (development view only).

Nothing here is a model. The rolling-origin recentering is a labelled
diagnostic that uses only earlier seasons' mean error; no parameter is fitted
on the rows being scored.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .error_slices import require_development_view


def _by_season_and_pooled(frame: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    groups = [(str(s), g) for s, g in frame.groupby("season", sort=True)]
    return [*groups, ("pooled", frame)]


def paired_errors(common: pd.DataFrame) -> pd.DataFrame:
    """One row per game with margin, total, home-points and away-points errors.

    Implied team points are (total + margin) / 2 for home and
    (total - margin) / 2 for away, so the team-points errors are exact
    combinations of the two target errors.
    """
    require_development_view(common)
    wide = {}
    for target in ("margin", "total"):
        part = common[common["target"].eq(target)].set_index(["season", "game_id"])
        wide[target] = part["actual"] - part["prediction"]
    frame = pd.DataFrame(
        {"margin_error": wide["margin"], "total_error": wide["total"]}
    ).reset_index()
    if frame.isna().any().any():
        raise ValueError("margin and total rows do not cover the same games")
    frame["home_error"] = (frame["total_error"] + frame["margin_error"]) / 2
    frame["away_error"] = (frame["total_error"] - frame["margin_error"]) / 2
    return frame


def team_points_split(errors: pd.DataFrame) -> pd.DataFrame:
    """Bias and MAE of home-points and away-points errors, by season and pooled."""
    rows = [
        {
            "season": label,
            "games": len(part),
            "home_bias": float(part["home_error"].mean()),
            "away_bias": float(part["away_error"].mean()),
            "home_mae": float(part["home_error"].abs().mean()),
            "away_mae": float(part["away_error"].abs().mean()),
        }
        for label, part in _by_season_and_pooled(errors)
    ]
    return pd.DataFrame(rows)


def level_and_slope(total: pd.DataFrame) -> pd.DataFrame:
    """Descriptive regression of actual total on predicted total, per season.

    A slope near 1 with a gap in the means is a pure level offset; a slope
    below 1 means the over-prediction grows with the predicted total.
    """
    rows = []
    for label, part in _by_season_and_pooled(total):
        pred = part["prediction"].to_numpy(float)
        actual = part["actual"].to_numpy(float)
        slope, intercept = np.polyfit(pred, actual, 1)
        rows.append(
            {
                "season": label,
                "games": len(part),
                "mean_predicted": float(pred.mean()),
                "mean_actual": float(actual.mean()),
                "level_gap": float((actual - pred).mean()),
                "slope": float(slope),
                "intercept": float(intercept),
            }
        )
    return pd.DataFrame(rows)


def _scored(part: pd.DataFrame, shift: float) -> dict[str, float]:
    pred = part["prediction"].to_numpy(float) + shift
    actual = part["actual"].to_numpy(float)
    error = actual - pred
    lower = part["interval_90_lower"].to_numpy(float) + shift
    upper = part["interval_90_upper"].to_numpy(float) + shift
    return {
        "mae": float(np.abs(error).mean()),
        "rmse": float(np.sqrt(np.square(error).mean())),
        "bias": float(error.mean()),
        "coverage": float(((actual >= lower) & (actual <= upper)).mean()),
    }


def rolling_recentering(total: pd.DataFrame) -> pd.DataFrame:
    """Diagnostic: shift each season by the mean error of strictly earlier seasons.

    The first season has no earlier evidence and is left unshifted. The
    same-season variant removes that season's own mean error; it uses the scored
    rows, so it is an upper bound on recentering, not a usable rule.
    """
    rows = []
    for i, season in enumerate(sorted(total["season"].unique())):
        part = total[total["season"].eq(season)]
        earlier = total[total["season"].lt(season)]
        shift = float((earlier["actual"] - earlier["prediction"]).mean()) if i else 0.0
        own = float((part["actual"] - part["prediction"]).mean())
        rows.append(
            {
                "season": int(season),
                "games": len(part),
                "shift": shift,
                "base": _scored(part, 0.0),
                "rolling": _scored(part, shift),
                "same_season": _scored(part, own),
            }
        )
    return pd.DataFrame(rows)


def error_correlation(errors: pd.DataFrame) -> pd.DataFrame:
    """Pearson correlation of margin error with total error, by season and pooled."""
    rows = [
        {
            "season": label,
            "games": len(part),
            "correlation": float(
                np.corrcoef(part["margin_error"], part["total_error"])[0, 1]
            ),
        }
        for label, part in _by_season_and_pooled(errors)
    ]
    return pd.DataFrame(rows)


def bias_share_of_mse(total: pd.DataFrame) -> float:
    """Share of the total's mean squared error that is the squared mean error."""
    error = (total["actual"] - total["prediction"]).to_numpy(float)
    return float(error.mean() ** 2 / np.square(error).mean())


def quantile_bands(values: pd.Series, bands: int) -> tuple[pd.Series, list[float]]:
    """Equal-count bands labelled ``band 1`` .. ``band n`` (low to high) and interior edges."""
    edges = [float(q) for q in np.quantile(values, np.arange(1, bands) / bands)]
    index = np.searchsorted(edges, values.to_numpy(float), side="left")
    return pd.Series([f"band {i + 1}" for i in index], index=values.index), edges
